import os
import time
import uuid
from datetime import datetime

import pytest
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

_session_has_failures = False


def pytest_runtest_logreport(report):
    """Track if any test failed during the session."""
    global _session_has_failures
    if report.failed:
        _session_has_failures = True


def get_missing_credentials() -> list[str]:
    """Return list of missing credential configurations."""
    missing = []

    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        missing.append("GOOGLE_APPLICATION_CREDENTIALS env var not set")
    elif not os.path.exists(creds_path):
        missing.append(f"GOOGLE_APPLICATION_CREDENTIALS file not found: {creds_path}")

    if not os.getenv("TEMPLATE_SPREADSHEET_ID"):
        missing.append("TEMPLATE_SPREADSHEET_ID env var not set")

    if not os.getenv("RUNS_FOLDER_ID"):
        missing.append("RUNS_FOLDER_ID env var not set")

    if not os.getenv("HISTORY_FOLDER_ID"):
        missing.append("HISTORY_FOLDER_ID env var not set")

    return missing


def _get_drive_service():
    """Build Google Drive API service."""
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    credentials = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=[
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets",
        ],
    )
    return build("drive", "v3", credentials=credentials)


def _generate_copy_name() -> str:
    """Generate unique name for spreadsheet copy."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S.%f")[:-3]
    unique_id = uuid.uuid4().hex[:8]
    github_run_id = os.getenv("GITHUB_RUN_ID", "")
    if github_run_id:
        return f"yt-upload-automation__{timestamp}__run-{github_run_id}__{unique_id}"
    return f"yt-upload-automation__{timestamp}__{unique_id}"


def _copy_spreadsheet(drive_service, template_id: str, name: str, folder_id: str) -> str:
    """Copy spreadsheet to target folder, return new file ID."""
    body = {"name": name, "parents": [folder_id]}
    copied_file = drive_service.files().copy(fileId=template_id, body=body).execute()
    return copied_file["id"]


def _move_file(drive_service, file_id: str, from_folder_id: str, to_folder_id: str):
    """Move file from one folder to another."""
    drive_service.files().update(
        fileId=file_id,
        addParents=to_folder_id,
        removeParents=from_folder_id,
    ).execute()


def _wait_for_spreadsheet_ready(spreadsheet_id: str, max_retries: int = 5, delay: float = 1.0):
    """Wait until Sheets API can access the copied spreadsheet."""
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    credentials = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    sheets_service = build("sheets", "v4", credentials=credentials)

    for attempt in range(max_retries):
        try:
            sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            return
        except HttpError as e:
            if attempt < max_retries - 1:
                time.sleep(delay * (attempt + 1))
            else:
                raise RuntimeError(
                    f"Spreadsheet {spreadsheet_id} not accessible after {max_retries} retries"
                ) from e


@pytest.fixture(scope="session")
def run_spreadsheet_id(request):
    """
    Create a copy of template spreadsheet for this test run.

    On teardown:
    - If all tests passed: move to HISTORY_FOLDER_ID
    - If any test failed: leave in RUNS_FOLDER_ID
    """
    template_id = os.getenv("TEMPLATE_SPREADSHEET_ID")
    runs_folder_id = os.getenv("RUNS_FOLDER_ID")
    history_folder_id = os.getenv("HISTORY_FOLDER_ID")

    drive_service = _get_drive_service()
    copy_name = _generate_copy_name()

    new_spreadsheet_id = _copy_spreadsheet(
        drive_service, template_id, copy_name, runs_folder_id
    )

    _wait_for_spreadsheet_ready(new_spreadsheet_id)

    yield new_spreadsheet_id

    global _session_has_failures
    if not _session_has_failures:
        _move_file(drive_service, new_spreadsheet_id, runs_folder_id, history_folder_id)


@pytest.fixture(autouse=True)
def require_google_credentials():
    """Fail acceptance tests with clear message if credentials are missing."""
    missing = get_missing_credentials()
    if missing:
        pytest.fail(
            "Google Sheets credentials not configured.\n\n"
            "Missing:\n"
            + "\n".join(f"  - {m}" for m in missing)
            + "\n\n"
            "For local development:\n"
            "  1. Create .env file with:\n"
            "     - GOOGLE_APPLICATION_CREDENTIALS\n"
            "     - TEMPLATE_SPREADSHEET_ID\n"
            "     - RUNS_FOLDER_ID\n"
            "     - HISTORY_FOLDER_ID\n"
            "  2. Ensure the credentials file exists\n\n"
            "For GitHub Actions:\n"
            "  Configure these secrets in Settings > Secrets and variables > Actions:\n"
            "  - GOOGLE_SA_JSON (full service account JSON)\n"
            "  - TEMPLATE_SPREADSHEET_ID\n"
            "  - RUNS_FOLDER_ID\n"
            "  - HISTORY_FOLDER_ID\n\n"
            "See README.md for detailed setup instructions."
        )
