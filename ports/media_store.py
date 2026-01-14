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
