"""Fake YouTube media uploader for acceptance tests."""
from datetime import datetime
from enum import Enum
from pathlib import Path

from domain.models import PublishResult, TaskStatus, Task
from ports.media_uploader import MediaUploader, PermanentError


class FakeYouTubeMode(Enum):
    """Modes for controlling FakeYouTubeUploader behavior."""

    SUCCESS_PUBLIC = "success_public"
    SUCCESS_SCHEDULED = "success_scheduled"
    FAIL = "fail"


class FakeYouTubeUploader(MediaUploader):
    """
    Fake YouTube media uploader for acceptance tests.

    Behavior controlled by mode parameter.
    Validates media reference format.
    """

    def __init__(self, mode: FakeYouTubeMode = FakeYouTubeMode.SUCCESS_PUBLIC):
        """
        Initialize fake uploader.

        Args:
            mode: Behavior mode (success or failure scenarios).
        """
        self.mode = mode
        self.uploaded_videos = {}
        self.call_count = 0

    def publish_media(self, task: Task, media_ref: str) -> PublishResult:
        """
        Simulate media upload with configurable behavior.

        Only accepts .mp4 and .mov files; rejects others with format error.

        Args:
            task: Media task with metadata.
            media_ref: Media reference (path, URL, etc.).

        Returns:
            PublishResult with outcome based on mode.

        Raises:
            PermanentError: If unsupported format or in FAIL mode.
        """
        self.call_count += 1

        media_path = Path(media_ref)
        allowed_extensions = {'.mp4', '.mov'}
        if media_path.suffix.lower() not in allowed_extensions:
            raise PermanentError("Incorrect media format")

        if self.mode == FakeYouTubeMode.FAIL:
            raise PermanentError("Upload failed (fake): Invalid media format")

        media_id = f"fake_{task.task_id}_{self.call_count}"
        self.uploaded_videos[media_id] = (task, media_ref)

        return PublishResult(
            success=True,
            media_id=media_id,
            status=TaskStatus.SCHEDULED,
            publish_at=task.publish_at,
            upload_time=datetime.utcnow(),
        )

    def upload_thumbnail(self, video_id: str, thumbnail_ref: str) -> bool:
        """
        Simulate thumbnail upload (always succeeds).

        Args:
            video_id: YouTube video ID.
            thumbnail_ref: Thumbnail reference (path, URL, etc.).

        Returns:
            True (always succeeds in fake uploader).
        """
        return True
