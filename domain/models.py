"""Domain models for YouTube publishing."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TaskStatus(str, Enum):
    """Video task status."""
    READY = "READY"
    UPLOADING = "UPLOADING"
    SCHEDULED = "SCHEDULED"
    FAILED = "FAILED"
    VALIDATED = "VALIDATED"
    DRY_RUN_OK = "DRY_RUN_OK"


class PrivacyStatus(str, Enum):
    """YouTube video privacy status."""
    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"


class MediaStage(str, Enum):
    """Media file workflow stage."""
    IN_PROGRESS = "IN_PROGRESS"
    UPLOADED = "UPLOADED"


class TaskOutcome(str, Enum):
    """Task processing outcome."""
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"


@dataclass
class VideoTask:
    """
    Video publishing task from metadata source.

    Represents a single video to be uploaded to YouTube with all necessary metadata.
    """
    # Required fields (no defaults)
    task_id: str
    row_index: int  # Position in metadata source (e.g., Google Sheets row)
    video_file_path: str
    title: str

    # Optional fields (with defaults)
    # Video content
    thumbnail_path: Optional[str] = None

    # YouTube metadata
    description: str = ""
    tags: list[str] = field(default_factory=list)
    category_id: str = "22"  # Default: People & Blogs

    # Publishing schedule
    publish_at: Optional[datetime] = None
    privacy_status: PrivacyStatus = PrivacyStatus.PRIVATE

    # Task status
    status: TaskStatus = TaskStatus.READY
    youtube_video_id: Optional[str] = None
    error_message: Optional[str] = None

    # Retry tracking
    attempts: int = 0
    last_attempt_at: Optional[datetime] = None

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        """Convert string enums to proper enum types."""
        if isinstance(self.status, str):
            self.status = TaskStatus(self.status)
        if isinstance(self.privacy_status, str):
            self.privacy_status = PrivacyStatus(self.privacy_status)


@dataclass
class PublishResult:
    """
    Result of a video publishing operation.

    Contains information about the uploaded video and its scheduled publishing time.
    """
    success: bool
    video_id: Optional[str] = None
    status: Optional[TaskStatus] = None
    publish_at: Optional[datetime] = None
    error_message: Optional[str] = None

    # Additional metadata
    upload_time: Optional[datetime] = None
    thumbnail_uploaded: bool = False
