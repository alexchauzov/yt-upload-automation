"""Acceptance tests for LocalMediaStore adapter."""
import pytest
from unittest.mock import Mock

from adapters.local_media_store import LocalMediaStore
from domain.models import TaskStatus, Task
from domain.services import PublishService
from ports.metadata_repository import MetadataRepository
from tests.acceptance.fake_youtube_uploader import FakeYouTubeUploader, FakeYouTubeMode
from tests.acceptance.test_local_media_helpers import create_test_video


@pytest.mark.acceptance
class TestLocalMediaStoreA1:
    """A1: Starting processing moves file WATCH -> IN_PROGRESS."""

    def test_start_processing_moves_file_to_in_progress(
        self, clean_workflow_dirs, run_spreadsheet_id
    ):
        """
        When processing starts, file should move from WATCH to IN_PROGRESS.

        Test flow:
        1. Create video file in WATCH directory
        2. Create task pointing to WATCH file
        3. Start processing via PublishService
        4. Verify file moved from WATCH to IN_PROGRESS
        5. Verify task.media_reference updated to new location
        """
        watch_dir = clean_workflow_dirs["WATCH"]
        in_progress_dir = clean_workflow_dirs["IN_PROGRESS"]
        uploaded_dir = clean_workflow_dirs["UPLOADED"]

        video_file = create_test_video(watch_dir, "test_video_a1.mp4")
        assert video_file.exists(), "Video file should exist in WATCH before processing"

        task = Task(
            task_id="a1_test",
            row_index=2,
            media_reference=str(video_file),
            title="Test A1",
        )

        media_store = LocalMediaStore(
            in_progress_dir=in_progress_dir,
            uploaded_dir=uploaded_dir,
        )

        mock_metadata_repo = Mock(spec=MetadataRepository)

        fake_uploader = FakeYouTubeUploader(mode=FakeYouTubeMode.SUCCESS_PUBLIC)

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_store=media_store,
            media_uploader=fake_uploader,
            max_retries=1,
            dry_run=False,
        )

        result = service.publish_task(task)

        assert result == "success", "Publish should succeed"
        assert not video_file.exists(), "File should be removed from WATCH"

        # After successful upload, file should be in UPLOADED directory
        expected_uploaded_path = uploaded_dir / "test_video_a1.mp4"
        assert expected_uploaded_path.exists(), "File should exist in UPLOADED after successful upload"
        assert expected_uploaded_path.is_file(), "Path should be a file"

        with open(expected_uploaded_path, 'rb') as f:
            content = f.read()
            assert len(content) > 0, "File should be readable"

        assert task.media_reference == str(expected_uploaded_path), (
            f"Task media_reference should be updated to UPLOADED path: {expected_uploaded_path}"
        )


@pytest.mark.acceptance
class TestLocalMediaStoreA2:
    """A2: YouTube success moves file IN_PROGRESS -> UPLOADED."""

    def test_youtube_success_moves_to_uploaded(
        self, clean_workflow_dirs, run_spreadsheet_id
    ):
        """
        When YouTube upload succeeds, file should move to UPLOADED.

        Test flow:
        1. Create video file in IN_PROGRESS directory
        2. Create task pointing to IN_PROGRESS file
        3. Process task via PublishService (with fake successful uploader)
        4. Verify file moved from IN_PROGRESS to UPLOADED
        5. Verify task.media_reference updated to new location
        """
        in_progress_dir = clean_workflow_dirs["IN_PROGRESS"]
        uploaded_dir = clean_workflow_dirs["UPLOADED"]

        video_file = create_test_video(in_progress_dir, "test_video_a2.mp4")

        task = Task(
            task_id="a2_test",
            row_index=2,
            media_reference=str(video_file),
            title="Test A2",
        )

        media_store = LocalMediaStore(
            in_progress_dir=in_progress_dir,
            uploaded_dir=uploaded_dir,
        )

        mock_metadata_repo = Mock(spec=MetadataRepository)

        fake_uploader = FakeYouTubeUploader(mode=FakeYouTubeMode.SUCCESS_PUBLIC)

        service = PublishService(
            metadata_repo=mock_metadata_repo,
            media_store=media_store,
            media_uploader=fake_uploader,
            max_retries=1,
            dry_run=False,
        )

        result = service.publish_task(task)

        assert result == "success", "Publish should succeed"
        assert not video_file.exists(), "File should be removed from IN_PROGRESS"

        expected_new_path = uploaded_dir / "test_video_a2.mp4"
        assert expected_new_path.exists(), "File should exist in UPLOADED"
        assert expected_new_path.is_file(), "Path should be a file"

        with open(expected_new_path, 'rb') as f:
            content = f.read()
            assert len(content) > 0, "File should be readable"        assert task.media_reference == str(expected_new_path), (
            f"Task media_reference should be updated to new path: {expected_new_path}"
        )
