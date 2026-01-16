"""Local filesystem media store adapter."""
from pathlib import Path
from typing import Union

from domain.models import MediaStage
from ports.adapter_error import AdapterError
from ports.media_store import MediaStore


class LocalMediaStore(MediaStore):
    """
    Local filesystem implementation of MediaStore.

    Unified adapter handling both validation and lifecycle management.
    Manages media file storage and transitions between workflow stages.
    """

    def __init__(
        self,
        base_path: Union[str, Path, None] = None,
        in_progress_dir: Union[str, Path, None] = None,
        uploaded_dir: Union[str, Path, None] = None,
    ):
        """
        Initialize local media store.

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

    def exists(self, ref: str) -> bool:
        """Check if media reference exists."""
        try:
            resolved_path = self._resolve_path(ref)
            return resolved_path.exists() and resolved_path.is_file()
        except Exception:
            return False

    def get_path(self, ref: str) -> Path:
        """
        Resolve and validate media reference to local Path.

        Returns:
            Absolute Path object.

        Raises:
            AdapterError: If reference is invalid or media doesn't exist.
        """
        try:
            resolved_path = self._resolve_path(ref)

            if not resolved_path.exists():
                raise AdapterError(
                    code="FILE_NOT_FOUND",
                    message=f"Media does not exist: {ref}",
                    details={"path": str(resolved_path)}
                )

            if not resolved_path.is_file():
                raise AdapterError(
                    code="NOT_A_FILE",
                    message=f"Path is not a file: {ref}",
                    details={"path": str(resolved_path)}
                )

            return resolved_path

        except AdapterError:
            raise
        except Exception as e:
            raise AdapterError(
                code="PATH_RESOLUTION_FAILED",
                message=f"Invalid media reference: {ref}",
                details={"error": str(e)}
            ) from e

    def get_local_file_path(self, ref: str) -> Path:
        """
        Get local file path for media reference.

        Validates that the reference exists and is accessible, then returns the local path.
        This method is called by adapters that need a local file path.

        Returns:
            Absolute Path to local file.

        Raises:
            AdapterError: If reference is invalid, media doesn't exist, or can't be accessed.
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            resolved_path = self._resolve_path(ref)

            if not resolved_path.exists():
                error = AdapterError(
                    code="FILE_NOT_FOUND",
                    message=f"Media does not exist: {ref}",
                    details={"path": str(resolved_path)}
                )
                logger.error(f"Failed to get local file path: {error}")
                raise error

            if not resolved_path.is_file():
                error = AdapterError(
                    code="NOT_A_FILE",
                    message=f"Path is not a file: {ref}",
                    details={"path": str(resolved_path)}
                )
                logger.error(f"Failed to get local file path: {error}")
                raise error

            logger.debug(f"Resolved media reference {ref} to local path: {resolved_path}")
            return resolved_path

        except AdapterError:
            raise
        except Exception as e:
            error = AdapterError(
                code="PATH_RESOLUTION_FAILED",
                message=f"Invalid media reference: {ref}",
                details={"error": str(e)}
            )
            logger.error(f"Failed to get local file path: {error}", exc_info=True)
            raise error from e

    def mark_in_progress(self, ref: str) -> str:
        """
        Mark media reference as IN_PROGRESS.

        Moves file to IN_PROGRESS directory if configured.
        Returns updated media reference (new path after move, or same if no move needed).

        Returns:
            Updated media reference.

        Raises:
            AdapterError: If marking fails.
        """
        import logging
        logger = logging.getLogger(__name__)

        if MediaStage.IN_PROGRESS not in self.stage_dirs:
            # If no IN_PROGRESS directory configured, just return the same reference
            logger.debug(f"No IN_PROGRESS directory configured, keeping reference: {ref}")
            return ref

        try:
            # Use transition method to move file
            new_ref = self.transition(ref, MediaStage.IN_PROGRESS)
            logger.info(f"Media reference {ref} marked as IN_PROGRESS, new reference: {new_ref}")
            return new_ref
        except AdapterError as e:
            logger.error(f"Failed to mark media {ref} as IN_PROGRESS: {e}", exc_info=True)
            raise

    def get_size(self, ref: str) -> int:
        """
        Get media size in bytes.

        Raises:
            AdapterError: If media doesn't exist or can't be accessed.
        """
        try:
            resolved_path = self.get_path(ref)
            return resolved_path.stat().st_size
        except AdapterError:
            raise
        except Exception as e:
            raise AdapterError(
                code="SIZE_READ_FAILED",
                message=f"Cannot get size for: {ref}",
                details={"error": str(e)}
            ) from e

    def transition(self, media_ref: str, to_stage: MediaStage) -> str:
        """
        Transition media to a new workflow stage.

        Moves file from current location to the directory mapped to target stage.

        Args:
            media_ref: Current media reference (absolute or relative file path).
            to_stage: Target workflow stage.

        Returns:
            New media reference after transition.

        Raises:
            AdapterError: If transition fails.
        """
        import logging
        logger = logging.getLogger(__name__)

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
                message=f"Source media not found: {media_ref}",
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

        # If file is already in target directory, no need to move
        if source_path.parent.resolve() == dest_dir.resolve():
            logger.debug(f"Media {source_path.name} already in {to_stage.value} directory, skipping move")
            return str(source_path)

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

    def _resolve_path(self, ref: str) -> Path:
        """
        Resolve media reference to absolute Path object.

        Args:
            ref: Relative or absolute file path.

        Returns:
            Absolute Path object.
        """
        p = Path(ref)

        if p.is_absolute():
            return p
        else:
            return (self.base_path / p).resolve()
