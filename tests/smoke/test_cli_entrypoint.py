import pytest
import subprocess
import sys


@pytest.mark.smoke
def test_cli_help_command():
    result = subprocess.run(
        [sys.executable, "-m", "app.main", "--help"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0
    assert "YouTube Publisher" in result.stdout
    assert "--dry-run" in result.stdout
