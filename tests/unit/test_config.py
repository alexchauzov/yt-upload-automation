"""
Unit tests for configuration module.

Tests configuration loading from environment variables.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core import config


@pytest.fixture(autouse=True)
def reset_config_cache():
    """Reset config cache before each test."""
    config._config_instance = None
    yield
    config._config_instance = None


def test_get_config_default_values(monkeypatch):
    """Test get_config() with default values (no env vars set)."""
    # Clear environment variables
    monkeypatch.delenv("YT_SCOPES", raising=False)
    monkeypatch.delenv("YT_CREDENTIALS_FILE", raising=False)
    monkeypatch.delenv("YT_TOKEN_FILE", raising=False)

    # Get config
    cfg = config.get_config()

    # Verify defaults
    assert cfg.youtube_scopes == ["https://www.googleapis.com/auth/youtube.upload"]
    assert cfg.credentials_file == "credentials.json"
    assert cfg.token_file == "token.json"


def test_get_config_custom_values(monkeypatch):
    """Test get_config() with custom environment variables."""
    # Set custom environment variables
    monkeypatch.setenv("YT_SCOPES", "https://www.googleapis.com/auth/youtube.force-ssl")
    monkeypatch.setenv("YT_CREDENTIALS_FILE", "custom_credentials.json")
    monkeypatch.setenv("YT_TOKEN_FILE", "custom_token.json")

    # Get config
    cfg = config.get_config()

    # Verify custom values
    assert cfg.youtube_scopes == ["https://www.googleapis.com/auth/youtube.force-ssl"]
    assert cfg.credentials_file == "custom_credentials.json"
    assert cfg.token_file == "custom_token.json"


def test_get_config_multiple_scopes_comma_separated(monkeypatch):
    """Test parsing multiple scopes separated by commas."""
    monkeypatch.setenv("YT_SCOPES", "scope1,scope2,scope3")
    monkeypatch.delenv("YT_CREDENTIALS_FILE", raising=False)
    monkeypatch.delenv("YT_TOKEN_FILE", raising=False)

    cfg = config.get_config()

    assert cfg.youtube_scopes == ["scope1", "scope2", "scope3"]


def test_get_config_multiple_scopes_space_separated(monkeypatch):
    """Test parsing multiple scopes separated by spaces."""
    monkeypatch.setenv("YT_SCOPES", "scope1 scope2 scope3")
    monkeypatch.delenv("YT_CREDENTIALS_FILE", raising=False)
    monkeypatch.delenv("YT_TOKEN_FILE", raising=False)

    cfg = config.get_config()

    assert cfg.youtube_scopes == ["scope1", "scope2", "scope3"]


def test_get_config_multiple_scopes_mixed_separators(monkeypatch):
    """Test parsing multiple scopes with mixed separators."""
    monkeypatch.setenv("YT_SCOPES", "scope1, scope2  ,  scope3")
    monkeypatch.delenv("YT_CREDENTIALS_FILE", raising=False)
    monkeypatch.delenv("YT_TOKEN_FILE", raising=False)

    cfg = config.get_config()

    assert cfg.youtube_scopes == ["scope1", "scope2", "scope3"]


def test_get_config_caching(monkeypatch):
    """Test that get_config() returns cached instance."""
    monkeypatch.delenv("YT_SCOPES", raising=False)
    monkeypatch.delenv("YT_CREDENTIALS_FILE", raising=False)
    monkeypatch.delenv("YT_TOKEN_FILE", raising=False)

    cfg1 = config.get_config()
    cfg2 = config.get_config()

    # Should return the same instance
    assert cfg1 is cfg2
