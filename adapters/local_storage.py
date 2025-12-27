"""Local filesystem storage adapter."""
from __future__ import annotations

import logging
from pathlib import Path

from ports.storage import Storage, StorageError

logger = logging.getLogger(__name__)


class LocalFileStorage(Storage):
    """
    Local filesystem storage implementation.

    Handles file access and validation on the local filesystem.
    """

    def __init__(self, base_path: str | None = None):
        """
        Initialize local storage.

        Args:
            base_path: Optional base directory for relative paths.
                      If None, uses current working directory.
        """
        self.base_path = Path(base_path) if base_path else Path.cwd()
        logger.debug(f"LocalFileStorage initialized with base_path={self.base_path}")

    def exists(self, path: str) -> bool:
        """Check if file exists."""
        try:
            resolved_path = self._resolve_path(path)
            exists = resolved_path.exists() and resolved_path.is_file()
            logger.debug(f"File exists check: {path} -> {exists}")
            return exists
        except Exception as e:
            logger.warning(f"Error checking file existence for {path}: {e}")
            return False

    def get_path(self, path: str) -> Path:
        """
        Resolve and validate file path.

        Returns:
            Absolute Path object.

        Raises:
            StorageError: If path is invalid or file doesn't exist.
        """
        try:
            resolved_path = self._resolve_path(path)

            if not resolved_path.exists():
                raise StorageError(f"File does not exist: {resolved_path}")

            if not resolved_path.is_file():
                raise StorageError(f"Path is not a file: {resolved_path}")

            logger.debug(f"Resolved path: {path} -> {resolved_path}")
            return resolved_path

        except StorageError:
            raise
        except Exception as e:
            raise StorageError(f"Invalid path {path}: {e}") from e

    def get_size(self, path: str) -> int:
        """
        Get file size in bytes.

        Raises:
            StorageError: If file doesn't exist or can't be accessed.
        """
        try:
            resolved_path = self.get_path(path)
            size = resolved_path.stat().st_size
            logger.debug(f"File size: {path} -> {size} bytes")
            return size
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(f"Cannot get size for {path}: {e}") from e

    def _resolve_path(self, path: str) -> Path:
        """
        Resolve path to absolute Path object.

        Args:
            path: Relative or absolute file path.

        Returns:
            Absolute Path object.
        """
        p = Path(path)

        if p.is_absolute():
            return p
        else:
            return (self.base_path / p).resolve()
