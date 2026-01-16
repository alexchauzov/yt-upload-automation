"""Full workflow acceptance tests with real adapters.

Tests integration of:
- GoogleSheetsMetadataRepository (real)
- LocalMediaStore (real)
- FakeYouTubeUploader (mock - only uploader is mocked)

These tests verify the complete publishing workflow with real file system
operations and real Google Sheets API calls.
"""
import os
from pathlib import Path

import pytest

from adapters.google_sheets_repository import GoogleSheetsMetadataRepository
from adapters.local_media_store import LocalMediaStore
from domain.models import TaskStatus
from domain.services import PublishService
from ports.media_uploader import PermanentError
from tests.acceptance.fake_youtube_uploader import FakeYouTubeUploader, FakeYouTubeMode
from tests.acceptance.test_metadata_repository import read_all_rows_from_sheet


def create_test_file(path: Path, size_bytes: int = 1024) -> None:
    """Create a test file with random binary content."""
    import random
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as f:
        f.write(bytes([random.randint(0, 255) for _ in range(size_bytes)]))


class FailOnUploadFakeUploader(FakeYouTubeUploader):
    """Fake uploader that fails during upload (after file is moved to IN_PROGRESS)."""
    
    def __init__(self, error_message: str = "Upload failed: simulated error"):
        super().__init__(mode=FakeYouTubeMode.FAIL)
        self.error_message = error_message
    
    def publish_media(self, task, media_ref: str):
        """Always fail with PermanentError."""
        self.call_count += 1
        raise PermanentError(self.error_message)


@pytest.fixture
def workflow_base_dir():
    """
    Return the base directory for workflow folders.
    Uses relative path from project root: ./watch, ./in_progress, ./uploaded
    """
    return Path(".")


@pytest.fixture
def setup_workflow_dirs(workflow_base_dir):
    """
    Create and clean workflow directories before each test.
    
    Creates:
    - ./watch
    - ./in_progress
    - ./uploaded
    
    Cleans any existing files in these directories.
    """
    watch_dir = workflow_base_dir / "watch"
    in_progress_dir = workflow_base_dir / "in_progress"
    uploaded_dir = workflow_base_dir / "uploaded"
    
    # Create directories
    for d in [watch_dir, in_progress_dir, uploaded_dir]:
        d.mkdir(parents=True, exist_ok=True)
        # Clean existing files
        for f in d.iterdir():
            if f.is_file():
                f.unlink()
    
    return {
        "watch": watch_dir,
        "in_progress": in_progress_dir,
        "uploaded": uploaded_dir,
    }


@pytest.fixture
def local_media_store(setup_workflow_dirs):
    """Create LocalMediaStore with test directories."""
    return LocalMediaStore(
        base_path=Path("."),
        in_progress_dir=setup_workflow_dirs["in_progress"],
        uploaded_dir=setup_workflow_dirs["uploaded"],
    )


def repo_for_sheet(sheet_name: str, spreadsheet_id: str) -> GoogleSheetsMetadataRepository:
    """Create repository instance for a specific sheet."""
    return GoogleSheetsMetadataRepository(
        spreadsheet_id=spreadsheet_id,
        range_name=f"{sheet_name}!A:Z",
        credentials_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
    )


