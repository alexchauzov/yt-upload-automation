"""Domain service for media publishing orchestration."""
import logging
from typing import Optional

from domain.models import PublishResult, Task, TaskStatus
from ports.adapter_error import AdapterError
from ports.media_store import MediaStore
from ports.media_uploader import MediaUploader, MediaUploaderError
from ports.metadata_repository import MetadataRepository, MetadataRepositoryError

logger = logging.getLogger(__name__)


class PublishService:
    """
    Orchestrates media publishing workflow.

    Responsibilities:
    - Fetch ready tasks from metadata repository
    - Send signals to mark tasks and media as IN_PROGRESS
    - Coordinate media upload to platforms
    - Update task status and metadata
    - Handle errors with proper logging and status updates
    - Ensure idempotency (skip already uploaded media)
    """

    def __init__(
        self,
        metadata_repo: MetadataRepository,
        media_store: MediaStore,
        media_uploader: Optional[MediaUploader],
        max_retries: int = 1,
        dry_run: bool = False,
    ):
        """
        Initialize publish service.

        Args:
            metadata_repo: Repository for task metadata.
            media_store: Store for accessing and managing media files.
            media_uploader: Uploader for publishing media to platforms.
            max_retries: Maximum retry attempts (default: 1, no retries).
            dry_run: If True, validate but don't actually upload.
        """
        self.metadata_repo = metadata_repo
        self.media_store = media_store
        self.media_uploader = media_uploader
        self.max_retries = max_retries
        self.dry_run = dry_run

    def publish_all_ready_tasks(self) -> dict:
        """
        Process all tasks with READY status.

        Returns:
            Summary dict with counts: processed, succeeded, failed, skipped.
        """
        logger.info("Starting publish workflow")
        tasks = self.metadata_repo.get_ready_tasks()
        logger.info(f"Found {len(tasks)} tasks with READY status")

        stats = {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
        }

        for task in tasks:
            try:
                result = self.publish_task(task)
                stats["processed"] += 1

                if result == "skipped":
                    stats["skipped"] += 1
                elif result == "success":
                    stats["succeeded"] += 1
                else:
                    stats["failed"] += 1

            except Exception as e:
                logger.exception(f"Unexpected error processing task {task.task_id}: {e}")
                stats["processed"] += 1
                stats["failed"] += 1

        logger.info(
            f"Publish workflow completed: "
            f"processed={stats['processed']}, "
            f"succeeded={stats['succeeded']}, "
            f"failed={stats['failed']}, "
            f"skipped={stats['skipped']}"
        )

        return stats

    def publish_task(self, task: Task) -> str:
        """
        Publish a single media task.

        Workflow:
        1. Check idempotency (skip if already uploaded)
        2. Send signal to metadata_repo: task IN_PROGRESS
        3. Send signal to media_store: media_reference IN_PROGRESS
        4. Send task metadata + media_reference to media_uploader
        5. Update status based on upload result

        Args:
            task: Task to publish.

        Returns:
            Result status: "success", "failed", or "skipped".
        """
        logger.info(f"Processing task {task.task_id} (row {task.row_index})")

        # Idempotency: skip if already uploaded
        if task.platform_media_id:
            logger.info(
                f"Task {task.task_id} already has platform_media_id={task.platform_media_id}, skipping"
            )
            return "skipped"

        # Step 1: Send signal to metadata_repo - mark task as IN_PROGRESS
        try:
            self.metadata_repo.update_task_status(task, TaskStatus.IN_PROGRESS.value)
            logger.info(f"Task {task.task_id}: marked as IN_PROGRESS in metadata repository")
        except MetadataRepositoryError as e:
            error_msg = f"Failed to mark task as IN_PROGRESS in metadata repository: {str(e)}"
            logger.error(f"Task {task.task_id}: {error_msg}", exc_info=True)
            # Try to mark as failed, but don't fail if that also fails
            try:
                self._mark_failed(task, error_msg)
            except Exception:
                logger.error(f"Task {task.task_id}: failed to mark as FAILED, continuing to next task")
            return "failed"
        except Exception as e:
            error_msg = f"Unexpected error marking task as IN_PROGRESS: {str(e)}"
            logger.error(f"Task {task.task_id}: {error_msg}", exc_info=True)
            try:
                self._mark_failed(task, error_msg)
            except Exception:
                logger.error(f"Task {task.task_id}: failed to mark as FAILED, continuing to next task")
            return "failed"

        # Step 2: Send signal to media_store - mark media_reference as IN_PROGRESS
        try:
            updated_media_ref = self.media_store.mark_in_progress(task.media_reference)
            task.media_reference = updated_media_ref
            logger.info(
                f"Task {task.task_id}: media_reference {task.media_reference} marked as IN_PROGRESS"
            )
        except AdapterError as e:
            error_msg = f"Failed to mark media as IN_PROGRESS: {str(e)}"
            logger.error(f"Task {task.task_id}: {error_msg}", exc_info=True)
            self._mark_failed(task, error_msg)
            return "failed"

        # Dry run mode: validate only
        if self.dry_run or self.media_uploader is None:
            logger.info(f"Task {task.task_id}: DRY RUN mode - validation passed")
            try:
                self.metadata_repo.update_task_status(task, TaskStatus.DRY_RUN_OK.value)
            except Exception as e:
                logger.warning(f"Task {task.task_id}: failed to update status to DRY_RUN_OK: {e}")
            return "success"

        # Step 3: Send task metadata + media_reference to media_uploader
        # The uploader will request get_local_file_path from media_store, which validates the reference
        result = self._upload_media(task)

        if result.success:
            # Upload thumbnail if provided
            if task.thumbnail_reference:
                self._upload_thumbnail(task, result.media_id)

            # Update task with success status
            try:
                self.metadata_repo.update_task_status(
                    task,
                    status=TaskStatus.SCHEDULED.value,
                    youtube_video_id=result.media_id,
                )
                logger.info(
                    f"Task {task.task_id}: successfully published "
                    f"(media_id={result.media_id}, publish_at={result.publish_at})"
                )
            except Exception as e:
                logger.error(f"Task {task.task_id}: failed to update status to SCHEDULED: {e}", exc_info=True)
            return "success"
        else:
            # Mark as failed
            self._mark_failed(task, result.error_message or "Unknown error")
            return "failed"

    def _upload_media(self, task: Task) -> PublishResult:
        """
        Upload media to platform.

        The uploader will request get_local_file_path from media_store,
        which validates the media reference and returns the local path.

        Args:
            task: Media task.

        Returns:
            PublishResult with upload outcome.
        """
        try:
            logger.info(f"Task {task.task_id}: starting media upload")

            # Increment attempts counter
            try:
                self.metadata_repo.increment_attempts(task)
            except Exception as e:
                logger.warning(f"Task {task.task_id}: failed to increment attempts: {e}")

            # Attempt upload
            # The uploader will call media_store.get_local_file_path() internally
            # which validates the reference and returns the local path
            result = self.media_uploader.publish_media(task, task.media_reference)

            if result.success:
                logger.info(f"Task {task.task_id}: upload succeeded")
            else:
                logger.error(f"Task {task.task_id}: upload failed: {result.error_message}")

            return result

        except MediaUploaderError as e:
            # Uploader error - already logged by uploader
            error_msg = str(e)
            logger.error(f"Task {task.task_id}: upload error: {error_msg}")
            return PublishResult(
                success=False,
                error_message=error_msg,
            )

        except Exception as e:
            # Unexpected error
            error_msg = f"Unexpected error during upload: {str(e)}"
            logger.exception(f"Task {task.task_id}: {error_msg}")
            return PublishResult(
                success=False,
                error_message=error_msg,
            )

    def _upload_thumbnail(self, task: Task, media_id: str) -> None:
        """
        Upload thumbnail for a media (best effort).

        Args:
            task: Media task.
            media_id: Platform media ID (e.g., YouTube video ID).
        """
        if not task.thumbnail_reference:
            return

        try:
            logger.info(f"Task {task.task_id}: uploading thumbnail from {task.thumbnail_reference}")

            success = self.media_uploader.upload_thumbnail(media_id, task.thumbnail_reference)

            if success:
                logger.info(f"Task {task.task_id}: thumbnail uploaded successfully")
            else:
                logger.warning(f"Task {task.task_id}: thumbnail upload failed")

        except Exception as e:
            # Don't fail the whole task if thumbnail upload fails
            logger.warning(f"Task {task.task_id}: thumbnail upload error: {e}", exc_info=True)

    def _mark_failed(self, task: Task, error_message: str) -> None:
        """
        Mark task as failed with error message.

        Args:
            task: Task.
            error_message: Error description (brief, detailed info should be in logs).
        """
        try:
            self.metadata_repo.update_task_status(
                task,
                status=TaskStatus.FAILED.value,
                error_message=error_message,
            )
            logger.error(f"Task {task.task_id}: marked as FAILED - {error_message}")
        except Exception as e:
            # If we can't mark as failed, just log it and continue
            logger.error(f"Task {task.task_id}: failed to update status to FAILED: {e}", exc_info=True)
