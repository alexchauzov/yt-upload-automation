"""Unit tests for PublishService."""
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, MagicMock, call

from domain.models import Task, TaskStatus, PrivacyStatus, PublishResult
from domain.services import PublishService
from ports.adapter_error import AdapterError
from ports.media_store import MediaStore
from ports.media_uploader import MediaUploader, RetryableError, PermanentError
from ports.metadata_repository import MetadataRepository


@pytest.fixture
def mock_metadata_repo():
    """Mock metadata repository."""
    return Mock(spec=MetadataRepository)


@pytest.fixture
def mock_media_store():
    """Mock media store."""
    mock = Mock(spec=MediaStore)
    # Default mark_in_progress behavior: return same path with /in_progress/ prefix
    mock.mark_in_progress.side_effect = lambda ref: f"/in_progress{ref}"
    # Default transition behavior for UPLOADED stage
    mock.transition.side_effect = lambda ref, stage: f"/uploaded{ref.replace('/in_progress', '')}"
    return mock


@pytest.fixture
def mock_media_uploader():
    """Mock media uploader."""
    return Mock(spec=MediaUploader)


@pytest.fixture
def sample_task():
    """Sample video task."""
    return Task(
        task_id="test_001",
        row_index=2,
        media_reference="/videos/test.mp4",
        title="Test Video",
        description="Test description",
        tags=["test", "demo"],
        status=TaskStatus.READY,
    )


@pytest.mark.unit
class TestPublishServiceHappyPath:
    """Test successful publishing scenarios."""

    def test_successful_publish(
        self, mock_metadata_repo, mock_media_store, mock_media_uploader, sample_task
    ):
        """Test successful media publishing."""
        # Arrange
        mock_metadata_repo.get_ready_tasks.return_value = [sample_task]

        mock_media_uploader.publish_media.return_value = PublishResult(
            success=True,
            media_id="abc123",
            status=TaskStatus.SCHEDULED,
            publish_at=None,
        )

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_store=mock_media_store,
            media_uploader=mock_media_uploader,
        )

        # Act
        stats = service.publish_all_ready_tasks()

        # Assert
        assert stats["processed"] == 1
        assert stats["succeeded"] == 1
        assert stats["failed"] == 0
        assert stats["skipped"] == 0

        # Verify interactions
        mock_metadata_repo.get_ready_tasks.assert_called_once()
        mock_media_uploader.publish_media.assert_called_once()
        mock_metadata_repo.increment_attempts.assert_called_once_with(sample_task)

    def test_successful_publish_with_thumbnail(
        self, mock_metadata_repo, mock_media_store, mock_media_uploader, sample_task
    ):
        """Test publishing with thumbnail upload."""
        # Arrange
        sample_task.thumbnail_reference = "/thumbnails/test.jpg"

        mock_metadata_repo.get_ready_tasks.return_value = [sample_task]

        mock_media_uploader.publish_media.return_value = PublishResult(
            success=True,
            media_id="abc123",
            status=TaskStatus.SCHEDULED,
        )
        mock_media_uploader.upload_thumbnail.return_value = True

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_store=mock_media_store,
            media_uploader=mock_media_uploader,
        )

        # Act
        stats = service.publish_all_ready_tasks()

        # Assert
        assert stats["succeeded"] == 1
        mock_media_uploader.upload_thumbnail.assert_called_once_with(
            "abc123", "/thumbnails/test.jpg"
        )


@pytest.mark.unit
class TestPublishServiceIdempotency:
    """Test idempotency - skip already uploaded tasks."""

    def test_skip_already_uploaded(
        self, mock_metadata_repo, mock_media_store, mock_media_uploader, sample_task
    ):
        """Test that tasks with platform_media_id are skipped."""
        # Arrange
        sample_task.platform_media_id = "existing123"
        mock_metadata_repo.get_ready_tasks.return_value = [sample_task]

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_store=mock_media_store,
            media_uploader=mock_media_uploader,
        )

        # Act
        stats = service.publish_all_ready_tasks()

        # Assert
        assert stats["processed"] == 1
        assert stats["skipped"] == 1
        assert stats["succeeded"] == 0

        # Should not attempt upload
        mock_media_uploader.publish_media.assert_not_called()
        mock_media_store.exists.assert_not_called()


@pytest.mark.unit
class TestPublishServiceValidation:
    """Test validation errors."""

    def test_media_transition_error(
        self, mock_metadata_repo, mock_media_store, mock_media_uploader, sample_task
    ):
        """Test handling of media transition error (e.g., file not found)."""
        # Arrange
        mock_metadata_repo.get_ready_tasks.return_value = [sample_task]
        mock_media_store.mark_in_progress.side_effect = AdapterError(
            code="FILE_NOT_FOUND",
            message="Media file not found"
        )

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_store=mock_media_store,
            media_uploader=mock_media_uploader,
        )

        # Act
        stats = service.publish_all_ready_tasks()

        # Assert
        assert stats["failed"] == 1
        assert stats["succeeded"] == 0

        # Should not attempt upload
        mock_media_uploader.publish_media.assert_not_called()

    def test_storage_error(
        self, mock_metadata_repo, mock_media_store, mock_media_uploader, sample_task
    ):
        """Test handling of storage errors during transition."""
        # Arrange
        mock_metadata_repo.get_ready_tasks.return_value = [sample_task]
        mock_media_store.mark_in_progress.side_effect = AdapterError(
            code="STORAGE_UNAVAILABLE",
            message="Storage unavailable"
        )

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_store=mock_media_store,
            media_uploader=mock_media_uploader,
        )

        # Act
        stats = service.publish_all_ready_tasks()

        # Assert
        assert stats["failed"] == 1
        mock_media_uploader.publish_media.assert_not_called()


