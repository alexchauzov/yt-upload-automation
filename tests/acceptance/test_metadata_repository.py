"""Acceptance tests for MetadataRepository adapter (Google Sheets)."""
import os
from datetime import datetime
from typing import List
from unittest.mock import Mock

import pytest
from google.oauth2 import service_account
from googleapiclient.discovery import build

from adapters.google_sheets_repository import GoogleSheetsMetadataRepository
from domain.models import TaskStatus, Task, PrivacyStatus
from domain.services import PublishService
from ports.media_store import MediaStore
from tests.acceptance.fake_youtube_uploader import FakeYouTubeUploader, FakeYouTubeMode


def repo_for_sheet(sheet_name: str, spreadsheet_id: str) -> GoogleSheetsMetadataRepository:
    """Create repository instance for a specific sheet."""
    return GoogleSheetsMetadataRepository(
        spreadsheet_id=spreadsheet_id,
        range_name=f"{sheet_name}!A:Z",
        credentials_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
    )


def create_publish_service_for_test(
    sheet_name: str,
    spreadsheet_id: str,
    fake_youtube_mode: FakeYouTubeMode = FakeYouTubeMode.SUCCESS_PUBLIC,
) -> PublishService:
    """
    Create PublishService for acceptance tests with fake uploader.

    Args:
        sheet_name: Sheet name for metadata repository.
        spreadsheet_id: Google Sheets document ID.
        fake_youtube_mode: Mode for fake YouTube uploader.

    Returns:
        PublishService configured for acceptance testing.
    """
    from pathlib import Path

    metadata_repo = repo_for_sheet(sheet_name, spreadsheet_id)

    mock_media_store = Mock(spec=MediaStore)
    mock_media_store.exists.return_value = True
    mock_media_store.get_path.side_effect = lambda ref: Path(ref)
    mock_media_store.mark_in_progress.side_effect = lambda ref: ref  # Return string, not Mock
    mock_media_store.transition.side_effect = lambda ref, stage: ref  # Return string, not Mock

    fake_uploader = FakeYouTubeUploader(mode=fake_youtube_mode)

    return PublishService(
        metadata_repo=metadata_repo,
        media_store=mock_media_store,
        media_uploader=fake_uploader,
        max_retries=1,
        dry_run=False,
    )


def read_all_rows_from_sheet(sheet_name: str, spreadsheet_id: str) -> List[Task]:
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

        # Read from column "video_file_path" but store as media_reference (abstract reference)
        media_reference = get_cell(row, "video_file_path")
        title = get_cell(row, "title")
        description = get_cell(row, "description", default="")
        publish_at = parse_datetime(get_cell(row, "publish_at", default=None))

        privacy_status_str = get_cell(row, "privacy_status", default="private")
        try:
            privacy_status = PrivacyStatus(privacy_status_str)
        except ValueError:
            privacy_status = PrivacyStatus.PRIVATE

        # Read from column "youtube_video_id" but store as platform_media_id (platform-agnostic)
        platform_media_id = get_cell(row, "youtube_video_id", default=None)
        error_message = get_cell(row, "error_message", default=None)

        task = Task(
            task_id=task_id,
            row_index=row_index,
            media_reference=media_reference,
            title=title,
            description=description,
            publish_at=publish_at,
            privacy_status=privacy_status,
            status=status,
            platform_media_id=platform_media_id or None,
            error_message=error_message or None,
        )
        tasks.append(task)

    return tasks


@pytest.mark.acceptance
class TestMetadataRepositoryBasicRead:
    """Test #1: Basic read with standard column order."""

    def test_read_single_ready_task(self, run_spreadsheet_id):
        """Read single READY task from Test #1 sheet with standard columns."""
        repo = repo_for_sheet("Test #1", run_spreadsheet_id)
        tasks = repo.get_ready_tasks()

        assert len(tasks) == 1

        task = tasks[0]
        assert task.task_id == "1"
        assert task.media_reference == r"D:\Projects\test-data\VID.mp4"
        assert task.title == "Test upload"
        assert task.description == "Test description"
        assert task.status == TaskStatus.READY

        expected_dt = datetime(2025, 12, 27, 22, 30, 0)
        assert task.publish_at == expected_dt, (
            f"Expected publish_at={expected_dt}, got {task.publish_at}"
        )


