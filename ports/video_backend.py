"""Interface for video publishing backend (e.g., YouTube API)."""
from abc import ABC, abstractmethod

from domain.models import PublishResult, VideoTask


class VideoBackend(ABC):
    """
    Backend interface for video publishing operations.

    Implementation examples: YouTube API, Vimeo API, Local storage.
    """

    @abstractmethod
    def publish_video(self, task: VideoTask, media_ref: str) -> PublishResult:
        """
        Upload and schedule video for publishing.

        Args:
            task: Video task with metadata.
            media_ref: Abstract media reference (e.g., file path, S3 key, URL).

        Returns:
            PublishResult with upload status and video ID.

        Raises:
            VideoBackendError: If upload fails.
            RetryableError: For temporary errors (429, 5xx, network).
        """
        pass

    @abstractmethod
    def upload_thumbnail(self, video_id: str, thumbnail_ref: str) -> bool:
        """
        Upload custom thumbnail for a video.

        Args:
            video_id: YouTube video ID.
            thumbnail_ref: Abstract thumbnail reference (e.g., file path, S3 key, URL).

        Returns:
            True if thumbnail uploaded successfully.

        Raises:
            VideoBackendError: If upload fails.
        """
        pass


class VideoBackendError(Exception):
    """Base exception for video backend errors."""
    pass


class RetryableError(VideoBackendError):
    """
    Temporary error that should trigger a retry.

    Examples: Rate limiting (429), server errors (5xx), network timeouts.
    """
    pass


class PermanentError(VideoBackendError):
    """
    Permanent error that should not be retried.

    Examples: Invalid credentials, quota exceeded, invalid video format.
    """
    pass
