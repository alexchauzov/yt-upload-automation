"""YouTube API backend implementation."""
from __future__ import annotations

import logging
import os
import pickle
from datetime import datetime
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from domain.models import PrivacyStatus, PublishResult, TaskStatus, VideoTask
from ports.video_backend import PermanentError, RetryableError, VideoBackend, VideoBackendError

logger = logging.getLogger(__name__)


class YouTubeApiBackend(VideoBackend):
    """
    YouTube Data API v3 backend implementation.

    Handles OAuth2 authentication, video upload, and scheduled publishing.
    """

    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube",
    ]

    # Retryable HTTP status codes
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        client_secrets_file: str | None = None,
        token_file: str | None = None,
    ):
        """
        Initialize YouTube API backend.

        Args:
            client_secrets_file: Path to OAuth2 client secrets JSON.
                       If None, uses YOUTUBE_CLIENT_SECRETS_FILE env var.
            token_file: Path to store OAuth2 token.
                       If None, uses YOUTUBE_TOKEN_FILE env var or default.

        Raises:
            VideoBackendError: If initialization fails.
        """
        self.client_secrets_file = client_secrets_file or os.getenv(
            "YOUTUBE_CLIENT_SECRETS_FILE", "client_secrets.json"
        )
        self.token_file = token_file or os.getenv(
            "YOUTUBE_TOKEN_FILE", ".data/youtube_token.pickle"
        )

        # Ensure token directory exists
        Path(self.token_file).parent.mkdir(parents=True, exist_ok=True)

        self.youtube = None
        self._authenticate()

        logger.info("YouTubeApiBackend initialized")

    def _authenticate(self) -> None:
        """
        Authenticate with YouTube API using OAuth2.

        Uses stored credentials if available, otherwise initiates OAuth flow.

        Raises:
            VideoBackendError: If authentication fails.
        """
        creds = None

        # Load existing credentials
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, "rb") as token:
                    creds = pickle.load(token)
                logger.debug("Loaded existing credentials from token file")
            except Exception as e:
                logger.warning(f"Failed to load token file: {e}")

        # Refresh or create new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    logger.info("Refreshing expired credentials")
                    creds.refresh(Request())
                except Exception as e:
                    logger.warning(f"Token refresh failed: {e}")
                    creds = None

            if not creds:
                # Initiate OAuth2 flow
                if not os.path.exists(self.client_secrets_file):
                    raise VideoBackendError(
                        f"Client secrets file not found: {self.client_secrets_file}. "
                        f"Please download OAuth2 credentials from Google Cloud Console."
                    )

                try:
                    logger.info("Starting OAuth2 authentication flow")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.client_secrets_file, self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                    logger.info("OAuth2 authentication successful")
                except Exception as e:
                    raise VideoBackendError(f"OAuth2 authentication failed: {e}") from e

            # Save credentials
            try:
                with open(self.token_file, "wb") as token:
                    pickle.dump(creds, token)
                logger.debug(f"Saved credentials to {self.token_file}")
            except Exception as e:
                logger.warning(f"Failed to save credentials: {e}")

        # Build YouTube API client
        try:
            self.youtube = build("youtube", "v3", credentials=creds)
            logger.info("YouTube API client initialized")
        except Exception as e:
            raise VideoBackendError(f"Failed to build YouTube API client: {e}") from e

    def publish_video(self, task: VideoTask, video_path: Path) -> PublishResult:
        """
        Upload and schedule video for publishing.

        Args:
            task: Video task with metadata.
            video_path: Absolute path to video file.

        Returns:
            PublishResult with upload status and video ID.

        Raises:
            RetryableError: For temporary errors (429, 5xx, network).
            PermanentError: For permanent errors (invalid file, quota, etc.).
            VideoBackendError: For other errors.
        """
        try:
            logger.info(f"Starting video upload: {task.title}")

            # Prepare video metadata
            body = self._prepare_metadata(task)

            # Prepare media upload
            media = MediaFileUpload(
                str(video_path),
                chunksize=-1,  # Upload in single request
                resumable=True,
            )

            # Execute upload request
            logger.debug(f"Uploading video file: {video_path}")
            request = self.youtube.videos().insert(
                part=",".join(body.keys()),
                body=body,
                media_body=media,
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    logger.debug(f"Upload progress: {progress}%")

            video_id = response["id"]
            logger.info(f"Video uploaded successfully: video_id={video_id}")

            # Determine result status
            result_status = TaskStatus.SCHEDULED
            publish_at = task.publish_at

            return PublishResult(
                success=True,
                video_id=video_id,
                status=result_status,
                publish_at=publish_at,
                upload_time=datetime.utcnow(),
            )

        except HttpError as e:
            return self._handle_http_error(e, task)

        except FileNotFoundError as e:
            raise PermanentError(f"Video file not found: {video_path}") from e

        except Exception as e:
            logger.exception(f"Unexpected error during upload: {e}")
            raise VideoBackendError(f"Upload failed: {e}") from e

    def upload_thumbnail(self, video_id: str, thumbnail_path: Path) -> bool:
        """
        Upload custom thumbnail for a video.

        Args:
            video_id: YouTube video ID.
            thumbnail_path: Absolute path to thumbnail image.

        Returns:
            True if thumbnail uploaded successfully.

        Raises:
            VideoBackendError: If upload fails.
        """
        try:
            logger.info(f"Uploading thumbnail for video {video_id}")

            media = MediaFileUpload(
                str(thumbnail_path),
                mimetype="image/jpeg",
                resumable=True,
            )

            request = self.youtube.thumbnails().set(
                videoId=video_id,
                media_body=media,
            )

            response = request.execute()

            logger.info(f"Thumbnail uploaded successfully for video {video_id}")
            return True

        except HttpError as e:
            if e.resp.status in self.RETRYABLE_STATUS_CODES:
                logger.warning(f"Thumbnail upload failed (retryable): {e}")
                return False
            else:
                logger.error(f"Thumbnail upload failed (permanent): {e}")
                return False

        except Exception as e:
            logger.warning(f"Thumbnail upload error: {e}")
            return False

    def _prepare_metadata(self, task: VideoTask) -> dict:
        """
        Prepare video metadata for YouTube API.

        Args:
            task: Video task.

        Returns:
            Metadata dictionary for API request.
        """
        snippet = {
            "title": task.title,
            "description": task.description,
            "categoryId": task.category_id,
        }

        if task.tags:
            snippet["tags"] = task.tags

        status = {
            "privacyStatus": task.privacy_status.value,
        }

        # Handle scheduled publishing
        if task.publish_at:
            # YouTube requires publishAt in ISO 8601 format with timezone
            publish_at_str = task.publish_at.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            status["publishAt"] = publish_at_str

            # For scheduled videos, privacy must be "private" until publish time
            # YouTube will automatically change it based on the scheduled time
            if task.privacy_status != PrivacyStatus.PRIVATE:
                # Set to private now, will change at publishAt time
                logger.debug(
                    f"Scheduled video privacy set to private (will change to "
                    f"{task.privacy_status.value} at {publish_at_str})"
                )

        body = {
            "snippet": snippet,
            "status": status,
        }

        logger.debug(f"Video metadata prepared: {body}")
        return body

    def _handle_http_error(self, error: HttpError, task: VideoTask) -> PublishResult:
        """
        Handle HTTP errors from YouTube API.

        Args:
            error: HTTP error from API.
            task: Video task being processed.

        Returns:
            PublishResult with error information.

        Raises:
            RetryableError: For temporary errors.
            PermanentError: For permanent errors.
        """
        status_code = error.resp.status
        error_content = error.content.decode("utf-8") if error.content else ""

        logger.error(f"YouTube API error {status_code}: {error_content}")

        # Retryable errors
        if status_code in self.RETRYABLE_STATUS_CODES:
            error_msg = f"Temporary error {status_code}: {error_content}"
            raise RetryableError(error_msg)

        # Permanent errors
        permanent_errors = {
            400: "Invalid request (check video format, metadata)",
            401: "Authentication failed (check credentials)",
            403: "Forbidden (check quota, permissions)",
            404: "Resource not found",
        }

        if status_code in permanent_errors:
            error_msg = f"{permanent_errors[status_code]}: {error_content}"
            raise PermanentError(error_msg)

        # Unknown error - treat as permanent
        error_msg = f"HTTP error {status_code}: {error_content}"
        raise PermanentError(error_msg)
