import os
import pytest
from datetime import datetime

from adapters.google_sheets_repository import GoogleSheetsMetadataRepository
from domain.models import TaskStatus, VideoTask
from tests.acceptance.conftest import skip_without_credentials


@pytest.mark.acceptance
@skip_without_credentials
class TestGoogleSheetsLiveRead:

    def test_read_single_ready_task_from_live_sheets(self):
        repo = GoogleSheetsMetadataRepository()

        tasks = repo.get_ready_tasks()

        assert len(tasks) == 1, f"Expected 1 task, got {len(tasks)}"

        task = tasks[0]

        assert isinstance(task, VideoTask)

        assert task.task_id == "1", f"task_id mismatch: {task.task_id}"
        assert task.video_file_path == r"D:\Dropbox\PsychoAlex\Projects\data\VID_20251209_171519_579.mp4"
        assert task.title == "Test upload", f"title mismatch: {task.title}"
        assert task.description == "Test description", f"description mismatch: {task.description}"
        assert task.status == TaskStatus.READY, f"status mismatch: {task.status}"

        expected_publish_at = datetime(2025, 12, 27, 22, 30, 0)
        assert task.publish_at == expected_publish_at, f"publish_at mismatch: {task.publish_at}"

        assert task.row_index >= 2, f"row_index should be >= 2, got {task.row_index}"
