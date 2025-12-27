"""Interface for file storage operations."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class Storage(ABC):
    """
    Storage interface for accessing video and thumbnail files.

    Implementation examples: Local filesystem, Cloud storage (S3, GCS).
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
            StorageError: If path is invalid or file doesn't exist.
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
            StorageError: If file doesn't exist or can't be accessed.
        """
        pass


class StorageError(Exception):
    """Base exception for storage errors."""
    pass
