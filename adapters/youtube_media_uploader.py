"""YouTube API media uploader implementation."""
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

from domain.models import PrivacyStatus, PublishResult, Task, TaskStatus
from ports.media_store import MediaStore
from ports.media_uploader import MediaUploader, MediaUploaderError, PermanentError, RetryableError

logger = logging.getLogger(__name__)

class YouTubeMediaUploader(MediaUploader):
    """
    YouTube Data API v3 media uploader implementation.

    Handles OAuth2 authentication, media upload, and scheduled publishing.
    Requires local file access, so uses MediaStore to resolve media references.
    """

    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube",
    ]

    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        media_store: MediaStore,
        client_secrets_file: str | None = None,
        token_file: str | None = None,
    ):
        """
        Initialize YouTube API media uploader.

        Args:
            media_store: Media store for resolving media references to local paths.
            client_secrets_file: Path to OAuth2 client secrets JSON.
                       If None, uses YOUTUBE_CLIENT_SECRETS_FILE env var.
            token_file: Path to store OAuth2 token.
                       If None, uses YOUTUBE_TOKEN_FILE env var or default.

        Raises:
            MediaUploaderError: If initialization fails.
        """
        self.media_store = media_store
        self.client_secrets_file = client_secrets_file or os.getenv(
            "YOUTUBE_CLIENT_SECRETS_FILE", "client_secrets.json"
        )
        self.token_file = token_file or os.getenv(
            "YOUTUBE_TOKEN_FILE", ".data/youtube_token.pickle"
        )

        Path(self.token_file).parent.mkdir(parents=True, exist_ok=True)

        self.youtube = None
        self._authenticate()

        logger.info("YouTubeMediaUploader initialized")

    def _authenticate(self) -> None:
        """
        Authenticate with YouTube API using OAuth2.

        Uses stored credentials if available, otherwise initiates OAuth flow.

        Raises:
            MediaUploaderError: If authentication fails.
        """
        creds = None

        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, "rb") as token:
                    creds = pickle.load(token)
                logger.debug("Loaded existing credentials from token file")
            except Exception as e:
                logger.warning(f"Failed to load token file: {e}")

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    logger.info("Refreshing expired credentials")
                    creds.refresh(Request())
                except Exception as e:
                    logger.warning(f"Token refresh failed: {e}")
                    creds = None

            if not creds:
                if not os.path.exists(self.client_secrets_file):
                    raise MediaUploaderError(
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
                    raise MediaUploaderError(f"OAuth2 authentication failed: {e}") from e

            try:
                with open(self.token_file, "wb") as token:
                    pickle.dump(creds, token)
                logger.debug(f"Saved credentials to {self.token_file}")
            except Exception as e:
                logger.warning(f"Failed to save credentials: {e}")

        try:
            self.youtube = build("youtube", "v3", credentials=creds)
            logger.info("YouTube API client initialized")
        except Exception as e:
            raise MediaUploaderError(f"Failed to build YouTube API client: {e}") from e

    def publish_media(self, task: Task, media_ref: str) -> PublishResult:
        """
        Upload and schedule media for publishing.

        Args:
            task: Media task with metadata.
            media_ref: Media reference (resolved to local file path internally via MediaStore).

        Returns:
            PublishResult with upload status and video ID.

        Raises:
            RetryableError: For temporary errors (429, 5xx, network).
            PermanentError: For permanent errors (invalid file, quota, etc.).
            MediaUploaderError: For other errors.
        """
        try:
            logger.info(f"Starting media upload: {task.title}")

            # Request local file path from media_store
            # This validates the reference and returns the local path
            # If validation fails, AdapterError is raised with full details logged by media_store
            video_path = self.media_store.get_local_file_path(media_ref)

            body = self._prepare_metadata(task)

            media = MediaFileUpload(
                str(video_path),
                chunksize=-1,
                resumable=True,
            )

            logger.debug(f"Uploading media file: {video_path}")
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
            logger.info(f"Media uploaded successfully: video_id={video_id}")

            result_status = TaskStatus.SCHEDULED
            publish_at = task.publish_at

            return PublishResult(
                success=True,
                media_id=video_id,
                status=result_status,
                publish_at=publish_at,
                upload_time=datetime.utcnow(),
            )

        except HttpError as e:
            return self._handle_http_error(e, task)

        except FileNotFoundError as e:
            error_msg = f"Media file not found: {video_path}"
            logger.error(f"Upload failed: {error_msg}", exc_info=True)
            raise PermanentError(error_msg) from e

        except Exception as e:
            error_msg = f"Unexpected error during upload: {str(e)}"
            logger.exception(f"Upload failed: {error_msg}")
            raise MediaUploaderError(error_msg) from e

    def upload_thumbnail(self, video_id: str, thumbnail_ref: str) -> bool:
        """
        Upload custom thumbnail for a media.

        Args:
            video_id: YouTube video ID.
            thumbnail_ref: Thumbnail reference (resolved to local path internally via MediaStore).

        Returns:
            True if thumbnail uploaded successfully.
        """
        try:
            logger.info(f"Uploading thumbnail for video {video_id}")

            # Request local file path from media_store
            thumbnail_path = self.media_store.get_local_file_path(thumbnail_ref)

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

    def _prepare_metadata(self, task: Task) -> dict:
        """
        Prepare media metadata for YouTube API.

        Args:
            task: Media task.

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

        if task.publish_at:
            publish_at_str = task.publish_at.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            status["publishAt"] = publish_at_str

            if task.privacy_status != PrivacyStatus.PRIVATE:
                logger.debug(
                    f"Scheduled media privacy set to private (will change to "
                    f"{task.privacy_status.value} at {publish_at_str})"
                )

        body = {
            "snippet": snippet,
            "status": status,
        }

        logger.debug(f"Media metadata prepared: {body}")
        return body

    def _handle_http_error(self, error: HttpError, task: Task) -> PublishResult:
        """
        Handle HTTP errors from YouTube API.

        Args:
            error: HTTP error from API.
            task: Media task being processed.

        Returns:
            PublishResult with error information.

        Raises:
            RetryableError: For temporary errors.
            PermanentError: For permanent errors.
        """
        status_code = error.resp.status
        error_content = error.content.decode("utf-8") if error.content else ""

        logger.error(f"YouTube API error {status_code}: {error_content}")

        if status_code in self.RETRYABLE_STATUS_CODES:
            error_msg = f"Temporary error {status_code}: {error_content}"
            raise RetryableError(error_msg)

        permanent_errors = {
            400: "Invalid request (check media format, metadata)",
            401: "Authentication failed (check credentials)",
            403: "Forbidden (check quota, permissions)",
            404: "Resource not found",
        }

        if status_code in permanent_errors:
            error_msg = f"{permanent_errors[status_code]}: {error_content}"
            raise PermanentError(error_msg)

        error_msg = f"HTTP error {status_code}: {error_content}"
        raise PermanentError(error_msg)
