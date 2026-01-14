"""Domain service for video publishing orchestration."""
import logging
from datetime import datetime
from typing import Optional

from ports.media_uploader import MediaUploader

from domain.models import MediaStage, PublishResult, TaskStatus, VideoTask
from ports.adapter_error import AdapterError
from ports.media_store import MediaStore
from ports.media_uploader import MediaUploader, MediaUploaderError, RetryableError
from ports.metadata_repository import MetadataRepository

logger = logging.getLogger(__name__)


class PublishService:
    """
    Orchestrates video publishing workflow.

    Responsibilities:
    - Fetch ready tasks from metadata repository
    - Validate media files exist
    - Upload media to platforms (e.g., YouTube)
    - Update task status and metadata
    - Handle retries for temporary failures
    - Ensure idempotency (skip already uploaded media)
    """

    def __init__(
        self,
        metadata_repo: MetadataRepository,
        media_store: MediaStore,
        media_uploader: Optional[MediaUploader],
        max_retries: int = 3,
        dry_run: bool = False,
    ):
        """
        Initialize publish service.

        Args:
            metadata_repo: Repository for task metadata.
            media_store: Store for accessing and managing media files.
            media_uploader: Uploader for publishing media to platforms.
            max_retries: Maximum retry attempts for retryable errors.
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

    def publish_task(self, task: VideoTask) -> str:
        """
        Publish a single video task.

        Args:
            task: Video task to publish.

        Returns:
            Result status: "success", "failed", or "skipped".
        """
        logger.info(f"Processing task {task.task_id} (row {task.row_index})")

        # Idempotency: skip if already uploaded
        if task.youtube_video_id:
            logger.info(
                f"Task {task.task_id} already has youtube_video_id={task.youtube_video_id}, skipping"
            )
            return "skipped"

        # Validate media file exists
        try:
            if not self.media_store.exists(task.video_file_path):
                error_msg = f"Media file not found: {task.video_file_path}"
                logger.error(f"Task {task.task_id}: {error_msg}")
                self._mark_failed(task, error_msg)
                return "failed"

            logger.debug(f"Task {task.task_id}: media file validated at {task.video_file_path}")

        except AdapterError as e:
            error_msg = f"Storage error: {str(e)}"
            logger.error(f"Task {task.task_id}: {error_msg}")
            self._mark_failed(task, error_msg)
            return "failed"

        # Transition media to IN_PROGRESS stage
        try:
            new_media_ref = self.media_store.transition(
                task.video_file_path, MediaStage.IN_PROGRESS
            )
            task.video_file_path = new_media_ref
            logger.info(
                f"Task {task.task_id}: media transitioned to IN_PROGRESS at {new_media_ref}"
            )
        except AdapterError as e:
            error_msg = f"Failed to transition media to IN_PROGRESS: {str(e)}"
            logger.error(f"Task {task.task_id}: {error_msg}")
            self._mark_failed(task, error_msg)
            return "failed"

        # Dry run mode: validate only
        if self.dry_run or self.media_uploader is None:
            logger.info(f"Task {task.task_id}: DRY RUN mode - validation passed")
            self.metadata_repo.update_task_status(task, TaskStatus.DRY_RUN_OK.value)
            return "success"

        # Update status to UPLOADING
        try:
            self.metadata_repo.update_task_status(task, TaskStatus.UPLOADING.value)
            logger.info(f"Task {task.task_id}: status updated to UPLOADING")
        except Exception as e:
            logger.warning(f"Task {task.task_id}: failed to update status to UPLOADING: {e}")

        # Attempt upload with retry logic
        result = self._upload_with_retry(task, new_media_ref)

        if result.success:
            # Upload thumbnail if provided
            if task.thumbnail_path:
                self._upload_thumbnail(task, result.video_id)

            # Update task with success status
            self.metadata_repo.update_task_status(
                task,
                status=TaskStatus.SCHEDULED.value,
                youtube_video_id=result.video_id,
            )
            logger.info(
                f"Task {task.task_id}: successfully published "
                f"(video_id={result.video_id}, publish_at={result.publish_at})"
            )
            return "success"
        else:
            # Mark as failed
            self._mark_failed(task, result.error_message or "Unknown error")
            return "failed"

    def _upload_with_retry(self, task: VideoTask, media_ref: str) -> PublishResult:
        """
        Upload media with retry logic for temporary failures.

        Args:
            task: Media task.
            media_ref: Media reference (path, URL, etc.).

        Returns:
            PublishResult with upload outcome.
        """
        last_error: Optional[str] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Task {task.task_id}: upload attempt {attempt}/{self.max_retries}")

                # Increment attempts counter
                self.metadata_repo.increment_attempts(task)

                # Attempt upload
                result = self.media_uploader.publish_media(task, media_ref)

                if result.success:
                    logger.info(f"Task {task.task_id}: upload succeeded on attempt {attempt}")
                    return result
                else:
                    last_error = result.error_message
                    logger.warning(
                        f"Task {task.task_id}: upload failed on attempt {attempt}: {last_error}"
                    )
                    # Don't retry if uploader returned unsuccessful result
                    break

            except RetryableError as e:
                last_error = str(e)
                logger.warning(
                    f"Task {task.task_id}: retryable error on attempt {attempt}: {last_error}"
                )

                if attempt < self.max_retries:
                    logger.info(f"Task {task.task_id}: will retry (attempt {attempt + 1})")
                    continue
                else:
                    logger.error(f"Task {task.task_id}: max retries reached")
                    break

            except MediaUploaderError as e:
                # Permanent error - don't retry
                last_error = str(e)
                logger.error(f"Task {task.task_id}: permanent error, not retrying: {last_error}")
                break

            except Exception as e:
                # Unexpected error - don't retry
                last_error = f"Unexpected error: {str(e)}"
                logger.exception(f"Task {task.task_id}: {last_error}")
                break

        # All attempts failed
        return PublishResult(
            success=False,
            error_message=last_error or "Upload failed after all retry attempts",
        )

    def _upload_thumbnail(self, task: VideoTask, video_id: str) -> None:
        """
        Upload thumbnail for a media (best effort).

        Args:
            task: Media task.
            video_id: Platform media ID (e.g., YouTube video ID).
        """
        try:
            if not self.media_store.exists(task.thumbnail_path):
                logger.warning(
                    f"Task {task.task_id}: thumbnail file not found: {task.thumbnail_path}"
                )
                return

            logger.info(f"Task {task.task_id}: uploading thumbnail from {task.thumbnail_path}")

            success = self.media_uploader.upload_thumbnail(video_id, task.thumbnail_path)

            if success:
                logger.info(f"Task {task.task_id}: thumbnail uploaded successfully")
            else:
                logger.warning(f"Task {task.task_id}: thumbnail upload failed")

        except Exception as e:
            # Don't fail the whole task if thumbnail upload fails
            logger.warning(f"Task {task.task_id}: thumbnail upload error: {e}")

    def _mark_failed(self, task: VideoTask, error_message: str) -> None:
        """
        Mark task as failed with error message.

        Args:
            task: Video task.
            error_message: Error description.
        """
        try:
            self.metadata_repo.update_task_status(
                task,
                status=TaskStatus.FAILED.value,
                error_message=error_message,
            )
            logger.error(f"Task {task.task_id}: marked as FAILED - {error_message}")
        except Exception as e:
            logger.exception(f"Task {task.task_id}: failed to update status to FAILED: {e}")
