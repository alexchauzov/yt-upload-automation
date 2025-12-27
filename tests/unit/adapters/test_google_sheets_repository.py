"""Unit tests for GoogleSheetsMetadataRepository column flexibility."""
import pytest
from unittest.mock import Mock, MagicMock, patch

from adapters.google_sheets_repository import GoogleSheetsMetadataRepository
from ports.metadata_repository import MetadataRepositoryError


class TestGoogleSheetsRepositoryHeaderMapping:
    """Tests for header-based column mapping."""

    @pytest.fixture
    def mock_credentials(self):
        """Mock the Google credentials and service."""
        with patch(
            "adapters.google_sheets_repository.service_account.Credentials.from_service_account_file"
        ) as mock_creds, patch(
            "adapters.google_sheets_repository.build"
        ) as mock_build:
            mock_creds.return_value = Mock()
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            yield mock_service

    def test_get_ready_tasks_with_reordered_columns(self, mock_credentials):
        """
        Test that get_ready_tasks() correctly parses data when columns are reordered.

        The header row has columns in a different order than COLUMN_MAP:
        status, title, task_id, video_file_path, description, tags
        """
        # Arrange: columns in non-standard order
        header = [
            "status",
            "title",
            "task_id",
            "video_file_path",
            "description",
            "tags",
            "privacy_status",
        ]
        # Data row with values in the same (reordered) positions
        data_row = [
            "READY",            # status (index 0)
            "My Test Video",    # title (index 1)
            "vid_001",          # task_id (index 2)
            "/videos/test.mp4", # video_file_path (index 3)
            "Test description", # description (index 4)
            "tag1,tag2",        # tags (index 5)
            "private",          # privacy_status (index 6)
        ]

        mock_values = MagicMock()
        mock_values.get.return_value.execute.return_value = {
            "values": [header, data_row]
        }
        mock_credentials.spreadsheets.return_value.values.return_value = mock_values

        repo = GoogleSheetsMetadataRepository(
            spreadsheet_id="test_id",
            range_name="Videos!A:Z",
            credentials_path="fake_creds.json",
            ready_status="READY",
        )

        # Act
        tasks = repo.get_ready_tasks()

        # Assert
        assert len(tasks) == 1
        task = tasks[0]
        assert task.task_id == "vid_001"
        assert task.title == "My Test Video"
        assert task.video_file_path == "/videos/test.mp4"
        assert task.description == "Test description"
        assert task.tags == ["tag1", "tag2"]
        assert task.status.value == "READY"
        assert task.row_index == 2  # Row 2 (1-indexed, row 1 is header)

    def test_get_ready_tasks_with_shuffled_columns_all_fields(self, mock_credentials):
        """
        Test parsing with all fields in completely shuffled order.
        """
        # Arrange: completely shuffled column order with all columns present
        header = [
            "youtube_video_id",  # 0
            "error_message",     # 1
            "status",            # 2
            "video_file_path",   # 3
            "task_id",           # 4
            "title",             # 5
            "attempts",          # 6
            "category_id",       # 7
            "description",       # 8
            "privacy_status",    # 9
            "tags",              # 10
            "thumbnail_path",    # 11
            "publish_at",        # 12
            "last_attempt_at",   # 13
            "created_at",        # 14
            "updated_at",        # 15
        ]
        data_row = [
            "",                  # youtube_video_id
            "",                  # error_message
            "READY",             # status
            "/path/to/video.mp4",# video_file_path
            "task_123",          # task_id
            "Shuffled Title",    # title
            "2",                 # attempts
            "27",                # category_id
            "Shuffled desc",     # description
            "private",           # privacy_status
            "tag1,tag2",         # tags
            "",                  # thumbnail_path
            "",                  # publish_at
            "",                  # last_attempt_at
            "",                  # created_at
            "",                  # updated_at
        ]

        mock_values = MagicMock()
        mock_values.get.return_value.execute.return_value = {
            "values": [header, data_row]
        }
        mock_credentials.spreadsheets.return_value.values.return_value = mock_values

        repo = GoogleSheetsMetadataRepository(
            spreadsheet_id="test_id",
            range_name="Videos!A:Z",
            credentials_path="fake_creds.json",
            ready_status="READY",
        )

        # Act
        tasks = repo.get_ready_tasks()

        # Assert
        assert len(tasks) == 1
        task = tasks[0]
        assert task.task_id == "task_123"
        assert task.title == "Shuffled Title"
        assert task.video_file_path == "/path/to/video.mp4"
        assert task.description == "Shuffled desc"
        assert task.category_id == "27"
        assert task.attempts == 2
        assert task.tags == ["tag1", "tag2"]

    def test_get_ready_tasks_missing_required_column_raises_error(self, mock_credentials):
        """
        Test that missing required column (video_file_path) raises MetadataRepositoryError.
        """
        # Arrange: header is valid but missing video_file_path
        header = ["task_id", "status", "title", "description"]
        data_row = ["vid_001", "READY", "Test Title", "Some description"]

        mock_values = MagicMock()
        mock_values.get.return_value.execute.return_value = {
            "values": [header, data_row]
        }
        mock_credentials.spreadsheets.return_value.values.return_value = mock_values

        repo = GoogleSheetsMetadataRepository(
            spreadsheet_id="test_id",
            range_name="Videos!A:Z",
            credentials_path="fake_creds.json",
            ready_status="READY",
        )

        # Act & Assert
        with pytest.raises(MetadataRepositoryError) as exc_info:
            repo.get_ready_tasks()

        error_msg = str(exc_info.value)
        assert "Missing required columns" in error_msg
        assert "video_file_path" in error_msg
        assert "found columns" in error_msg

    def test_get_ready_tasks_missing_multiple_required_columns(self, mock_credentials):
        """
        Test that missing multiple required columns are all listed in error.
        """
        # Arrange: header only has task_id and description
        header = ["task_id", "description"]
        data_row = ["vid_001", "Some description"]

        mock_values = MagicMock()
        mock_values.get.return_value.execute.return_value = {
            "values": [header, data_row]
        }
        mock_credentials.spreadsheets.return_value.values.return_value = mock_values

        repo = GoogleSheetsMetadataRepository(
            spreadsheet_id="test_id",
            range_name="Videos!A:Z",
            credentials_path="fake_creds.json",
            ready_status="READY",
        )

        # Act & Assert
        with pytest.raises(MetadataRepositoryError) as exc_info:
            repo.get_ready_tasks()

        error_msg = str(exc_info.value)
        assert "Missing required columns" in error_msg
        assert "status" in error_msg
        assert "title" in error_msg
        assert "video_file_path" in error_msg

    def test_get_ready_tasks_fallback_to_column_map_on_invalid_header(self, mock_credentials):
        """
        Test that COLUMN_MAP fallback is used when header doesn't contain expected columns.
        """
        # Arrange: header with unrecognized column names -> fallback to COLUMN_MAP
        header = ["unknown1", "unknown2", "unknown3"]
        # Data in COLUMN_MAP order: task_id(0), status(1), title(2), video_file_path(3)
        data_row = ["vid_001", "READY", "Fallback Title", "/videos/fallback.mp4"]

        mock_values = MagicMock()
        mock_values.get.return_value.execute.return_value = {
            "values": [header, data_row]
        }
        mock_credentials.spreadsheets.return_value.values.return_value = mock_values

        repo = GoogleSheetsMetadataRepository(
            spreadsheet_id="test_id",
            range_name="Videos!A:Z",
            credentials_path="fake_creds.json",
            ready_status="READY",
        )

        # Act
        tasks = repo.get_ready_tasks()

        # Assert - should parse using COLUMN_MAP positions
        assert len(tasks) == 1
        task = tasks[0]
        assert task.task_id == "vid_001"
        assert task.title == "Fallback Title"
        assert task.video_file_path == "/videos/fallback.mp4"

    def test_get_ready_tasks_header_with_extra_whitespace(self, mock_credentials):
        """
        Test that header names with extra whitespace are normalized correctly.
        """
        # Arrange: header with spaces around names
        header = [
            "  task_id  ",
            " status",
            "title ",
            "  video_file_path",
        ]
        data_row = ["vid_001", "READY", "Whitespace Test", "/videos/ws.mp4"]

        mock_values = MagicMock()
        mock_values.get.return_value.execute.return_value = {
            "values": [header, data_row]
        }
        mock_credentials.spreadsheets.return_value.values.return_value = mock_values

        repo = GoogleSheetsMetadataRepository(
            spreadsheet_id="test_id",
            range_name="Videos!A:Z",
            credentials_path="fake_creds.json",
            ready_status="READY",
        )

        # Act
        tasks = repo.get_ready_tasks()

        # Assert
        assert len(tasks) == 1
        task = tasks[0]
        assert task.task_id == "vid_001"
        assert task.title == "Whitespace Test"

    def test_get_ready_tasks_header_case_insensitive(self, mock_credentials):
        """
        Test that header names are case-insensitive.
        """
        # Arrange: mixed case headers
        header = ["TASK_ID", "Status", "TITLE", "Video_File_Path"]
        data_row = ["vid_001", "READY", "Case Test", "/videos/case.mp4"]

        mock_values = MagicMock()
        mock_values.get.return_value.execute.return_value = {
            "values": [header, data_row]
        }
        mock_credentials.spreadsheets.return_value.values.return_value = mock_values

        repo = GoogleSheetsMetadataRepository(
            spreadsheet_id="test_id",
            range_name="Videos!A:Z",
            credentials_path="fake_creds.json",
            ready_status="READY",
        )

        # Act
        tasks = repo.get_ready_tasks()

        # Assert
        assert len(tasks) == 1
        task = tasks[0]
        assert task.task_id == "vid_001"
        assert task.title == "Case Test"

    def test_get_ready_tasks_empty_sheet(self, mock_credentials):
        """
        Test handling of empty sheet.
        """
        mock_values = MagicMock()
        mock_values.get.return_value.execute.return_value = {"values": []}
        mock_credentials.spreadsheets.return_value.values.return_value = mock_values

        repo = GoogleSheetsMetadataRepository(
            spreadsheet_id="test_id",
            range_name="Videos!A:Z",
            credentials_path="fake_creds.json",
        )

        # Act
        tasks = repo.get_ready_tasks()

        # Assert
        assert tasks == []

    def test_get_ready_tasks_filters_by_ready_status(self, mock_credentials):
        """
        Test that only rows with READY status are returned.
        """
        header = ["task_id", "status", "title", "video_file_path"]
        rows = [
            header,
            ["vid_001", "READY", "Ready Video", "/videos/ready.mp4"],
            ["vid_002", "SCHEDULED", "Scheduled Video", "/videos/sched.mp4"],
            ["vid_003", "FAILED", "Failed Video", "/videos/fail.mp4"],
            ["vid_004", "READY", "Another Ready", "/videos/ready2.mp4"],
        ]

        mock_values = MagicMock()
        mock_values.get.return_value.execute.return_value = {"values": rows}
        mock_credentials.spreadsheets.return_value.values.return_value = mock_values

        repo = GoogleSheetsMetadataRepository(
            spreadsheet_id="test_id",
            range_name="Videos!A:Z",
            credentials_path="fake_creds.json",
            ready_status="READY",
        )

        # Act
        tasks = repo.get_ready_tasks()

        # Assert
        assert len(tasks) == 2
        assert tasks[0].task_id == "vid_001"
        assert tasks[1].task_id == "vid_004"

