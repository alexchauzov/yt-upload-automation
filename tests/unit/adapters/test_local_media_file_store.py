"""Unit tests for LocalMediaFileStore adapter."""
import pytest
from pathlib import Path

from adapters.local_media_file_store import LocalMediaFileStore
from domain.models import MediaStage
from ports.adapter_error import AdapterError


@pytest.mark.unit
class TestLocalMediaFileStoreInit:
    """Tests for LocalMediaFileStore initialization."""

    def test_init_creates_stage_directories(self, tmp_path):
        """LocalMediaFileStore should create stage directories if they don't exist."""
        in_progress_dir = tmp_path / "new_in_progress"
        uploaded_dir = tmp_path / "new_uploaded"

        assert not in_progress_dir.exists()
        assert not uploaded_dir.exists()

        store = LocalMediaFileStore(
            base_path=tmp_path,
            in_progress_dir=in_progress_dir,
            uploaded_dir=uploaded_dir,
        )

        assert in_progress_dir.exists()
        assert uploaded_dir.exists()
        assert in_progress_dir.is_dir()
        assert uploaded_dir.is_dir()

    def test_init_without_stage_dirs(self, tmp_path):
        """LocalMediaFileStore can be initialized without stage directories for validation only."""
        store = LocalMediaFileStore(base_path=tmp_path)
        assert store.base_path == tmp_path
        assert len(store.stage_dirs) == 0


@pytest.mark.unit
class TestLocalMediaFileStoreValidation:
    """Tests for validation operations (exists, get_path, get_size)."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create LocalMediaFileStore instance."""
        return LocalMediaFileStore(base_path=tmp_path)

    def test_exists_returns_true_for_existing_file(self, store, tmp_path):
        """exists() should return True for existing files."""
        test_file = tmp_path / "test.mp4"
        test_file.write_text("content")

        assert store.exists(str(test_file)) is True

    def test_exists_returns_false_for_missing_file(self, store, tmp_path):
        """exists() should return False for missing files."""
        assert store.exists(str(tmp_path / "missing.mp4")) is False

    def test_exists_returns_false_for_directory(self, store, tmp_path):
        """exists() should return False for directories."""
        test_dir = tmp_path / "folder"
        test_dir.mkdir()

        assert store.exists(str(test_dir)) is False

    def test_get_path_returns_absolute_path(self, store, tmp_path):
        """get_path() should return absolute Path for existing file."""
        test_file = tmp_path / "video.mp4"
        test_file.write_text("content")

        path = store.get_path(str(test_file))

        assert isinstance(path, Path)
        assert path.is_absolute()
        assert path.exists()

    def test_get_path_raises_for_missing_file(self, store, tmp_path):
        """get_path() should raise AdapterError for missing files."""
        with pytest.raises(AdapterError) as exc_info:
            store.get_path(str(tmp_path / "missing.mp4"))

        error = exc_info.value
        assert error.code == "FILE_NOT_FOUND"
        assert "does not exist" in error.message.lower()

    def test_get_path_raises_for_directory(self, store, tmp_path):
        """get_path() should raise AdapterError for directories."""
        test_dir = tmp_path / "folder"
        test_dir.mkdir()

        with pytest.raises(AdapterError) as exc_info:
            store.get_path(str(test_dir))

        error = exc_info.value
        assert error.code == "NOT_A_FILE"
        assert "not a file" in error.message.lower()

    def test_get_size_returns_file_size(self, store, tmp_path):
        """get_size() should return file size in bytes."""
        test_file = tmp_path / "video.mp4"
        test_file.write_bytes(b"x" * 1024)

        size = store.get_size(str(test_file))

        assert size == 1024

    def test_get_size_raises_for_missing_file(self, store, tmp_path):
        """get_size() should raise AdapterError for missing files."""
        with pytest.raises(AdapterError) as exc_info:
            store.get_size(str(tmp_path / "missing.mp4"))

        error = exc_info.value
        assert error.code == "FILE_NOT_FOUND"

    def test_resolve_relative_path(self, store, tmp_path):
        """Store should resolve relative paths using base_path."""
        test_file = tmp_path / "relative.mp4"
        test_file.write_text("content")

        # Use relative path
        path = store.get_path("relative.mp4")

        assert path.is_absolute()
        assert path == test_file


