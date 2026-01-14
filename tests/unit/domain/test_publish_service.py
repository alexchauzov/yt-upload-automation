"""Unit tests for PublishService."""
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, MagicMock, call

from domain.models import VideoTask, TaskStatus, PrivacyStatus, PublishResult
from domain.services import PublishService
from ports.adapter_error import AdapterError
from ports.media_file_store import MediaFileStore
from ports.metadata_repository import MetadataRepository
from ports.video_backend import VideoBackend, RetryableError, PermanentError


@pytest.fixture
def mock_metadata_repo():
    """Mock metadata repository."""
    return Mock(spec=MetadataRepository)


@pytest.fixture
def mock_media_file_store():
    """Mock media file store."""
    return Mock(spec=MediaFileStore)


@pytest.fixture
def mock_video_backend():
    """Mock video backend."""
    return Mock(spec=VideoBackend)


@pytest.fixture
def sample_task():
    """Sample video task."""
    return VideoTask(
        task_id="test_001",
        row_index=2,
        video_file_path="/videos/test.mp4",
        title="Test Video",
        description="Test description",
        tags=["test", "demo"],
        status=TaskStatus.READY,
    )


@pytest.mark.unit
class TestPublishServiceHappyPath:
    """Test successful publishing scenarios."""

    def test_successful_publish(
        self, mock_metadata_repo, mock_media_file_store, mock_video_backend, sample_task
    ):
        """Test successful video publishing."""
        # Arrange
        mock_metadata_repo.get_ready_tasks.return_value = [sample_task]
        mock_media_file_store.exists.return_value = True
        mock_media_file_store.get_path.return_value = Path("/videos/test.mp4")

        mock_video_backend.publish_video.return_value = PublishResult(
            success=True,
            video_id="abc123",
            status=TaskStatus.SCHEDULED,
            publish_at=None,
        )

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_file_store=mock_media_file_store,
            video_backend=mock_video_backend,
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
        mock_media_file_store.exists.assert_called_with("/videos/test.mp4")
        mock_video_backend.publish_video.assert_called_once()
        mock_metadata_repo.update_task_status.assert_called_with(
            sample_task,
            status=TaskStatus.SCHEDULED.value,
            youtube_video_id="abc123",
        )
        mock_metadata_repo.increment_attempts.assert_called_once_with(sample_task)

    def test_successful_publish_with_thumbnail(
        self, mock_metadata_repo, mock_media_file_store, mock_video_backend, sample_task
    ):
        """Test publishing with thumbnail upload."""
        # Arrange
        sample_task.thumbnail_path = "/thumbnails/test.jpg"

        mock_metadata_repo.get_ready_tasks.return_value = [sample_task]
        mock_media_file_store.exists.return_value = True
        mock_media_file_store.get_path.side_effect = [
            Path("/videos/test.mp4"),
            Path("/thumbnails/test.jpg"),
        ]

        mock_video_backend.publish_video.return_value = PublishResult(
            success=True,
            video_id="abc123",
            status=TaskStatus.SCHEDULED,
        )
        mock_video_backend.upload_thumbnail.return_value = True

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_file_store=mock_media_file_store,
            video_backend=mock_video_backend,
        )

        # Act
        stats = service.publish_all_ready_tasks()

        # Assert
        assert stats["succeeded"] == 1
        mock_video_backend.upload_thumbnail.assert_called_once_with(
            "abc123", Path("/thumbnails/test.jpg")
        )


@pytest.mark.unit
class TestPublishServiceIdempotency:
    """Test idempotency - skip already uploaded tasks."""

    def test_skip_already_uploaded(
        self, mock_metadata_repo, mock_media_file_store, mock_video_backend, sample_task
    ):
        """Test that tasks with youtube_video_id are skipped."""
        # Arrange
        sample_task.youtube_video_id = "existing123"
        mock_metadata_repo.get_ready_tasks.return_value = [sample_task]

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_file_store=mock_media_file_store,
            video_backend=mock_video_backend,
        )

        # Act
        stats = service.publish_all_ready_tasks()

        # Assert
        assert stats["processed"] == 1
        assert stats["skipped"] == 1
        assert stats["succeeded"] == 0

        # Should not attempt upload
        mock_video_backend.publish_video.assert_not_called()
        mock_media_file_store.exists.assert_not_called()


