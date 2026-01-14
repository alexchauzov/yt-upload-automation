"""Acceptance tests for video file workflow through directories."""
import pytest

from domain.models import TaskStatus, VideoTask
from tests.acceptance.fake_youtube_backend import FakeYouTubeBackend, FakeYouTubeMode
from tests.acceptance.test_file_workflow_helpers import create_test_video


@pytest.mark.acceptance
class TestFileWorkflowA1:
    """A1: Starting processing moves file WATCH -> IN_PROGRESS."""

    def test_start_processing_moves_file_to_in_progress(
        self, clean_workflow_dirs, run_spreadsheet_id
    ):
        """
        When processing starts, file should move from WATCH to IN_PROGRESS.

        Expected behavior (not yet implemented):
        - File physically moved from WATCH to IN_PROGRESS directory
        - Task.video_file_path updated to new location
        - File remains readable at new location
        """
        watch_dir = clean_workflow_dirs["WATCH"]
        in_progress_dir = clean_workflow_dirs["IN_PROGRESS"]

        video_file = create_test_video(watch_dir, "test_video_a1.mp4")

        task = VideoTask(
            task_id="a1_test",
            row_index=2,
            video_file_path=str(video_file),
            title="Test A1",
        )

        assert not video_file.exists(), "File should be removed from WATCH"

        expected_new_path = in_progress_dir / "test_video_a1.mp4"
        assert expected_new_path.exists(), "File should exist in IN_PROGRESS"
        assert expected_new_path.is_file(), "Path should be a file"

        with open(expected_new_path, 'rb') as f:
            content = f.read()
            assert len(content) > 0, "File should be readable"

        pytest.xfail("File workflow not implemented yet")


@pytest.mark.acceptance
class TestFileWorkflowA2:
    """A2: YouTube success moves file IN_PROGRESS -> UPLOADED."""

    def test_youtube_success_moves_to_uploaded(
        self, clean_workflow_dirs, run_spreadsheet_id
    ):
        """
        When YouTube upload succeeds, file should move to UPLOADED.

        Expected behavior (not yet implemented):
        - File physically moved from IN_PROGRESS to UPLOADED directory
        - Task.video_file_path updated to new location
        - Task marked with youtube_video_id
        """
        in_progress_dir = clean_workflow_dirs["IN_PROGRESS"]
        uploaded_dir = clean_workflow_dirs["UPLOADED"]

        video_file = create_test_video(in_progress_dir, "test_video_a2.mp4")

        task = VideoTask(
            task_id="a2_test",
            row_index=2,
            video_file_path=str(video_file),
            title="Test A2",
        )

        fake_backend = FakeYouTubeBackend(mode=FakeYouTubeMode.SUCCESS_PUBLIC)

        assert not video_file.exists(), "File should be removed from IN_PROGRESS"

        expected_new_path = uploaded_dir / "test_video_a2.mp4"
        assert expected_new_path.exists(), "File should exist in UPLOADED"

        pytest.xfail("File workflow not implemented yet")


@pytest.mark.acceptance
class TestFileWorkflowA3:
    """A3: YouTube failure moves file IN_PROGRESS -> FAILED."""

    def test_youtube_failure_moves_to_failed(
        self, clean_workflow_dirs, run_spreadsheet_id
    ):
        """
        When YouTube upload fails, file should move to FAILED.

        Expected behavior (not yet implemented):
        - File physically moved from IN_PROGRESS to FAILED directory
        - Task.video_file_path updated to new location
        - Task.status set to FAILED
        - Task.error_message populated with error details
        """
        in_progress_dir = clean_workflow_dirs["IN_PROGRESS"]
        failed_dir = clean_workflow_dirs["FAILED"]

        video_file = create_test_video(in_progress_dir, "test_video_a3.mp4")

        task = VideoTask(
            task_id="a3_test",
            row_index=2,
            video_file_path=str(video_file),
            title="Test A3",
            status=TaskStatus.READY,
        )

        fake_backend = FakeYouTubeBackend(mode=FakeYouTubeMode.FAIL_PERMANENT)

        assert not video_file.exists(), "File should be removed from IN_PROGRESS"

        expected_new_path = failed_dir / "test_video_a3.mp4"
        assert expected_new_path.exists(), "File should exist in FAILED"

        pytest.xfail("File workflow not implemented yet")


@pytest.mark.acceptance
class TestFileWorkflowA4:
    """A4: Destination file exists -> move to FAILED."""

    def test_duplicate_in_uploaded_moves_to_failed(
        self, clean_workflow_dirs, run_spreadsheet_id
    ):
        """
        When destination file already exists, treat as failure.

        Expected behavior (not yet implemented):
        - Detect file already exists in UPLOADED directory
        - Move file to FAILED instead of UPLOADED
        - Task.video_file_path updated to FAILED location
        - Task.status set to FAILED
        - Task.error_message contains "already exists" or similar
        """
        in_progress_dir = clean_workflow_dirs["IN_PROGRESS"]
        uploaded_dir = clean_workflow_dirs["UPLOADED"]
        failed_dir = clean_workflow_dirs["FAILED"]

        video_file = create_test_video(in_progress_dir, "test_video_a4.mp4")
        duplicate_file = create_test_video(uploaded_dir, "test_video_a4.mp4")

        task = VideoTask(
            task_id="a4_test",
            row_index=2,
            video_file_path=str(video_file),
            title="Test A4",
        )

        fake_backend = FakeYouTubeBackend(mode=FakeYouTubeMode.SUCCESS_PUBLIC)

        assert not video_file.exists(), "Original file should be removed from IN_PROGRESS"
        assert duplicate_file.exists(), "Duplicate in UPLOADED should remain"

        expected_failed_path = failed_dir / "test_video_a4.mp4"
        assert expected_failed_path.exists(), "File should be moved to FAILED"

        pytest.xfail("File workflow not implemented yet")