@pytest.mark.acceptance
class TestFullWorkflowUploadError:
    """Test #7: Upload error after file moved to IN_PROGRESS."""

    def test_upload_error_preserves_in_progress_reference(
        self, run_spreadsheet_id, setup_workflow_dirs, local_media_store
    ):
        """
        When upload fails AFTER file is moved to IN_PROGRESS:
        - Task status should be FAILED
        - video_file_path should point to IN_PROGRESS directory
        - youtube_video_id should be empty
        - error_message should indicate upload error
        
        Test flow:
        1. Create vid.mp4 in ./watch (matches spreadsheet reference)
        2. Read task from Test #7 sheet
        3. Process with uploader that fails during upload
        4. Verify: status=FAILED, video_file_path=./in_progress/vid.mp4, error contains "upload"
        """
        # Setup: create test video in watch directory
        watch_dir = setup_workflow_dirs["watch"]
        video_file = watch_dir / "vid.mp4"
        create_test_file(video_file)
        assert video_file.exists(), "Test video should exist in watch directory"
        
        # Create service with failing uploader
        repo = repo_for_sheet("Test #7", run_spreadsheet_id)
        failing_uploader = FailOnUploadFakeUploader(
            error_message="Upload failed: simulated network error"
        )
        
        service = PublishService(
            metadata_repo=repo,
            media_store=local_media_store,
            media_uploader=failing_uploader,
            max_retries=1,
            dry_run=False,
        )
        
        # Get task and process
        tasks = repo.get_ready_tasks()
        assert len(tasks) == 1, f"Expected 1 READY task in Test #7, got {len(tasks)}"
        
        result = service.publish_task(tasks[0])
        assert result == "failed", "Task should fail during upload"
        
        # Verify final state in spreadsheet
        all_tasks = read_all_rows_from_sheet("Test #7", run_spreadsheet_id)
        # Find the task we processed (task_id="1")
        task = next((t for t in all_tasks if t.task_id == "1"), None)
        assert task is not None, "Task with task_id='1' should exist"
        
        # Status should be FAILED
        assert task.status == TaskStatus.FAILED, (
            f"Expected status FAILED, got {task.status}"
        )
        
        # video_file_path should point to in_progress directory
        expected_in_progress_path = str(setup_workflow_dirs["in_progress"] / "vid.mp4")
        assert task.media_reference == expected_in_progress_path, (
            f"Expected video_file_path to be in in_progress: {expected_in_progress_path}, "
            f"got {task.media_reference}"
        )
        
        # youtube_video_id should be empty
        assert not task.platform_media_id, (
            f"youtube_video_id should be empty on failure, got {task.platform_media_id}"
        )
        
        # error_message should mention upload error
        assert task.error_message, "error_message should not be empty"
        assert "upload" in task.error_message.lower() or "Upload" in task.error_message, (
            f"error_message should mention upload error, got: {task.error_message}"
        )
        
        # Verify file is actually in in_progress directory
        in_progress_file = setup_workflow_dirs["in_progress"] / "vid.mp4"
        assert in_progress_file.exists(), (
            f"File should exist in in_progress directory: {in_progress_file}"
        )
        assert not video_file.exists(), "File should not exist in watch directory anymore"


@pytest.mark.acceptance
class TestFullWorkflowTransitionError:
    """Test #8: Transition error when file already exists in IN_PROGRESS."""

    def test_transition_error_when_file_exists(
        self, run_spreadsheet_id, setup_workflow_dirs, local_media_store
    ):
        """
        When transition to IN_PROGRESS fails because file already exists:
        - Task status should be FAILED
        - video_file_path should remain pointing to watch directory (original)
        - youtube_video_id should be empty
        - error_message should indicate transition/file error
        
        Test flow:
        1. Create vid.mp4 in both ./watch AND ./in_progress (conflict)
        2. Read task from Test #8 sheet
        3. Process - should fail during mark_in_progress
        4. Verify: status=FAILED, video_file_path=./watch/vid.mp4, error mentions file/transition
        """
        # Setup: create test video in BOTH watch and in_progress (creates conflict)
        watch_dir = setup_workflow_dirs["watch"]
        in_progress_dir = setup_workflow_dirs["in_progress"]
        
        watch_video = watch_dir / "vid.mp4"
        in_progress_video = in_progress_dir / "vid.mp4"
        
        create_test_file(watch_video)
        create_test_file(in_progress_video)  # This creates the conflict!
        
        assert watch_video.exists(), "Test video should exist in watch directory"
        assert in_progress_video.exists(), "Conflicting video should exist in in_progress"
        
        # Create service with working uploader (but it won't be reached)
        repo = repo_for_sheet("Test #8", run_spreadsheet_id)
        uploader = FakeYouTubeUploader(mode=FakeYouTubeMode.SUCCESS_PUBLIC)
        
        service = PublishService(
            metadata_repo=repo,
            media_store=local_media_store,
            media_uploader=uploader,
            max_retries=1,
            dry_run=False,
        )
        
        # Get task and process
        tasks = repo.get_ready_tasks()
        assert len(tasks) == 1, f"Expected 1 READY task in Test #8, got {len(tasks)}"
        
        result = service.publish_task(tasks[0])
        assert result == "failed", "Task should fail during transition"
        
        # Verify final state in spreadsheet
        all_tasks = read_all_rows_from_sheet("Test #8", run_spreadsheet_id)
        # Find the task we processed (task_id="1")
        task = next((t for t in all_tasks if t.task_id == "1"), None)
        assert task is not None, "Task with task_id='1' should exist"
        
        # Status should be FAILED
        assert task.status == TaskStatus.FAILED, (
            f"Expected status FAILED, got {task.status}"
        )
        
        # video_file_path should still point to watch directory (transition failed before move)
        # Note: path may have ".\" prefix from spreadsheet, so normalize for comparison
        assert "watch" in task.media_reference and "vid.mp4" in task.media_reference, (
            f"Expected video_file_path to remain in watch directory, "
            f"got {task.media_reference}"
        )
        # Ensure it's NOT in in_progress or uploaded
        assert "in_progress" not in task.media_reference, (
            f"video_file_path should NOT be in in_progress: {task.media_reference}"
        )
        assert "uploaded" not in task.media_reference, (
            f"video_file_path should NOT be in uploaded: {task.media_reference}"
        )
        
        # youtube_video_id should be empty
        assert not task.platform_media_id, (
            f"youtube_video_id should be empty on failure, got {task.platform_media_id}"
        )
        
        # error_message should mention file/transition error
        assert task.error_message, "error_message should not be empty"
        error_lower = task.error_message.lower()
        assert any(word in error_lower for word in ["file", "exists", "in_progress", "transition", "move"]), (
            f"error_message should mention file/transition error, got: {task.error_message}"
        )
        
        # Verify files still exist in their original locations
        assert watch_video.exists(), "Watch video should still exist"
        assert in_progress_video.exists(), "In-progress video should still exist"


