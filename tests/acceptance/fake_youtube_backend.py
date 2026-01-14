"""Fake YouTube backend for acceptance tests."""
from datetime import datetime
from enum import Enum
from pathlib import Path

from domain.models import PublishResult, TaskStatus, VideoTask
from ports.video_backend import PermanentError, RetryableError, VideoBackend


class FakeYouTubeMode(Enum):
    """Modes for controlling FakeYouTubeBackend behavior."""

    SUCCESS_PUBLIC = "success_public"
    SUCCESS_SCHEDULED = "success_scheduled"
    FAIL_RETRYABLE = "fail_retryable"
    FAIL_PERMANENT = "fail_permanent"


class FakeYouTubeBackend(VideoBackend):
    """
    Fake YouTube backend for acceptance tests.

    Behavior controlled by mode parameter.
    Always validates that video file exists and is readable.
    """

    def __init__(self, mode: FakeYouTubeMode = FakeYouTubeMode.SUCCESS_PUBLIC):
        """
        Initialize fake backend.

        Args:
            mode: Behavior mode (success or failure scenarios).
        """
        self.mode = mode
        self.uploaded_videos = {}
        self.call_count = 0

    def publish_video(self, task: VideoTask, video_path: Path) -> PublishResult:
        """
        Simulate video upload with configurable behavior.

        Always validates file exists and is readable before processing.

        Args:
            task: Video task with metadata.
            video_path: Absolute path to video file.

        Returns:
            PublishResult with outcome based on mode.

        Raises:
            PermanentError: If file not found/readable, or in FAIL_PERMANENT mode.
            RetryableError: In FAIL_RETRYABLE mode.
        """
        self.call_count += 1

        if not video_path.exists():
            raise PermanentError(f"Video file not found: {video_path}")

        if not video_path.is_file():
            raise PermanentError(f"Path is not a file: {video_path}")

        try:
            with open(video_path, 'rb') as f:
                f.read(100)
        except Exception as e:
            raise PermanentError(f"Cannot read video file: {e}")

        if self.mode == FakeYouTubeMode.FAIL_RETRYABLE:
            raise RetryableError("Rate limit exceeded (fake)")

        if self.mode == FakeYouTubeMode.FAIL_PERMANENT:
            raise PermanentError("Invalid video format (fake)")

        video_id = f"fake_{task.task_id}_{self.call_count}"
        self.uploaded_videos[video_id] = (task, video_path)

        return PublishResult(
            success=True,
            video_id=video_id,
            status=TaskStatus.SCHEDULED,
            publish_at=task.publish_at,
            upload_time=datetime.utcnow(),
        )

    def upload_thumbnail(self, video_id: str, thumbnail_path: Path) -> bool:
        """
        Simulate thumbnail upload (always succeeds).

        Args:
            video_id: YouTube video ID.
            thumbnail_path: Path to thumbnail image.

        Returns:
            True (always succeeds in fake backend).
        """
        return True