@pytest.mark.unit
class TestPublishServiceValidation:
    """Test validation errors."""

    def test_video_file_not_found(
        self, mock_metadata_repo, mock_media_file_store, mock_video_backend, sample_task
    ):
        """Test handling of missing video file."""
        # Arrange
        mock_metadata_repo.get_ready_tasks.return_value = [sample_task]
        mock_media_file_store.exists.return_value = False

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_file_store=mock_media_file_store,
            video_backend=mock_video_backend,
        )

        # Act
        stats = service.publish_all_ready_tasks()

        # Assert
        assert stats["failed"] == 1
        assert stats["succeeded"] == 0

        # Should not attempt upload
        mock_video_backend.publish_video.assert_not_called()

        # Should mark as failed
        mock_metadata_repo.update_task_status.assert_called_once()
        call_args = mock_metadata_repo.update_task_status.call_args
        assert call_args[1]["status"] == TaskStatus.FAILED.value
        assert "not found" in call_args[1]["error_message"].lower()

    def test_storage_error(
        self, mock_metadata_repo, mock_media_file_store, mock_video_backend, sample_task
    ):
        """Test handling of storage errors."""
        # Arrange
        mock_metadata_repo.get_ready_tasks.return_value = [sample_task]
        mock_media_file_store.exists.side_effect = AdapterError(
            code="STORAGE_UNAVAILABLE",
            message="Storage unavailable"
        )

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_file_store=mock_media_file_store,
            video_backend=mock_video_backend,
        )

        # Act
        stats = service.publish_all_ready_tasks()

        # Assert
        assert stats["failed"] == 1
        mock_video_backend.publish_video.assert_not_called()


@pytest.mark.unit
class TestPublishServiceRetry:
    """Test retry logic for retryable errors."""

    def test_retry_on_retryable_error_then_success(
        self, mock_metadata_repo, mock_media_file_store, mock_video_backend, sample_task
    ):
        """Test retry succeeds after temporary failure."""
        # Arrange
        mock_metadata_repo.get_ready_tasks.return_value = [sample_task]
        mock_media_file_store.exists.return_value = True
        mock_media_file_store.get_path.return_value = Path("/videos/test.mp4")

        # First attempt fails, second succeeds
        mock_video_backend.publish_video.side_effect = [
            RetryableError("Rate limit exceeded"),
            PublishResult(success=True, video_id="abc123", status=TaskStatus.SCHEDULED),
        ]

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_file_store=mock_media_file_store,
            video_backend=mock_video_backend,
            max_retries=3,
        )

        # Act
        stats = service.publish_all_ready_tasks()

        # Assert
        assert stats["succeeded"] == 1
        assert mock_video_backend.publish_video.call_count == 2
        assert mock_metadata_repo.increment_attempts.call_count == 2

    def test_retry_exhausted(
        self, mock_metadata_repo, mock_media_file_store, mock_video_backend, sample_task
    ):
        """Test max retries exceeded."""
        # Arrange
        mock_metadata_repo.get_ready_tasks.return_value = [sample_task]
        mock_media_file_store.exists.return_value = True
        mock_media_file_store.get_path.return_value = Path("/videos/test.mp4")

        # All attempts fail
        mock_video_backend.publish_video.side_effect = RetryableError("Network error")

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_file_store=mock_media_file_store,
            video_backend=mock_video_backend,
            max_retries=3,
        )

        # Act
        stats = service.publish_all_ready_tasks()

        # Assert
        assert stats["failed"] == 1
        assert stats["succeeded"] == 0
        assert mock_video_backend.publish_video.call_count == 3  # max_retries
        assert mock_metadata_repo.increment_attempts.call_count == 3

        # Should mark as failed
        call_args = mock_metadata_repo.update_task_status.call_args
        assert call_args[1]["status"] == TaskStatus.FAILED.value

    def test_no_retry_on_permanent_error(
        self, mock_metadata_repo, mock_media_file_store, mock_video_backend, sample_task
    ):
        """Test permanent errors don't trigger retries."""
        # Arrange
        mock_metadata_repo.get_ready_tasks.return_value = [sample_task]
        mock_media_file_store.exists.return_value = True
        mock_media_file_store.get_path.return_value = Path("/videos/test.mp4")

        # Permanent error
        mock_video_backend.publish_video.side_effect = PermanentError("Invalid video format")

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_file_store=mock_media_file_store,
            video_backend=mock_video_backend,
            max_retries=3,
        )

        # Act
        stats = service.publish_all_ready_tasks()

        # Assert
        assert stats["failed"] == 1
        assert mock_video_backend.publish_video.call_count == 1  # No retries
        assert mock_metadata_repo.increment_attempts.call_count == 1


