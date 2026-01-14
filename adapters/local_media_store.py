"""Local filesystem media store adapter."""
from pathlib import Path
from typing import Union

from domain.models import MediaStage
from ports.adapter_error import AdapterError
from ports.media_store import MediaStore


class LocalMediaStore(MediaStore):
    """
    Local filesystem implementation of MediaStore.

    Manages video file transitions between workflow stages using filesystem directories.
    Each MediaStage maps to a physical directory on the filesystem.
    """

    def __init__(self, in_progress_dir: Union[Path, str], uploaded_dir: Union[Path, str]):
        """
        Initialize local media store with stage directories.

        Args:
            in_progress_dir: Directory for IN_PROGRESS stage files.
            uploaded_dir: Directory for UPLOADED stage files.

        Stage directories are created if they don't exist.
        """
        self.stage_dirs = {
            MediaStage.IN_PROGRESS: Path(in_progress_dir),
            MediaStage.UPLOADED: Path(uploaded_dir),
        }

        for stage_dir in self.stage_dirs.values():
            stage_dir.mkdir(parents=True, exist_ok=True)

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
                - FILE_NOT_FOUND: Source file doesn't exist
                - FILE_EXISTS: Destination file already exists
                - MOVE_FAILED: File move operation failed
        """
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