@pytest.mark.acceptance
class TestMetadataRepositoryShuffledColumns:
    """Test #2: Read with shuffled column order."""

    def test_read_shuffled_columns(self, run_spreadsheet_id):
        """Columns shuffled but data same as Test #1."""
        repo = repo_for_sheet("Test #2", run_spreadsheet_id)
        tasks = repo.get_ready_tasks()

        assert len(tasks) == 1

        task = tasks[0]
        assert task.task_id == "1"
        assert task.media_reference == r"D:\Projects\test-data\VID.mp4"
        assert task.title == "Test upload"
        assert task.description == "Test description"
        assert task.status == TaskStatus.READY

        expected_dt = datetime(2025, 12, 27, 22, 30, 0)
        assert task.publish_at == expected_dt


@pytest.mark.acceptance
class TestMetadataRepositoryWriteNormalColumns:
    """Test #3: Write + read-back with normal column order."""

    def test_write_and_readback_normal_columns(self, run_spreadsheet_id):
        """Update status and youtube_video_id, then verify."""
        repo = repo_for_sheet("Test #3", run_spreadsheet_id)

        tasks = repo.get_ready_tasks()
        assert len(tasks) == 1
        task = tasks[0]

        repo.update_task_status(
            task,
            status=TaskStatus.SCHEDULED.value,
            platform_media_id="vIdEoId",
        )

        tasks_after = repo.get_ready_tasks()
        assert len(tasks_after) == 0, (
            "Task should no longer be READY after update to SCHEDULED"
        )


@pytest.mark.acceptance
class TestMetadataRepositoryWriteShuffledColumns:
    """Test #4: Write + read-back with shuffled column order."""

    def test_write_and_readback_shuffled_columns(self, run_spreadsheet_id):
        """Update with shuffled columns should work but currently uses COLUMN_MAP fallback."""
        repo = repo_for_sheet("Test #4", run_spreadsheet_id)

        tasks = repo.get_ready_tasks()
        assert len(tasks) == 1
        task = tasks[0]

        repo.update_task_status(
            task,
            status=TaskStatus.SCHEDULED.value,
            platform_media_id="vIdEoId",
        )

        tasks_after = repo.get_ready_tasks()
        assert len(tasks_after) == 0, (
            "Task should no longer be READY after update to SCHEDULED"
        )


@pytest.mark.acceptance
class TestMetadataRepositoryBulkOperations:
    """Test #5: Bulk process READY tasks through PublishService."""

    def test_bulk_read_and_update(self, run_spreadsheet_id):
        """
        Process 6 READY tasks through real PublishService flow.

        Tests full flow: read READY -> fake upload -> update sheet with status/video_id.
        No manual status painting; PublishService handles everything.
        Sheet may contain mixed extensions; outcomes determined by FakeYouTubeUploader.
        """
        repo = repo_for_sheet("Test #5", run_spreadsheet_id)

        tasks_before = repo.get_ready_tasks()
        assert len(tasks_before) == 6, f"Expected 6 READY tasks, got {len(tasks_before)}"

        expected_task_ids = {"1", "2", "3", "4", "5", "6"}
        actual_task_ids = {task.task_id for task in tasks_before}
        assert actual_task_ids == expected_task_ids

        for task in tasks_before:
            assert task.status == TaskStatus.READY

        mp4_or_mov_tasks = [
            task for task in tasks_before
            if task.media_reference.endswith(('.mp4', '.mov'))
        ]
        other_tasks = [
            task for task in tasks_before
            if not task.media_reference.endswith(('.mp4', '.mov'))
        ]

        service = create_publish_service_for_test("Test #5", run_spreadsheet_id)
        stats = service.publish_all_ready_tasks()

        assert stats["processed"] == 6, f"Expected 6 processed, got {stats['processed']}"
        assert stats["succeeded"] == len(mp4_or_mov_tasks), (
            f"Expected {len(mp4_or_mov_tasks)} succeeded, got {stats['succeeded']}"
        )
        assert stats["failed"] == len(other_tasks), (
            f"Expected {len(other_tasks)} failed, got {stats['failed']}"
        )

        tasks_after = repo.get_ready_tasks()
        assert len(tasks_after) == 0, "All READY tasks should be processed"

        all_tasks = read_all_rows_from_sheet("Test #5", run_spreadsheet_id)
        mp4_or_mov_task_ids = {task.task_id for task in mp4_or_mov_tasks}
        other_task_ids = {task.task_id for task in other_tasks}

        for task in all_tasks:
            if task.task_id in mp4_or_mov_task_ids:
                assert task.status == TaskStatus.SCHEDULED, (
                    f"Task {task.task_id}: expected SCHEDULED, got {task.status}"
                )
                assert task.platform_media_id, f"Task {task.task_id}: platform_media_id should not be empty"
                assert task.platform_media_id.startswith("fake_"), (
                    f"Task {task.task_id}: expected fake media_id, got {task.platform_media_id}"
                )
            elif task.task_id in other_task_ids:
                assert task.status == TaskStatus.FAILED, (
                    f"Task {task.task_id}: expected FAILED, got {task.status}"
                )
                assert task.error_message == "Incorrect media format", (
                    f"Task {task.task_id}: expected error 'Incorrect media format', got '{task.error_message}'"
                )


