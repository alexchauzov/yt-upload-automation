"""
Configuration module for the application.

Handles reading environment variables and paths to credential files.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv


@dataclass
class Config:
    """
    Application configuration for YouTube uploader.

    Attributes:
        youtube_scopes: List of YouTube API OAuth scopes
        credentials_file: Path to YouTube API credentials JSON file
        token_file: Path to OAuth token storage file
    """
    youtube_scopes: list[str]
    credentials_file: str
    token_file: str


# Module-level cache for configuration
_config_instance: Config | None = None


def get_config() -> Config:
    """
    Get application configuration (singleton pattern).

    Reads configuration from environment variables with sensible defaults.
    Loads .env file if present in the project root.

    Environment variables:
        YT_SCOPES: Comma or space-separated list of YouTube API scopes
            Default: "https://www.googleapis.com/auth/youtube.upload"
        YT_CREDENTIALS_FILE: Path to credentials.json
            Default: "credentials.json"
        YT_TOKEN_FILE: Path to token.json
            Default: "token.json"

    Returns:
        Config instance with loaded configuration
    """
    global _config_instance

    if _config_instance is not None:
        return _config_instance

    # Load .env file if it exists
    load_dotenv()

    # Read YouTube scopes
    scopes_str = os.getenv("YT_SCOPES", "https://www.googleapis.com/auth/youtube.upload")
    # Split by comma or space and strip whitespace
    scopes = [s.strip() for s in scopes_str.replace(",", " ").split() if s.strip()]

    # Read file paths
    credentials_file = os.getenv("YT_CREDENTIALS_FILE", "credentials.json")
    token_file = os.getenv("YT_TOKEN_FILE", "token.json")

    _config_instance = Config(
        youtube_scopes=scopes,
        credentials_file=credentials_file,
        token_file=token_file
    )

    return _config_instance
