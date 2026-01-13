"""Acceptance tests for Google Sheets adapter covering Test #1-#6 cases."""
import os
from datetime import datetime

import pytest

from adapters.google_sheets_repository import GoogleSheetsMetadataRepository
from domain.models import TaskStatus


@pytest.fixture
def runtime_spreadsheet_id():
    """Get runtime spreadsheet ID from environment."""
    return os.getenv("RUNTIME_SPREADSHEET_ID")


def repo_for_sheet(sheet_name: str, spreadsheet_id: str) -> GoogleSheetsMetadataRepository:
    """Create repository instance for a specific sheet."""
    return GoogleSheetsMetadataRepository(
        spreadsheet_id=spreadsheet_id,
        range_name=f"{sheet_name}!A:Z",
        credentials_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
    )


@pytest.mark.acceptance
class TestSheetsBasicRead:
    """Test #1: Basic read with standard column order."""

    def test_read_single_ready_task(self, runtime_spreadsheet_id):
        """Read single READY task from Test #1 sheet with standard columns."""
        repo = repo_for_sheet("Test #1", runtime_spreadsheet_id)
        tasks = repo.get_ready_tasks()

        assert len(tasks) == 1

        task = tasks[0]
        assert task.task_id == "1"
        assert task.video_file_path == r"D:\Projects\test-data\VID.mp4"
        assert task.title == "Test upload"
        assert task.description == "Test description"
        assert task.status == TaskStatus.READY

        expected_dt = datetime(2025, 12, 27, 22, 30, 0)
        assert task.publish_at == expected_dt, (
            f"Expected publish_at={expected_dt}, got {task.publish_at}"
        )


@pytest.mark.acceptance
class TestSheetsShuffledColumns:
    """Test #2: Read with shuffled column order."""

    def test_read_shuffled_columns(self, runtime_spreadsheet_id):
        """Columns shuffled but data same as Test #1."""
        repo = repo_for_sheet("Test #2", runtime_spreadsheet_id)
        tasks = repo.get_ready_tasks()

        assert len(tasks) == 1

        task = tasks[0]
        assert task.task_id == "1"
        assert task.video_file_path == r"D:\Projects\test-data\VID.mp4"
        assert task.title == "Test upload"
        assert task.description == "Test description"
        assert task.status == TaskStatus.READY

        expected_dt = datetime(2025, 12, 27, 22, 30, 0)
        assert task.publish_at == expected_dt


@pytest.mark.acceptance
class TestSheetsWriteNormalColumns:
    """Test #3: Write + read-back with normal column order."""

    def test_write_and_readback_normal_columns(self, runtime_spreadsheet_id):
        """Update status and youtube_video_id, then verify."""
        repo = repo_for_sheet("Test #3", runtime_spreadsheet_id)

        tasks = repo.get_ready_tasks()
        assert len(tasks) == 1
        task = tasks[0]

        repo.update_task_status(
            task,
            status=TaskStatus.SCHEDULED.value,
            youtube_video_id="vIdEoId",
        )

        tasks_after = repo.get_ready_tasks()
        assert len(tasks_after) == 0, (
            "Task should no longer be READY after update to SCHEDULED"
        )


@pytest.mark.acceptance
class TestSheetsWriteShuffledColumns:
    """Test #4: Write + read-back with shuffled column order."""

    @pytest.mark.xfail(
        reason="Adapter update_task_status uses COLUMN_MAP instead of header_map (shuffled columns not supported for writes)"
    )
    def test_write_and_readback_shuffled_columns(self, runtime_spreadsheet_id):
        """Update with shuffled columns should work but currently uses COLUMN_MAP fallback."""
        repo = repo_for_sheet("Test #4", runtime_spreadsheet_id)

        tasks = repo.get_ready_tasks()
        assert len(tasks) == 1
        task = tasks[0]

        repo.update_task_status(
            task,
            status=TaskStatus.SCHEDULED.value,
            youtube_video_id="vIdEoId",
        )

        tasks_after = repo.get_ready_tasks()
        assert len(tasks_after) == 0, (
            "Task should no longer be READY after update to SCHEDULED"
        )


@pytest.mark.acceptance
class TestSheetsBulkOperations:
    """Test #5: Bulk read READY + bulk update."""

    def test_bulk_read_and_update(self, runtime_spreadsheet_id):
        """Read 6 READY tasks and update all to SCHEDULED."""
        repo = repo_for_sheet("Test #5", runtime_spreadsheet_id)

        tasks = repo.get_ready_tasks()
        assert len(tasks) == 6, f"Expected 6 READY tasks, got {len(tasks)}"

        expected_task_ids = {"1", "2", "3", "4", "5", "6"}
        actual_task_ids = {task.task_id for task in tasks}
        assert actual_task_ids == expected_task_ids

        for task in tasks:
            assert task.status == TaskStatus.READY
            assert task.video_file_path.endswith(".mp4")
            assert task.title.startswith("Test ")
            assert task.description.startswith("Test ")
            assert task.publish_at == datetime(2025, 12, 27, 22, 30, 0)

        for task in tasks:
            repo.update_task_status(
                task,
                status=TaskStatus.SCHEDULED.value,
                youtube_video_id=f"tAsKiD{task.task_id}",
            )

        tasks_after = repo.get_ready_tasks()
        assert len(tasks_after) == 0, "All tasks should be SCHEDULED after bulk update"


@pytest.mark.acceptance
class TestSheetsConditionalUpdate:
    """Test #6: Read all statuses + conditional update based on file extension."""

    @pytest.mark.xfail(
        reason="Adapter lacks read_all_tasks() API - only get_ready_tasks() available"
    )
    def test_conditional_update_by_extension(self, runtime_spreadsheet_id):
        """
        Read all rows (not just READY), update based on extension:
        - .mp4 => SCHEDULED + youtube_video_id
        - other => FAILED + error message

        Expected in Test #6:
        - 6 rows total with shuffled columns (status, video_file_path, title, task_id, description, publish_at)
        - Initial: READY (.mp6), READY (.mp4), FAILED (.mp5), DONE (.mp5), READY (.mp4), READY (.mp6)
        - After update: 3 SCHEDULED (.mp4), 3 FAILED (non-.mp4)
        """
        repo = repo_for_sheet("Test #6", runtime_spreadsheet_id)

        # TODO: Need read_all_tasks() method that returns all rows regardless of status
        # For now, this is a placeholder showing expected logic:
        all_tasks = []  # repo.read_all_tasks() - NOT IMPLEMENTED YET

        assert len(all_tasks) == 6

        for task in all_tasks:
            if task.video_file_path.endswith(".mp4"):
                repo.update_task_status(
                    task,
                    status=TaskStatus.SCHEDULED.value,
                    youtube_video_id=f"tAsKiD{task.task_id}",
                )
            else:
                repo.update_task_status(
                    task,
                    status=TaskStatus.FAILED.value,
                    error_message="Incorrect video format",
                )

        # Verify results
        all_tasks_after = []  # repo.read_all_tasks()

        scheduled_count = sum(1 for t in all_tasks_after if t.status == TaskStatus.SCHEDULED)
        failed_count = sum(1 for t in all_tasks_after if t.status == TaskStatus.FAILED)

        assert scheduled_count == 3, "Expected 3 SCHEDULED tasks (.mp4)"
        assert failed_count == 3, "Expected 3 FAILED tasks (non-.mp4)"

        for task in all_tasks_after:
            if task.status == TaskStatus.SCHEDULED:
                assert task.youtube_video_id == f"tAsKiD{task.task_id}"
            elif task.status == TaskStatus.FAILED:
                assert task.error_message == "Incorrect video format"