@pytest.mark.acceptance
class TestMetadataRepositoryConditionalUpdate:
    """Test #6: Process mixed extensions through PublishService."""

    def test_conditional_update_by_extension(self, run_spreadsheet_id):
        """
        Process READY tasks with mixed extensions through PublishService.

        Tests that:
        - .mp4 files => SCHEDULED + youtube_video_id (uploader accepts)
        - other extensions => FAILED + error_message (uploader rejects)

        Extension validation logic is in FakeYouTubeUploader, NOT in test.
        Test only verifies outcomes. Shuffled columns in Test #6 sheet.
        """
        repo = repo_for_sheet("Test #6", run_spreadsheet_id)

        tasks_before = repo.get_ready_tasks()
        assert len(tasks_before) > 0, "Sheet should contain READY tasks"

        mp4_task_ids = {
            task.task_id for task in tasks_before
            if task.media_reference.endswith(".mp4")
        }
        non_mp4_task_ids = {
            task.task_id for task in tasks_before
            if not task.media_reference.endswith(".mp4")
        }

        assert len(mp4_task_ids) > 0, "Should have at least one .mp4 task"
        assert len(non_mp4_task_ids) > 0, "Should have at least one non-.mp4 task"

        service = create_publish_service_for_test("Test #6", run_spreadsheet_id)
        stats = service.publish_all_ready_tasks()

        expected_succeeded = len(mp4_task_ids)
        expected_failed = len(non_mp4_task_ids)
        assert stats["succeeded"] == expected_succeeded, (
            f"Expected {expected_succeeded} succeeded, got {stats['succeeded']}"
        )
        assert stats["failed"] == expected_failed, (
            f"Expected {expected_failed} failed, got {stats['failed']}"
        )

        tasks_after = repo.get_ready_tasks()
        assert len(tasks_after) == 0, "All READY tasks should be processed"

        all_tasks = read_all_rows_from_sheet("Test #6", run_spreadsheet_id)

        for task in all_tasks:
            if task.task_id in mp4_task_ids:
                assert task.status == TaskStatus.SCHEDULED, (
                    f"Task {task.task_id} (.mp4): expected SCHEDULED, got {task.status}"
                )
                assert task.platform_media_id, (
                    f"Task {task.task_id} (.mp4): platform_media_id should not be empty"
                )
                assert not task.error_message, (
                    f"Task {task.task_id} (.mp4): error_message should be empty"
                )
            elif task.task_id in non_mp4_task_ids:
                assert task.status == TaskStatus.FAILED, (
                    f"Task {task.task_id} (non-.mp4): expected FAILED, got {task.status}"
                )
                assert task.error_message == "Incorrect media format", (
                    f"Task {task.task_id} (non-.mp4): expected error 'Incorrect media format', "
                    f"got '{task.error_message}'"
                )
                assert not task.platform_media_id, (
                    f"Task {task.task_id} (non-.mp4): platform_media_id should be empty"
                )
