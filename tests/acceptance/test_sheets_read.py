import os

import pytest
from datetime import datetime

from adapters.google_sheets_repository import GoogleSheetsMetadataRepository
from domain.models import TaskStatus


@pytest.mark.acceptance
class TestSheetsRead:
    def test_get_ready_tasks_returns_expected_task(self):
        sheet_name = "Test #1"
        repo = GoogleSheetsMetadataRepository(
            spreadsheet_id=os.getenv("GOOGLE_SHEETS_ID"),
            range_name=f"{sheet_name}!A:Z",
            credentials_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        )
        tasks = repo.get_ready_tasks()

        assert len(tasks) == 1

        task = tasks[0]
        assert task.task_id == "1"
        assert task.video_file_path == r"D:\Projects\test-data\VID.mp4"
        assert task.title == "Test upload"
        assert task.description == "Test description"
        assert task.status == TaskStatus.READY
        assert task.publish_at == datetime(2025, 12, 27, 22, 30, 0)
