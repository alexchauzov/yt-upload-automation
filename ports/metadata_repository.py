"""Interface for metadata repository (e.g., Google Sheets)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from domain.models import Task


class MetadataRepository(ABC):
    """
    Repository for reading and updating task metadata.

    Implementation examples: Google Sheets, Database, JSON files.
    """

    @abstractmethod
    def get_ready_tasks(self) -> List[Task]:
        """
        Fetch all tasks with READY status (or configurable status).

        Returns:
            List of Task objects ready for publishing.

        Raises:
            MetadataRepositoryError: If fetching fails.
        """
        pass

    @abstractmethod
    def update_task_status(
        self,
        task: Task,
        status: str,
        youtube_video_id: str | None = None,
        error_message: str | None = None,
        video_file_path: str | None = None,
    ) -> None:
        """
        Update task status and related fields in the repository.

        Args:
            task: The task to update.
            status: New status value (domain status, e.g., IN_PROGRESS).
            youtube_video_id: Platform media ID if uploaded (parameter name kept for backward compatibility).
            error_message: Error message if failed.
            video_file_path: Updated media reference (e.g., after file transition to new stage).

        Raises:
            MetadataRepositoryError: If update fails.
        """
        pass

    @abstractmethod
    def increment_attempts(self, task: Task) -> None:
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