@pytest.mark.unit
class TestLocalMediaFileStoreTransition:
    """Tests for workflow transition operations."""

    @pytest.fixture
    def temp_dirs(self, tmp_path):
        """Create temporary stage directories."""
        in_progress_dir = tmp_path / "in_progress"
        uploaded_dir = tmp_path / "uploaded"
        return {
            "base": tmp_path,
            "in_progress": in_progress_dir,
            "uploaded": uploaded_dir,
        }

    @pytest.fixture
    def store(self, temp_dirs):
        """Create LocalMediaFileStore instance with stage directories."""
        return LocalMediaFileStore(
            base_path=temp_dirs["base"],
            in_progress_dir=temp_dirs["in_progress"],
            uploaded_dir=temp_dirs["uploaded"],
        )

    def test_transition_in_progress_to_uploaded(self, store, temp_dirs):
        """transition() should move file from IN_PROGRESS to UPLOADED."""
        in_progress_dir = temp_dirs["in_progress"]
        uploaded_dir = temp_dirs["uploaded"]

        source_file = in_progress_dir / "test_video.mp4"
        source_file.write_text("fake video content")

        new_ref = store.transition(
            media_ref=str(source_file),
            to_stage=MediaStage.UPLOADED
        )

        assert not source_file.exists(), "Source file should be moved"
        expected_dest = uploaded_dir / "test_video.mp4"
        assert expected_dest.exists(), "File should exist in UPLOADED"
        assert new_ref == str(expected_dest)
        assert expected_dest.read_text() == "fake video content"

    def test_transition_file_not_found(self, store, temp_dirs):
        """transition() should raise AdapterError when source file doesn't exist."""
        in_progress_dir = temp_dirs["in_progress"]
        non_existent = in_progress_dir / "missing.mp4"

        with pytest.raises(AdapterError) as exc_info:
            store.transition(
                media_ref=str(non_existent),
                to_stage=MediaStage.UPLOADED
            )

        error = exc_info.value
        assert error.code == "FILE_NOT_FOUND"
        assert "not found" in error.message.lower()

    def test_transition_destination_already_exists(self, store, temp_dirs):
        """transition() should raise AdapterError when destination file exists."""
        in_progress_dir = temp_dirs["in_progress"]
        uploaded_dir = temp_dirs["uploaded"]

        source_file = in_progress_dir / "duplicate.mp4"
        source_file.write_text("source content")

        dest_file = uploaded_dir / "duplicate.mp4"
        dest_file.write_text("existing content")

        with pytest.raises(AdapterError) as exc_info:
            store.transition(
                media_ref=str(source_file),
                to_stage=MediaStage.UPLOADED
            )

        error = exc_info.value
        assert error.code == "FILE_EXISTS"
        assert "already exists" in error.message.lower()
        assert source_file.exists(), "Source should remain unchanged"
        assert dest_file.read_text() == "existing content"

    def test_transition_source_is_directory(self, store, temp_dirs):
        """transition() should raise AdapterError when source is a directory."""
        in_progress_dir = temp_dirs["in_progress"]
        source_dir = in_progress_dir / "video_folder"
        source_dir.mkdir()

        with pytest.raises(AdapterError) as exc_info:
            store.transition(
                media_ref=str(source_dir),
                to_stage=MediaStage.UPLOADED
            )

        error = exc_info.value
        assert error.code == "NOT_A_FILE"
        assert "not a file" in error.message.lower()

    def test_transition_preserves_filename(self, store, temp_dirs):
        """transition() should preserve original filename."""
        in_progress_dir = temp_dirs["in_progress"]
        uploaded_dir = temp_dirs["uploaded"]

        source_file = in_progress_dir / "my_video_final_v2.mp4"
        source_file.write_text("content")

        new_ref = store.transition(
            media_ref=str(source_file),
            to_stage=MediaStage.UPLOADED
        )

        expected_dest = uploaded_dir / "my_video_final_v2.mp4"
        assert new_ref == str(expected_dest)
        assert expected_dest.exists()
        assert expected_dest.name == "my_video_final_v2.mp4"

    def test_transition_returns_absolute_path(self, store, temp_dirs):
        """transition() should return absolute path."""
        in_progress_dir = temp_dirs["in_progress"]
        source_file = in_progress_dir / "video.mp4"
        source_file.write_text("content")

        new_ref = store.transition(
            media_ref=str(source_file),
            to_stage=MediaStage.UPLOADED
        )

        new_path = Path(new_ref)
        assert new_path.is_absolute()
        assert new_path.exists()

    def test_transition_stage_not_configured(self, tmp_path):
        """transition() should raise AdapterError if stage directory not configured."""
        store = LocalMediaFileStore(base_path=tmp_path)
        test_file = tmp_path / "test.mp4"
        test_file.write_text("content")

        with pytest.raises(AdapterError) as exc_info:
            store.transition(
                media_ref=str(test_file),
                to_stage=MediaStage.UPLOADED
            )

        error = exc_info.value
        assert error.code == "STAGE_NOT_CONFIGURED"
        assert "not configured" in error.message.lower()
