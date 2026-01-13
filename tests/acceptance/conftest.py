import os

import pytest
from dotenv import load_dotenv

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
