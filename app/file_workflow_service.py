"""Manages video file lifecycle through workflow stages."""
from pathlib import Path

from domain.models import VideoTask


class FileWorkflowService:
    """
    Manages video file lifecycle through workflow stages.

    Stub implementation - methods are placeholders.
    """

    def __init__(
        self,
        watch_dir: Path,
        in_progress_dir: Path,
        uploaded_dir: Path,
        failed_dir: Path,
    ):
        """
        Initialize file workflow service.

        Args:
            watch_dir: Directory for unwatched video files.
            in_progress_dir: Directory for files being processed.
            uploaded_dir: Directory for successfully uploaded files.
            failed_dir: Directory for files that failed to upload.
        """
        self.watch_dir = watch_dir
        self.in_progress_dir = in_progress_dir
        self.uploaded_dir = uploaded_dir
        self.failed_dir = failed_dir

    def start_processing(self, task: VideoTask) -> None:
        """
        Move file from WATCH to IN_PROGRESS, update task path.

        Args:
            task: Video task with video_file_path pointing to WATCH directory.

        Raises:
            NotImplementedError: File workflow not implemented yet.
        """
        raise NotImplementedError("File workflow not implemented")

    def complete_processing(
        self, task: VideoTask, success: bool, error: str | None = None
    ) -> None:
        """
        Move file based on outcome and update task.

        Args:
            task: Video task with video_file_path pointing to IN_PROGRESS directory.
            success: True to move to UPLOADED, False to move to FAILED.
            error: Error message to record if success=False.

        Raises:
            NotImplementedError: File workflow not implemented yet.

        Expected behavior:
        - success=True -> move file to UPLOADED directory
        - success=False -> move file to FAILED directory
        - Update task.video_file_path to new location
        - Update task.status (SCHEDULED for success, FAILED for failure)
        - Record error_message if provided
        """
        raise NotImplementedError("File workflow not implemented")
