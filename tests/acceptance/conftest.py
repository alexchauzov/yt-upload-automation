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

    if not os.getenv("GOOGLE_SHEETS_ID"):
        missing.append("GOOGLE_SHEETS_ID env var not set")

    return missing


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
            "  1. Create .env file with GOOGLE_APPLICATION_CREDENTIALS and GOOGLE_SHEETS_ID\n"
            "  2. Ensure the credentials file exists\n\n"
            "For GitHub Actions:\n"
            "  Configure these secrets in Settings > Secrets and variables > Actions:\n"
            "  - GOOGLE_SA_JSON (full service account JSON)\n"
            "  - GOOGLE_SHEETS_ID\n"
            "  - GOOGLE_SHEETS_RANGE\n\n"
            "See README.md for detailed setup instructions."
        )