@pytest.mark.acceptance
class TestFullWorkflowSuccess:
    """Test #9: Successful complete workflow."""

    def test_successful_workflow_updates_all_fields(
        self, run_spreadsheet_id, setup_workflow_dirs, local_media_store
    ):
        """
        When workflow completes successfully:
        - Task status should be SCHEDULED
        - video_file_path should point to UPLOADED directory
        - youtube_video_id should contain value from uploader
        - error_message should be empty
        
        Test flow:
        1. Create vid.mp4 in ./watch
        2. Read task from Test #9 sheet
        3. Process with successful uploader
        4. Verify: status=SCHEDULED, video_file_path=./uploaded/vid.mp4, 
                   youtube_video_id=fake_*, error_message empty
        """
        # Setup: create test video in watch directory
        watch_dir = setup_workflow_dirs["watch"]
        video_file = watch_dir / "vid.mp4"
        create_test_file(video_file)
        assert video_file.exists(), "Test video should exist in watch directory"
        
        # Create service with successful uploader
        repo = repo_for_sheet("Test #9", run_spreadsheet_id)
        uploader = FakeYouTubeUploader(mode=FakeYouTubeMode.SUCCESS_PUBLIC)
        
        service = PublishService(
            metadata_repo=repo,
            media_store=local_media_store,
            media_uploader=uploader,
            max_retries=1,
            dry_run=False,
        )
        
        # Get task and process
        tasks = repo.get_ready_tasks()
        assert len(tasks) == 1, f"Expected 1 READY task in Test #9, got {len(tasks)}"
        
        result = service.publish_task(tasks[0])
        assert result == "success", "Task should succeed"
        
        # Verify final state in spreadsheet
        all_tasks = read_all_rows_from_sheet("Test #9", run_spreadsheet_id)
        # Find the task we processed (task_id="1")
        task = next((t for t in all_tasks if t.task_id == "1"), None)
        assert task is not None, "Task with task_id='1' should exist"
        
        # Status should be SCHEDULED
        assert task.status == TaskStatus.SCHEDULED, (
            f"Expected status SCHEDULED, got {task.status}"
        )
        
        # video_file_path should point to uploaded directory
        expected_uploaded_path = str(setup_workflow_dirs["uploaded"] / "vid.mp4")
        assert task.media_reference == expected_uploaded_path, (
            f"Expected video_file_path in uploaded: {expected_uploaded_path}, "
            f"got {task.media_reference}"
        )
        
        # youtube_video_id should have fake value from uploader
        assert task.platform_media_id, "youtube_video_id should not be empty"
        assert task.platform_media_id.startswith("fake_"), (
            f"Expected youtube_video_id to start with 'fake_', got {task.platform_media_id}"
        )
        
        # error_message should be empty
        assert not task.error_message, (
            f"error_message should be empty on success, got: {task.error_message}"
        )
        
        # Verify file is actually in uploaded directory
        uploaded_file = setup_workflow_dirs["uploaded"] / "vid.mp4"
        assert uploaded_file.exists(), (
            f"File should exist in uploaded directory: {uploaded_file}"
        )
        assert not video_file.exists(), "File should not exist in watch directory anymore"
        
        # in_progress should be empty
        in_progress_files = list(setup_workflow_dirs["in_progress"].iterdir())
        assert len(in_progress_files) == 0, (
            f"in_progress directory should be empty, but contains: {in_progress_files}"
        )
