"""Local filesystem media file store adapter."""
from pathlib import Path
from typing import Union

from domain.models import MediaStage
from ports.adapter_error import AdapterError
from ports.media_file_store import MediaFileStore


class LocalMediaFileStore(MediaFileStore):
    """
    Local filesystem implementation of MediaFileStore.

    Unified adapter handling both validation and lifecycle management.
    Manages video file storage and transitions between workflow stages.
    """

    def __init__(
        self,
        base_path: Union[str, Path, None] = None,
        in_progress_dir: Union[str, Path, None] = None,
        uploaded_dir: Union[str, Path, None] = None,
    ):
        """
        Initialize local media file store.

        Args:
            base_path: Optional base directory for resolving relative paths.
                      If None, uses current working directory.
            in_progress_dir: Directory for IN_PROGRESS stage files.
                            Required for transition operations.
            uploaded_dir: Directory for UPLOADED stage files.
                         Required for transition operations.

        Stage directories are created if they don't exist.
        """
        self.base_path = Path(base_path) if base_path else Path.cwd()

        self.stage_dirs = {}
        if in_progress_dir:
            self.stage_dirs[MediaStage.IN_PROGRESS] = Path(in_progress_dir)
        if uploaded_dir:
            self.stage_dirs[MediaStage.UPLOADED] = Path(uploaded_dir)

        for stage_dir in self.stage_dirs.values():
            stage_dir.mkdir(parents=True, exist_ok=True)

    def exists(self, path: str) -> bool:
        """Check if file exists."""
        try:
            resolved_path = self._resolve_path(path)
            return resolved_path.exists() and resolved_path.is_file()
        except Exception:
            return False

    def get_path(self, path: str) -> Path:
        """
        Resolve and validate file path.

        Returns:
            Absolute Path object.

        Raises:
            AdapterError: If path is invalid or file doesn't exist.
        """
        try:
            resolved_path = self._resolve_path(path)

            if not resolved_path.exists():
                raise AdapterError(
                    code="FILE_NOT_FOUND",
                    message=f"File does not exist: {path}",
                    details={"path": str(resolved_path)}
                )

            if not resolved_path.is_file():
                raise AdapterError(
                    code="NOT_A_FILE",
                    message=f"Path is not a file: {path}",
                    details={"path": str(resolved_path)}
                )

            return resolved_path

        except AdapterError:
            raise
        except Exception as e:
            raise AdapterError(
                code="PATH_RESOLUTION_FAILED",
                message=f"Invalid path: {path}",
                details={"error": str(e)}
            ) from e

    def get_size(self, path: str) -> int:
        """
        Get file size in bytes.

        Raises:
            AdapterError: If file doesn't exist or can't be accessed.
        """
        try:
            resolved_path = self.get_path(path)
            return resolved_path.stat().st_size
        except AdapterError:
            raise
        except Exception as e:
            raise AdapterError(
                code="SIZE_READ_FAILED",
                message=f"Cannot get size for: {path}",
                details={"error": str(e)}
            ) from e

    def transition(self, media_ref: str, to_stage: MediaStage) -> str:
        """
        Transition media file to a new workflow stage.

        Moves file from current location to the directory mapped to target stage.

        Args:
            media_ref: Current file path (absolute or relative).
            to_stage: Target workflow stage.

        Returns:
            New file path after transition.

        Raises:
            AdapterError: If transition fails.
        """
        if to_stage not in self.stage_dirs:
            raise AdapterError(
                code="STAGE_NOT_CONFIGURED",
                message=f"Stage directory not configured: {to_stage.value}",
                details={"stage": to_stage.value}
            )

        source_path = Path(media_ref)

        if not source_path.exists():
            raise AdapterError(
                code="FILE_NOT_FOUND",
                message=f"Source file not found: {media_ref}",
                details={"source_path": str(source_path)}
            )

        if not source_path.is_file():
            raise AdapterError(
                code="NOT_A_FILE",
                message=f"Source path is not a file: {media_ref}",
                details={"source_path": str(source_path)}
            )

        dest_dir = self.stage_dirs[to_stage]
        dest_path = dest_dir / source_path.name

        if dest_path.exists():
            raise AdapterError(
                code="FILE_EXISTS",
                message=f"Destination file already exists: {dest_path.name}",
                details={
                    "source_path": str(source_path),
                    "dest_path": str(dest_path)
                }
            )

        try:
            source_path.rename(dest_path)
        except PermissionError as e:
            raise AdapterError(
                code="PERMISSION_DENIED",
                message=f"Permission denied moving file: {source_path.name}",
                details={
                    "source_path": str(source_path),
                    "dest_path": str(dest_path),
                    "error": str(e)
                }
            ) from e
        except Exception as e:
            raise AdapterError(
                code="MOVE_FAILED",
                message=f"Failed to move file: {source_path.name}",
                details={
                    "source_path": str(source_path),
                    "dest_path": str(dest_path),
                    "error": str(e)
                }
            ) from e

        return str(dest_path)

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
