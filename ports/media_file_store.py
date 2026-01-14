"""Unified interface for media file storage and lifecycle management."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from domain.models import MediaStage


class MediaFileStore(ABC):
    """
    Unified interface for media file storage operations and lifecycle management.

    Combines read-only validation operations with workflow stage transitions.
    Single adapter per storage type (local filesystem, S3, GCS, etc).
    """

    @abstractmethod
    def exists(self, path: str) -> bool:
        """
        Check if file exists.

        Args:
            path: File path to check.

        Returns:
            True if file exists, False otherwise.
        """
        pass

    @abstractmethod
    def get_path(self, path: str) -> Path:
        """
        Resolve and validate file path.

        Args:
            path: Relative or absolute file path.

        Returns:
            Absolute Path object.

        Raises:
            AdapterError: If path is invalid or file doesn't exist.
        """
        pass

    @abstractmethod
    def get_size(self, path: str) -> int:
        """
        Get file size in bytes.

        Args:
            path: File path.

        Returns:
            File size in bytes.

        Raises:
            AdapterError: If file doesn't exist or can't be accessed.
        """
        pass

    @abstractmethod
    def transition(self, media_ref: str, to_stage: MediaStage) -> str:
        """
        Transition media file to a new workflow stage.

        Args:
            media_ref: Current media reference (implementation-specific identifier).
            to_stage: Target workflow stage.

        Returns:
            New media reference after transition.

        Raises:
            AdapterError: If transition fails (file not found, permission denied, etc).
        """
        pass
