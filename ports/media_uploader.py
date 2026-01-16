"""Interface for media uploading (e.g., YouTube, Instagram, etc.)."""
from abc import ABC, abstractmethod

from domain.models import PublishResult, Task


class MediaUploader(ABC):
    """
    Interface for media uploading operations.

    Implementation examples: YouTube API, Instagram API, Vimeo API, etc.
    """

    @abstractmethod
    def publish_media(self, task: Task, media_ref: str) -> PublishResult:
        """
        Upload media to platform.

        Args:
            task: Media task with metadata (title, description, tags, etc.).
            media_ref: Media reference (path, URL, S3 key, blob ID, etc.).
                     Adapter decides how to handle it based on its needs.

        Returns:
            PublishResult with upload status and media ID.

        Raises:
            MediaUploaderError: If upload fails.
            RetryableError: For temporary errors (429, 5xx, network).
        """
        pass

    @abstractmethod
    def upload_thumbnail(self, video_id: str, thumbnail_ref: str) -> bool:
        """
        Upload custom thumbnail for a media.

        Args:
            video_id: Platform media ID (e.g., YouTube video ID).
            thumbnail_ref: Thumbnail reference (path, URL, etc.).
                         Adapter decides how to handle it.

        Returns:
            True if thumbnail uploaded successfully.

        Raises:
            MediaUploaderError: If upload fails.
        """
        pass


class MediaUploaderError(Exception):
    """Base exception for media uploader errors."""
    pass


class RetryableError(MediaUploaderError):
    """
    Temporary error that should trigger a retry.

    Examples: Rate limiting (429), server errors (5xx), network timeouts.
    """
    pass


class PermanentError(MediaUploaderError):
    """
    Permanent error that should not be retried.

    Examples: Invalid credentials, quota exceeded, invalid media format.
    """
    pass
