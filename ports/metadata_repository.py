"""Interface for metadata repository (e.g., Google Sheets)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from domain.models import VideoTask


class MetadataRepository(ABC):
    """
    Repository for reading and updating video task metadata.

    Implementation examples: Google Sheets, Database, JSON files.
    """

    @abstractmethod
    def get_ready_tasks(self) -> List[VideoTask]:
        """
        Fetch all tasks with READY status (or configurable status).

        Returns:
            List of VideoTask objects ready for publishing.

        Raises:
            MetadataRepositoryError: If fetching fails.
        """
        pass

    @abstractmethod
    def update_task_status(
        self,
        task: VideoTask,
        status: str,
        youtube_video_id: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """
        Update task status and related fields in the repository.

        Args:
            task: The task to update.
            status: New status value.
            youtube_video_id: YouTube video ID if uploaded.
            error_message: Error message if failed.

        Raises:
            MetadataRepositoryError: If update fails.
        """
        pass

    @abstractmethod
    def increment_attempts(self, task: VideoTask) -> None:
        """
        Increment retry attempts counter for a task.

        Args:
            task: The task to update.

        Raises:
            MetadataRepositoryError: If update fails.
        """
        pass


class MetadataRepositoryError(Exception):
    """Base exception for metadata repository errors."""
    pass


class ValidationError(MetadataRepositoryError):
    """Raised when task data fails validation."""
    pass
