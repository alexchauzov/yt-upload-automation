import os

import pytest
from dotenv import load_dotenv

from tests.acceptance.test_file_workflow_helpers import reset_workflow_fs

load_dotenv()


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

    if not os.getenv("RUNTIME_SPREADSHEET_ID"):
        missing.append("RUNTIME_SPREADSHEET_ID env var not set")

    return missing


@pytest.fixture(scope="session")
def run_spreadsheet_id():
    """Return runtime spreadsheet ID for test execution."""
    return os.getenv("RUNTIME_SPREADSHEET_ID")


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
            "     - RUNTIME_SPREADSHEET_ID\n"
            "  2. Ensure the credentials file exists\n\n"
            "For GitHub Actions:\n"
            "  Configure these secrets in Settings > Secrets and variables > Actions:\n"
            "  - GOOGLE_SA_JSON (full service account JSON)\n"
            "  - TEMPLATE_SPREADSHEET_ID\n"
            "  - RUNTIME_SPREADSHEET_ID\n\n"
            "See README.md for detailed setup instructions."
        )


@pytest.fixture(scope="session")
def workflow_dirs(tmp_path_factory):
    """
    Create workflow directory structure for file tests.
    Session-scoped: created once, shared across tests.
    Cleaned up automatically by pytest tmp_path_factory.
    """
    temp_root = tmp_path_factory.mktemp("workflow")
    dirs = reset_workflow_fs(temp_root)

    # Override env vars for this session
    os.environ["VIDEO_WATCH_DIR"] = str(dirs["WATCH"])
    os.environ["VIDEO_IN_PROGRESS_DIR"] = str(dirs["IN_PROGRESS"])
    os.environ["VIDEO_UPLOADED_DIR"] = str(dirs["UPLOADED"])

    return dirs


@pytest.fixture
def clean_workflow_dirs(workflow_dirs):
    """
    Clean all workflow directories before each test.
    Ensures test isolation.
    """
    for dir_path in workflow_dirs.values():
        if dir_path.exists():
            for file in dir_path.iterdir():
                file.unlink()
    yield workflow_dirs