@pytest.mark.unit
class TestPublishServiceDryRun:
    """Test dry-run mode."""

    def test_dry_run_validates_only(
        self, mock_metadata_repo, mock_media_file_store, mock_video_backend, sample_task
    ):
        """Test dry-run mode validates but doesn't upload."""
        # Arrange
        mock_metadata_repo.get_ready_tasks.return_value = [sample_task]
        mock_media_file_store.exists.return_value = True
        mock_media_file_store.get_path.return_value = Path("/videos/test.mp4")

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_file_store=mock_media_file_store,
            video_backend=mock_video_backend,
            dry_run=True,
        )

        # Act
        stats = service.publish_all_ready_tasks()

        # Assert
        assert stats["succeeded"] == 1

        # Should NOT upload
        mock_video_backend.publish_video.assert_not_called()
        mock_video_backend.upload_thumbnail.assert_not_called()

        # Should update status to DRY_RUN_OK
        mock_metadata_repo.update_task_status.assert_called_once()
        call_args = mock_metadata_repo.update_task_status.call_args
        assert call_args[0][1] == TaskStatus.DRY_RUN_OK.value

    def test_dry_run_catches_validation_errors(
        self, mock_metadata_repo, mock_media_file_store, mock_video_backend, sample_task
    ):
        """Test dry-run mode still validates and catches errors."""
        # Arrange
        mock_metadata_repo.get_ready_tasks.return_value = [sample_task]
        mock_media_file_store.exists.return_value = False  # File missing

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_file_store=mock_media_file_store,
            video_backend=mock_video_backend,
            dry_run=True,
        )

        # Act
        stats = service.publish_all_ready_tasks()

        # Assert
        assert stats["failed"] == 1

        # Should mark as failed
        call_args = mock_metadata_repo.update_task_status.call_args
        assert call_args[1]["status"] == TaskStatus.FAILED.value


@pytest.mark.unit
class TestPublishServiceMultipleTasks:
    """Test processing multiple tasks."""

    def test_multiple_tasks_mixed_results(
        self, mock_metadata_repo, mock_media_file_store, mock_video_backend
    ):
        """Test processing multiple tasks with different outcomes."""
        # Arrange
        task1 = VideoTask(
            task_id="task1",
            row_index=2,
            video_file_path="/videos/video1.mp4",
            title="Video 1",
        )
        task2 = VideoTask(
            task_id="task2",
            row_index=3,
            video_file_path="/videos/video2.mp4",
            title="Video 2",
            youtube_video_id="existing123",  # Already uploaded
        )
        task3 = VideoTask(
            task_id="task3",
            row_index=4,
            video_file_path="/videos/video3.mp4",
            title="Video 3",
        )

        mock_metadata_repo.get_ready_tasks.return_value = [task1, task2, task3]
        mock_media_file_store.exists.side_effect = [True, False]  # task1 exists, task3 doesn't
        mock_media_file_store.get_path.return_value = Path("/videos/video1.mp4")

        mock_video_backend.publish_video.return_value = PublishResult(
            success=True, video_id="abc123", status=TaskStatus.SCHEDULED
        )

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_file_store=mock_media_file_store,
            video_backend=mock_video_backend,
        )

        # Act
        stats = service.publish_all_ready_tasks()

        # Assert
        assert stats["processed"] == 3
        assert stats["succeeded"] == 1  # task1
        assert stats["skipped"] == 1  # task2 (already uploaded)
        assert stats["failed"] == 1  # task3 (file not found)
