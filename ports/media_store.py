"""Unified interface for media storage and lifecycle management."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from domain.models import MediaStage


class MediaStore(ABC):
    """
    Unified interface for media storage operations and lifecycle management.

    Combines read-only validation operations with workflow stage transitions.
    Single adapter per storage type (local filesystem, S3, GCS, Google Photos, etc).
    """

    @abstractmethod
    def exists(self, ref: str) -> bool:
        """
        Check if media reference exists.

        Args:
            ref: Media reference to check.

        Returns:
            True if media exists, False otherwise.
        """
        pass

    @abstractmethod
    def get_path(self, ref: str) -> Path:
        """
        Resolve media reference to local Path (if needed by adapter).

        For local files: returns Path directly.
        For remote sources: may download and return local Path.

        Args:
            ref: Media reference (path, URL, S3 key, blob ID, etc.).

        Returns:
            Absolute Path object.

        Raises:
            AdapterError: If reference is invalid or media doesn't exist.
        """
        pass

    @abstractmethod
    def get_local_file_path(self, ref: str) -> Path:
        """
        Get local file path for media reference.

        This method is called by adapters that need a local file path (e.g., YouTube uploader).
        The adapter explicitly requests a local file path, and the media store:
        - Validates that the reference exists and is accessible
        - Returns the local file path (may download from remote storage if needed)
        - If validation fails, raises AdapterError with details

        Args:
            ref: Media reference to resolve.

        Returns:
            Absolute Path to local file.

        Raises:
            AdapterError: If reference is invalid, media doesn't exist, or can't be accessed.
                         The error should be logged by the adapter with full details.
        """
        pass

    @abstractmethod
    def mark_in_progress(self, ref: str) -> str:
        """
        Mark media reference as IN_PROGRESS.

        This is a signal from domain to mark media as being processed.
        The adapter handles this according to its internal rules:
        - Local filesystem: may move file from watch/ to in_progress/
        - Database: may update status column
        - Cloud storage: may update metadata

        Args:
            ref: Media reference to mark as IN_PROGRESS.

        Returns:
            Updated media reference (may be the same or different after transition).

        Raises:
            AdapterError: If marking fails (media not found, permission denied, etc).
        """
        pass

    @abstractmethod
    def get_size(self, ref: str) -> int:
        """
        Get media size in bytes.

        Args:
            ref: Media reference.

        Returns:
            Media size in bytes.

        Raises:
            AdapterError: If media doesn't exist or can't be accessed.
        """
        pass

    @abstractmethod
    def transition(self, media_ref: str, to_stage: MediaStage) -> str:
        """
        Transition media to a new workflow stage.

        Args:
            media_ref: Current media reference (implementation-specific identifier).
            to_stage: Target workflow stage.

        Returns:
            New media reference after transition.

        Raises:
            AdapterError: If transition fails (media not found, permission denied, etc).
        """
        pass
