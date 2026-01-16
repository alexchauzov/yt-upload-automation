"""Domain models for media publishing."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TaskStatus(str, Enum):
    """Task status."""
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
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
class Task:
    """
    Media publishing task from metadata source.

    Represents a single media item to be published with all necessary metadata.
    Domain-agnostic: works with any media type (video, image, text, etc.)
    """
    # Required fields (no defaults)
    task_id: str
    row_index: int  # Position in metadata source (e.g., Google Sheets row)
    media_reference: str  # Abstract media reference (not a concrete path)
    title: str

    # Optional fields (with defaults)
    # Media content
    thumbnail_reference: Optional[str] = None  # Abstract reference to thumbnail

    # Platform-specific metadata (domain doesn't interpret these)
    description: str = ""
    tags: list[str] = field(default_factory=list)
    category_id: str = "22"  # Default: People & Blogs

    # Publishing schedule
    publish_at: Optional[datetime] = None
    privacy_status: PrivacyStatus = PrivacyStatus.PRIVATE

    # Task status
    status: TaskStatus = TaskStatus.READY
    platform_media_id: Optional[str] = None  # Platform-specific media ID (e.g., YouTube video ID)
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
    Result of a media publishing operation.

    Contains information about the uploaded media and its scheduled publishing time.
    """
    success: bool
    media_id: Optional[str] = None  # Platform-specific media ID
    status: Optional[TaskStatus] = None
    publish_at: Optional[datetime] = None
    error_message: Optional[str] = None

    # Additional metadata
    upload_time: Optional[datetime] = None
    thumbnail_uploaded: bool = False
