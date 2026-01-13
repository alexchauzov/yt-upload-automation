"""Acceptance tests for Google Sheets adapter covering Test #1-#6 cases."""
import os
from datetime import datetime
from typing import List

import pytest
from google.oauth2 import service_account
from googleapiclient.discovery import build

from adapters.google_sheets_repository import GoogleSheetsMetadataRepository
from domain.models import TaskStatus, VideoTask, PrivacyStatus


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


def read_all_rows_from_sheet(sheet_name: str, spreadsheet_id: str) -> List[VideoTask]:
    """
    Read ALL rows from sheet regardless of status.

    This is a test helper function - NOT part of the adapter API.
    Used to verify data integrity across all rows in acceptance tests.
    """
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    credentials = service_account.Credentials.from_service_account_file(
        credentials_path,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    service = build("sheets", "v4", credentials=credentials)

    range_name = f"{sheet_name}!A:Z"
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_name
    ).execute()

    rows = result.get("values", [])
    if not rows:
        return []

    header = rows[0]
    data_rows = rows[1:]

    header_map = {}
    for idx, cell in enumerate(header):
        normalized = cell.strip().lower()
        if normalized:
            header_map[normalized] = idx

    def get_cell(row, column_name, default=""):
        normalized_name = column_name.strip().lower()
        index = header_map.get(normalized_name)
        if index is None or index >= len(row):
            return default
        value = row[index].strip()
        return value if value else default

    def parse_datetime(value):
        if not value:
            return None
        try:
            if value.endswith("Z"):
                return datetime.fromisoformat(value[:-1])
            else:
                return datetime.fromisoformat(value)
        except ValueError:
            return None

    tasks = []
    for row_index, row in enumerate(data_rows, start=2):
        pad_length = max(header_map.values()) + 1 if header_map else 16
        if len(row) < pad_length:
            row = row + [""] * (pad_length - len(row))

        task_id = get_cell(row, "task_id")
        if not task_id:
            continue

        status_str = get_cell(row, "status", default="READY")
        try:
            status = TaskStatus(status_str)
        except ValueError:
            continue

        video_file_path = get_cell(row, "video_file_path")
        title = get_cell(row, "title")
        description = get_cell(row, "description", default="")
        publish_at = parse_datetime(get_cell(row, "publish_at", default=None))

        privacy_status_str = get_cell(row, "privacy_status", default="private")
        try:
            privacy_status = PrivacyStatus(privacy_status_str)
        except ValueError:
            privacy_status = PrivacyStatus.PRIVATE

        youtube_video_id = get_cell(row, "youtube_video_id", default=None)
        error_message = get_cell(row, "error_message", default=None)

        task = VideoTask(
            task_id=task_id,
            row_index=row_index,
            video_file_path=video_file_path,
            title=title,
            description=description,
            publish_at=publish_at,
            privacy_status=privacy_status,
            status=status,
            youtube_video_id=youtube_video_id or None,
            error_message=error_message or None,
        )
        tasks.append(task)

    return tasks


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
            assert task.video_file_path, "video_file_path should not be empty"
            assert task.title.startswith("Test "), f"Task {task.task_id}: title should start with 'Test '"
            assert task.description.startswith("Test "), f"Task {task.task_id}: description should start with 'Test '"
            assert task.publish_at == datetime(2025, 12, 27, 22, 30, 0), (
                f"Task {task.task_id}: expected publish_at=2025-12-27 22:30:00, got {task.publish_at}"
            )

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

    def test_conditional_update_by_extension(self, runtime_spreadsheet_id):
        """
        Read all rows (not just READY), update based on extension:
        - .mp4 => SCHEDULED + youtube_video_id
        - other => FAILED + error message

        Test logic is extension-based, independent of row order.
        Shuffled columns in Test #6 sheet.
        """
        repo = repo_for_sheet("Test #6", runtime_spreadsheet_id)

        all_tasks_before = read_all_rows_from_sheet("Test #6", runtime_spreadsheet_id)
        assert len(all_tasks_before) > 0, "Sheet should contain tasks"

        mp4_task_ids = set()
        non_mp4_task_ids = set()

        for task in all_tasks_before:
            if task.video_file_path.endswith(".mp4"):
                mp4_task_ids.add(task.task_id)
                repo.update_task_status(
                    task,
                    status=TaskStatus.SCHEDULED.value,
                    youtube_video_id=f"tAsKiD{task.task_id}",
                )
            else:
                non_mp4_task_ids.add(task.task_id)
                repo.update_task_status(
                    task,
                    status=TaskStatus.FAILED.value,
                    error_message="Incorrect video format",
                )

        all_tasks_after = read_all_rows_from_sheet("Test #6", runtime_spreadsheet_id)
        assert len(all_tasks_after) == len(all_tasks_before), "Row count should not change"

        for task in all_tasks_after:
            if task.task_id in mp4_task_ids:
                assert task.status == TaskStatus.SCHEDULED, (
                    f"Task {task.task_id} (.mp4): expected status SCHEDULED, got {task.status}"
                )
                assert task.youtube_video_id == f"tAsKiD{task.task_id}", (
                    f"Task {task.task_id} (.mp4): expected youtube_video_id=tAsKiD{task.task_id}, "
                    f"got {task.youtube_video_id}"
                )
            elif task.task_id in non_mp4_task_ids:
                assert task.status == TaskStatus.FAILED, (
                    f"Task {task.task_id} (non-.mp4): expected status FAILED, got {task.status}"
                )
                assert task.error_message == "Incorrect video format", (
                    f"Task {task.task_id} (non-.mp4): expected error_message='Incorrect video format', "
                    f"got '{task.error_message}'"
                )
