"""Unit tests for LocalMediaStore adapter."""
import pytest
from pathlib import Path

from adapters.local_media_store import LocalMediaStore
from domain.models import MediaStage
from ports.adapter_error import AdapterError


@pytest.mark.unit
class TestLocalMediaStore:
    """Tests for LocalMediaStore filesystem adapter."""

    @pytest.fixture
    def temp_dirs(self, tmp_path):
        """Create temporary stage directories."""
        in_progress_dir = tmp_path / "in_progress"
        uploaded_dir = tmp_path / "uploaded"
        return {
            "in_progress": in_progress_dir,
            "uploaded": uploaded_dir,
        }

    @pytest.fixture
    def media_store(self, temp_dirs):
        """Create LocalMediaStore instance with temp directories."""
        return LocalMediaStore(
            in_progress_dir=temp_dirs["in_progress"],
            uploaded_dir=temp_dirs["uploaded"],
        )

    def test_init_creates_directories(self, tmp_path):
        """LocalMediaStore should create stage directories if they don't exist."""
        in_progress_dir = tmp_path / "new_in_progress"
        uploaded_dir = tmp_path / "new_uploaded"

        assert not in_progress_dir.exists()
        assert not uploaded_dir.exists()

        store = LocalMediaStore(
            in_progress_dir=in_progress_dir,
            uploaded_dir=uploaded_dir,
        )

        assert in_progress_dir.exists()
        assert uploaded_dir.exists()
        assert in_progress_dir.is_dir()
        assert uploaded_dir.is_dir()

    def test_transition_in_progress_to_uploaded(self, media_store, temp_dirs):
        """Transition should move file from IN_PROGRESS to UPLOADED."""
        in_progress_dir = temp_dirs["in_progress"]
        uploaded_dir = temp_dirs["uploaded"]

        source_file = in_progress_dir / "test_video.mp4"
        source_file.write_text("fake video content")

        new_ref = media_store.transition(
            media_ref=str(source_file),
            to_stage=MediaStage.UPLOADED
        )

        assert not source_file.exists(), "Source file should be moved"
        expected_dest = uploaded_dir / "test_video.mp4"
        assert expected_dest.exists(), "File should exist in UPLOADED"
        assert new_ref == str(expected_dest)
        assert expected_dest.read_text() == "fake video content"

    def test_transition_file_not_found(self, media_store, temp_dirs):
        """Transition should raise AdapterError when source file doesn't exist."""
        in_progress_dir = temp_dirs["in_progress"]
        non_existent = in_progress_dir / "missing.mp4"

        with pytest.raises(AdapterError) as exc_info:
            media_store.transition(
                media_ref=str(non_existent),
                to_stage=MediaStage.UPLOADED
            )

        error = exc_info.value
        assert error.code == "FILE_NOT_FOUND"
        assert "missing.mp4" in error.message or str(non_existent) in error.message
        assert "source_path" in error.details

    def test_transition_destination_already_exists(self, media_store, temp_dirs):
        """Transition should raise AdapterError when destination file exists."""
        in_progress_dir = temp_dirs["in_progress"]
        uploaded_dir = temp_dirs["uploaded"]

        source_file = in_progress_dir / "duplicate.mp4"
        source_file.write_text("source content")

        dest_file = uploaded_dir / "duplicate.mp4"
        dest_file.write_text("existing content")

        with pytest.raises(AdapterError) as exc_info:
            media_store.transition(
                media_ref=str(source_file),
                to_stage=MediaStage.UPLOADED
            )

        error = exc_info.value
        assert error.code == "FILE_EXISTS"
        assert "already exists" in error.message.lower()
        assert "dest_path" in error.details
        assert source_file.exists(), "Source should remain unchanged"
        assert dest_file.read_text() == "existing content", "Dest should be unchanged"

    def test_transition_source_is_directory(self, media_store, temp_dirs):
        """Transition should raise AdapterError when source is a directory."""
        in_progress_dir = temp_dirs["in_progress"]
        source_dir = in_progress_dir / "video_folder"
        source_dir.mkdir()

        with pytest.raises(AdapterError) as exc_info:
            media_store.transition(
                media_ref=str(source_dir),
                to_stage=MediaStage.UPLOADED
            )

        error = exc_info.value
        assert error.code == "NOT_A_FILE"
        assert "not a file" in error.message.lower()

    def test_transition_preserves_filename(self, media_store, temp_dirs):
        """Transition should preserve original filename."""
        in_progress_dir = temp_dirs["in_progress"]
        uploaded_dir = temp_dirs["uploaded"]

        source_file = in_progress_dir / "my_video_final_v2.mp4"
        source_file.write_text("content")

        new_ref = media_store.transition(
            media_ref=str(source_file),
            to_stage=MediaStage.UPLOADED
        )

        expected_dest = uploaded_dir / "my_video_final_v2.mp4"
        assert new_ref == str(expected_dest)
        assert expected_dest.exists()
        assert expected_dest.name == "my_video_final_v2.mp4"

    def test_transition_returns_absolute_path(self, media_store, temp_dirs):
        """Transition should return absolute path even if relative path given."""
        in_progress_dir = temp_dirs["in_progress"]
        source_file = in_progress_dir / "video.mp4"
        source_file.write_text("content")

        new_ref = media_store.transition(
            media_ref=str(source_file),
            to_stage=MediaStage.UPLOADED
        )

        new_path = Path(new_ref)
        assert new_path.is_absolute()
        assert new_path.exists()
