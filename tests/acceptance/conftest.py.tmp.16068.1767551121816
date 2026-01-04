import os
import pytest


def has_google_credentials() -> bool:
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    sheets_id = os.getenv("GOOGLE_SHEETS_ID")

    if not creds_path or not sheets_id:
        return False

    if not os.path.exists(creds_path):
        return False

    return True


skip_without_credentials = pytest.mark.skipif(
    not has_google_credentials(),
    reason=(
        "Google credentials not available. "
        "Set GOOGLE_APPLICATION_CREDENTIALS and GOOGLE_SHEETS_ID "
        "to run acceptance tests."
    ),
)
