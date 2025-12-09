"""
Unit tests for CLI upload_video module.

Tests command-line argument parsing and uploader invocation.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.cli import upload_video


class FakeYouTubeUploader:
    """Fake YouTubeUploader for testing."""

    def __init__(self, config=None):
        self.config = config
        self.upload_calls = []

    def upload_video(self, file_path, title, description="", tags=None, privacy_status="unlisted"):
        """Record the call and return fake video ID."""
        self.upload_calls.append({
            "file_path": file_path,
            "title": title,
            "description": description,
            "tags": tags,
            "privacy_status": privacy_status
        })
        return "TEST_VIDEO_ID"


def test_parse_args_minimal():
    """Test parsing minimal required arguments."""
    args = upload_video.parse_args(["--file", "test.mp4", "--title", "Test Title"])

    assert args.file == "test.mp4"
    assert args.title == "Test Title"
    assert args.description == ""
    assert args.tags is None
    assert args.privacy_status == "unlisted"


def test_parse_args_full():
    """Test parsing all arguments."""
    args = upload_video.parse_args([
        "--file", "video.mp4",
        "--title", "Full Title",
        "--description", "Full Description",
        "--tags", "tag1,tag2,tag3",
        "--privacy-status", "public"
    ])

    assert args.file == "video.mp4"
    assert args.title == "Full Title"
    assert args.description == "Full Description"
    assert args.tags == "tag1,tag2,tag3"
    assert args.privacy_status == "public"


def test_parse_args_privacy_status_choices():
    """Test that privacy-status only accepts valid choices."""
    # Valid choices
    for status in ["public", "unlisted", "private"]:
        args = upload_video.parse_args(["--file", "test.mp4", "--title", "Test", "--privacy-status", status])
        assert args.privacy_status == status

    # Invalid choice should raise SystemExit
    with pytest.raises(SystemExit):
        upload_video.parse_args(["--file", "test.mp4", "--title", "Test", "--privacy-status", "invalid"])


def test_main_basic_upload(monkeypatch, capsys):
    """Test main() with basic upload parameters."""
    fake_uploader = FakeYouTubeUploader()

    # Mock get_config to return a fake config
    mock_config = Mock()
    monkeypatch.setattr("src.cli.upload_video.get_config", lambda: mock_config)

    # Mock YouTubeUploader to return our fake
    monkeypatch.setattr("src.cli.upload_video.YouTubeUploader", lambda config: fake_uploader)

    # Run main with test arguments
    upload_video.main([
        "--file", "test.mp4",
        "--title", "Test Video"
    ])

    # Verify upload was called
    assert len(fake_uploader.upload_calls) == 1
    call = fake_uploader.upload_calls[0]

    assert call["file_path"] == "test.mp4"
    assert call["title"] == "Test Video"
    assert call["description"] == ""
    assert call["tags"] is None
    assert call["privacy_status"] == "unlisted"

    # Verify output
    captured = capsys.readouterr()
    assert "Uploaded video successfully. id=TEST_VIDEO_ID" in captured.out
    assert "https://youtube.com/watch?v=TEST_VIDEO_ID" in captured.out


def test_main_full_parameters(monkeypatch, capsys):
    """Test main() with all parameters including tags."""
    fake_uploader = FakeYouTubeUploader()

    # Mock get_config
    mock_config = Mock()
    monkeypatch.setattr("src.cli.upload_video.get_config", lambda: mock_config)

    # Mock YouTubeUploader
    monkeypatch.setattr("src.cli.upload_video.YouTubeUploader", lambda config: fake_uploader)

    # Run main with full arguments
    upload_video.main([
        "--file", "video.mp4",
        "--title", "Full Video",
        "--description", "Full description",
        "--tags", "a,b,c",
        "--privacy-status", "public"
    ])

    # Verify upload was called with correct parameters
    assert len(fake_uploader.upload_calls) == 1
    call = fake_uploader.upload_calls[0]

    assert call["file_path"] == "video.mp4"
    assert call["title"] == "Full Video"
    assert call["description"] == "Full description"
    assert call["tags"] == ["a", "b", "c"]
    assert call["privacy_status"] == "public"


def test_main_tags_with_spaces(monkeypatch, capsys):
    """Test that tags are properly stripped of whitespace."""
    fake_uploader = FakeYouTubeUploader()

    mock_config = Mock()
    monkeypatch.setattr("src.cli.upload_video.get_config", lambda: mock_config)
    monkeypatch.setattr("src.cli.upload_video.YouTubeUploader", lambda config: fake_uploader)

    # Run with tags that have extra spaces
    upload_video.main([
        "--file", "test.mp4",
        "--title", "Test",
        "--tags", "tag1 , tag2  ,  tag3"
    ])

    call = fake_uploader.upload_calls[0]
    assert call["tags"] == ["tag1", "tag2", "tag3"]


def test_main_file_not_found_error(monkeypatch, capsys):
    """Test that FileNotFoundError is handled properly."""
    mock_config = Mock()
    monkeypatch.setattr("src.cli.upload_video.get_config", lambda: mock_config)

    # Mock uploader to raise FileNotFoundError
    def mock_uploader_class(config):
        uploader = Mock()
        uploader.upload_video.side_effect = FileNotFoundError("File not found: test.mp4")
        return uploader

    monkeypatch.setattr("src.cli.upload_video.YouTubeUploader", mock_uploader_class)

    # Should exit with code 1
    with pytest.raises(SystemExit) as exc_info:
        upload_video.main([
            "--file", "nonexistent.mp4",
            "--title", "Test"
        ])

    assert exc_info.value.code == 1

    # Verify error message
    captured = capsys.readouterr()
    assert "Error:" in captured.err
    assert "File not found" in captured.err


def test_main_value_error(monkeypatch, capsys):
    """Test that ValueError is handled properly."""
    mock_config = Mock()
    monkeypatch.setattr("src.cli.upload_video.get_config", lambda: mock_config)

    # Mock uploader to raise ValueError
    def mock_uploader_class(config):
        uploader = Mock()
        uploader.upload_video.side_effect = ValueError("Invalid privacy status")
        return uploader

    monkeypatch.setattr("src.cli.upload_video.YouTubeUploader", mock_uploader_class)

    # Should exit with code 1
    with pytest.raises(SystemExit) as exc_info:
        upload_video.main([
            "--file", "test.mp4",
            "--title", "Test"
        ])

    assert exc_info.value.code == 1

    # Verify error message
    captured = capsys.readouterr()
    assert "Error:" in captured.err
