"""Helper utilities for LocalMediaStore acceptance tests."""
import os
from pathlib import Path


def get_workflow_dirs() -> dict[str, Path]:
    """
    Get all workflow directories from environment variables.

    Returns:
        Dict mapping stage names to Path objects.
        Keys: WATCH, IN_PROGRESS, UPLOADED
    """
    return {
        "WATCH": Path(os.getenv("VIDEO_WATCH_DIR", ".test_data/watch")),
        "IN_PROGRESS": Path(os.getenv("VIDEO_IN_PROGRESS_DIR", ".test_data/in_progress")),
        "UPLOADED": Path(os.getenv("VIDEO_UPLOADED_DIR", ".test_data/uploaded")),
    }


def reset_workflow_fs(temp_dir: Path) -> dict[str, Path]:
    """
    Create clean test directory structure under temp_dir.

    Args:
        temp_dir: Base directory for workflow folders.

    Returns:
        Dict mapping stage names to absolute Path objects.
        All directories are created if they don't exist.

    Cross-platform: works on Windows and Ubuntu.
    """
    dirs = {
        "WATCH": temp_dir / "watch",
        "IN_PROGRESS": temp_dir / "in_progress",
        "UPLOADED": temp_dir / "uploaded",
    }

    for dir_path in dirs.values():
        dir_path.mkdir(parents=True, exist_ok=True)

    return dirs


def create_test_video(dest_dir: Path, name: str, size_bytes: int = 1024) -> Path:
    """
    Create a test "video" file with random binary content.

    Args:
        dest_dir: Directory to create the file in.
        name: Filename (e.g., "test_video.mp4").
        size_bytes: Size of file content (default: 1024 bytes).

    Returns:
        Absolute path to created file.

    The file contains random bytes to simulate a real video file.
    Cross-platform: works on Windows and Ubuntu.
    """
    import random

    dest_dir.mkdir(parents=True, exist_ok=True)
    file_path = dest_dir / name

    with open(file_path, 'wb') as f:
        f.write(bytes([random.randint(0, 255) for _ in range(size_bytes)]))

    return file_path
