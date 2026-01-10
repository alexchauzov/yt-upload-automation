import pytest

from tests.acceptance.conftest import skip_without_credentials


@pytest.mark.acceptance
@skip_without_credentials
class TestGoogleSheetsLiveRead:
    pass
