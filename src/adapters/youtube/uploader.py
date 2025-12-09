"""
YouTube video uploader implementation.

Handles video uploads to YouTube via YouTube Data API v3.
"""

import os
import json
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

from src.core.config import Config, get_config


class YouTubeUploader:
    """
    YouTube video uploader.

    Handles OAuth authentication and video upload to YouTube.
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize YouTube uploader.

        Args:
            config: Configuration object. If None, uses get_config()
        """
        self.config = config if config is not None else get_config()
        self._service = None

    def _get_credentials(self) -> Credentials:
        """
        Get or refresh OAuth credentials.

        Loads credentials from token file if it exists, otherwise
        initiates OAuth flow and saves credentials.

        Returns:
            Valid OAuth credentials

        Raises:
            FileNotFoundError: If credentials file doesn't exist
        """
        credentials = None
        token_path = Path(self.config.token_file)

        # Load existing credentials if available
        if token_path.exists():
            credentials = Credentials.from_authorized_user_file(
                str(token_path),
                self.config.youtube_scopes
            )

        # Refresh or obtain new credentials
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                # Verify credentials file exists
                credentials_path = Path(self.config.credentials_file)
                if not credentials_path.exists():
                    raise FileNotFoundError(
                        f"Credentials file not found: {self.config.credentials_file}. "
                        "Please download it from Google Cloud Console."
                    )

                # Run OAuth flow
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.config.credentials_file,
                    self.config.youtube_scopes
                )
                credentials = flow.run_local_server(port=0)

            # Save credentials for future use
            token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(token_path, "w") as token_file:
                token_file.write(credentials.to_json())

        return credentials

    def _get_service(self):
        """
        Get or create YouTube API service.

        Returns:
            YouTube API service instance
        """
        if self._service is not None:
            return self._service

        credentials = self._get_credentials()
        self._service = build("youtube", "v3", credentials=credentials)
        return self._service

    def upload_video(
        self,
        file_path: str,
        title: str,
        description: str = "",
        tags: Optional[list[str]] = None,
        privacy_status: str = "unlisted",
    ) -> str:
        """
        Upload video to YouTube.

        Args:
            file_path: Path to video file
            title: Video title
            description: Video description (optional)
            tags: List of video tags (optional)
            privacy_status: Privacy status: "public", "unlisted", or "private"

        Returns:
            Video ID of uploaded video

        Raises:
            ValueError: If privacy_status is invalid
            FileNotFoundError: If video file doesn't exist
            HttpError: If YouTube API returns an error
        """
        # Validate privacy status
        valid_privacy_statuses = ["public", "unlisted", "private"]
        if privacy_status not in valid_privacy_statuses:
            raise ValueError(
                f"Invalid privacy_status: {privacy_status}. "
                f"Must be one of: {', '.join(valid_privacy_statuses)}"
            )

        # Verify file exists
        video_path = Path(file_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {file_path}")

        # Get YouTube service
        service = self._get_service()

        # Prepare request body
        body = {
            "snippet": {
                "title": title,
                "description": description,
            },
            "status": {
                "privacyStatus": privacy_status
            }
        }

        # Add tags if provided
        if tags is not None:
            body["snippet"]["tags"] = tags

        # Create media upload
        media = MediaFileUpload(
            str(video_path),
            resumable=False
        )

        try:
            # Execute upload request
            request = service.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )
            response = request.execute()

            # Return video ID
            return response["id"]

        except HttpError as e:
            error_message = f"YouTube API error: {e.resp.status} - {e.content.decode()}"
            raise HttpError(e.resp, e.content, uri=e.uri) from e