@pytest.mark.unit
class TestPublishServiceRetry:
    """Test retry logic for retryable errors."""

    def test_retry_on_retryable_error_then_success(
        self, mock_metadata_repo, mock_media_store, mock_media_uploader, sample_task
    ):
        """Test retry succeeds after temporary failure."""
        # Arrange
        mock_metadata_repo.get_ready_tasks.return_value = [sample_task]

        # First attempt fails, second succeeds
        mock_media_uploader.publish_media.side_effect = [
            RetryableError("Rate limit exceeded"),
            PublishResult(success=True, media_id="abc123", status=TaskStatus.SCHEDULED),
        ]

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_store=mock_media_store,
            media_uploader=mock_media_uploader,
            max_retries=3,
        )

        # Act
        stats = service.publish_all_ready_tasks()

        # Assert
        assert stats["succeeded"] == 1
        assert mock_media_uploader.publish_media.call_count == 2
        assert mock_metadata_repo.increment_attempts.call_count == 2

    def test_retry_exhausted(
        self, mock_metadata_repo, mock_media_store, mock_media_uploader, sample_task
    ):
        """Test max retries exceeded."""
        # Arrange
        mock_metadata_repo.get_ready_tasks.return_value = [sample_task]

        # All attempts fail
        mock_media_uploader.publish_media.side_effect = RetryableError("Network error")

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_store=mock_media_store,
            media_uploader=mock_media_uploader,
            max_retries=3,
        )

        # Act
        stats = service.publish_all_ready_tasks()

        # Assert
        assert stats["failed"] == 1
        assert stats["succeeded"] == 0
        assert mock_media_uploader.publish_media.call_count == 3  # max_retries
        assert mock_metadata_repo.increment_attempts.call_count == 3

        # Should mark as failed
        call_args = mock_metadata_repo.update_task_status.call_args
        assert call_args[1]["status"] == TaskStatus.FAILED.value

    def test_no_retry_on_permanent_error(
        self, mock_metadata_repo, mock_media_store, mock_media_uploader, sample_task
    ):
        """Test permanent errors don't trigger retries."""
        # Arrange
        mock_metadata_repo.get_ready_tasks.return_value = [sample_task]

        # Permanent error
        mock_media_uploader.publish_media.side_effect = PermanentError("Invalid media format")

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_store=mock_media_store,
            media_uploader=mock_media_uploader,
            max_retries=3,
        )

        # Act
        stats = service.publish_all_ready_tasks()

        # Assert
        assert stats["failed"] == 1
        assert mock_media_uploader.publish_media.call_count == 1  # No retries
        assert mock_metadata_repo.increment_attempts.call_count == 1


@pytest.mark.unit
class TestPublishServiceDryRun:
    """Test dry-run mode."""

    def test_dry_run_validates_only(
        self, mock_metadata_repo, mock_media_store, mock_media_uploader, sample_task
    ):
        """Test dry-run mode validates but doesn't upload."""
        # Arrange
        mock_metadata_repo.get_ready_tasks.return_value = [sample_task]

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_store=mock_media_store,
            media_uploader=mock_media_uploader,
            dry_run=True,
        )

        # Act
        stats = service.publish_all_ready_tasks()

        # Assert
        assert stats["succeeded"] == 1

        # Should NOT upload
        mock_media_uploader.publish_media.assert_not_called()
        mock_media_uploader.upload_thumbnail.assert_not_called()

    def test_dry_run_catches_validation_errors(
        self, mock_metadata_repo, mock_media_store, mock_media_uploader, sample_task
    ):
        """Test dry-run mode still validates and catches errors."""
        # Arrange
        mock_metadata_repo.get_ready_tasks.return_value = [sample_task]
        mock_media_store.mark_in_progress.side_effect = AdapterError(
            code="FILE_NOT_FOUND",
            message="Media file not found"
        )

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_store=mock_media_store,
            media_uploader=mock_media_uploader,
            dry_run=True,
        )

        # Act
        stats = service.publish_all_ready_tasks()

        # Assert
        assert stats["failed"] == 1


@pytest.mark.unit
class TestPublishServiceMultipleTasks:
    """Test processing multiple tasks."""

    def test_multiple_tasks_mixed_results(
        self, mock_metadata_repo, mock_media_store, mock_media_uploader
    ):
        """Test processing multiple tasks with different outcomes."""
        # Arrange
        task1 = Task(
            task_id="task1",
            row_index=2,
            media_reference="/videos/video1.mp4",
            title="Video 1",
        )
        task2 = Task(
            task_id="task2",
            row_index=3,
            media_reference="/videos/video2.mp4",
            title="Video 2",
            platform_media_id="existing123",  # Already uploaded
        )
        task3 = Task(
            task_id="task3",
            row_index=4,
            media_reference="/videos/video3.mp4",
            title="Video 3",
        )

        mock_metadata_repo.get_ready_tasks.return_value = [task1, task2, task3]
        # task1 transitions OK, task3 fails
        mock_media_store.mark_in_progress.side_effect = [
            "/in_progress/videos/video1.mp4",  # task1 OK
            AdapterError(code="FILE_NOT_FOUND", message="File not found"),  # task3 fails
        ]

        mock_media_uploader.publish_media.return_value = PublishResult(
            success=True, media_id="abc123", status=TaskStatus.SCHEDULED
        )

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_store=mock_media_store,
            media_uploader=mock_media_uploader,
        )

        # Act
        stats = service.publish_all_ready_tasks()

        # Assert
        assert stats["processed"] == 3
        assert stats["succeeded"] == 1  # task1
        assert stats["skipped"] == 1  # task2 (already uploaded)
        assert stats["failed"] == 1  # task3 (file not found)
