"""Google Sheets metadata repository implementation."""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, List

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from domain.models import PrivacyStatus, Task, TaskStatus
from ports.metadata_repository import (
    MetadataRepository,
    MetadataRepositoryError,
    ValidationError,
)

logger = logging.getLogger(__name__)


class GoogleSheetsMetadataRepository(MetadataRepository):
    """
    Google Sheets implementation of MetadataRepository.

    Uses Google Sheets API v4 with service account authentication.
    Column order is flexible - the first row should contain header names.
    """

    # Column mapping (0-indexed) - fallback when header is missing/invalid
    COLUMN_MAP = {
        "task_id": 0,
        "status": 1,
        "title": 2,
        "video_file_path": 3,
        "description": 4,
        "tags": 5,
        "category_id": 6,
        "thumbnail_path": 7,
        "publish_at": 8,
        "privacy_status": 9,
        "youtube_video_id": 10,
        "error_message": 11,
        "attempts": 12,
        "last_attempt_at": 13,
        "created_at": 14,
        "updated_at": 15,
    }

    # Expected header names (normalized: strip + lowercase)
    EXPECTED_HEADERS = {
        "task_id", "status", "title", "video_file_path", "description", "tags",
        "category_id", "thumbnail_path", "publish_at", "privacy_status",
        "youtube_video_id", "error_message", "attempts", "last_attempt_at",
        "created_at", "updated_at",
    }

    # Required columns when using header-based mapping
    REQUIRED_COLUMNS = {"task_id", "video_file_path", "title", "description", "publish_at", "status", "youtube_video_id", "error_message"}

    def __init__(
        self,
        spreadsheet_id: str | None = None,
        range_name: str | None = None,
        credentials_path: str | None = None,
        ready_status: str = "READY",
    ):
        """
        Initialize Google Sheets repository.

        Args:
            spreadsheet_id: Google Sheets ID (from URL). If None, read from env.
            range_name: Sheet range (e.g., 'Videos!A:Z'). If None, read from env.
            credentials_path: Path to service account JSON. If None, read from env.
            ready_status: Status value to filter for ready tasks.

        Raises:
            MetadataRepositoryError: If configuration is invalid.
        """
        self.spreadsheet_id = spreadsheet_id or os.getenv("GOOGLE_SHEETS_ID")
        self.range_name = range_name or os.getenv("GOOGLE_SHEETS_RANGE", "Videos!A:Z")
        self.ready_status = ready_status or os.getenv("SHEETS_READY_STATUS", "READY")

        credentials_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        if not self.spreadsheet_id:
            raise MetadataRepositoryError(
                "GOOGLE_SHEETS_ID not configured. Set environment variable or pass to constructor."
            )

        if not credentials_path:
            raise MetadataRepositoryError(
                "GOOGLE_APPLICATION_CREDENTIALS not configured. "
                "Set environment variable or pass to constructor."
            )

        # Initialize Google Sheets API client
        try:
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=["https://www.googleapis.com/auth/spreadsheets"],
            )
            self.service = build("sheets", "v4", credentials=credentials)
            self._header_map = None
            logger.info(
                f"GoogleSheetsMetadataRepository initialized: "
                f"spreadsheet_id={self.spreadsheet_id}, range={self.range_name}"
            )
        except Exception as e:
            raise MetadataRepositoryError(f"Failed to initialize Google Sheets client: {e}") from e

    def get_ready_tasks(self) -> List[Task]:
        """
        Fetch all tasks with configured ready status.

        Returns:
            List of VideoTask objects.

        Raises:
            MetadataRepositoryError: If fetching fails or required columns missing.
        """
        try:
            logger.info(f"Fetching tasks with status={self.ready_status}")

            # Read all rows from sheet
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range=self.range_name)
                .execute()
            )

            rows = result.get("values", [])

            if not rows:
                logger.warning("Sheet is empty")
                return []

            # First row is header, skip it
            header = rows[0]
            data_rows = rows[1:]

            # Build header_map from first row (normalized: strip + lowercase)
            header_map = self._build_header_map(header)

            # Cache header_map for use in write operations
            self._header_map = header_map

            # Determine padding length based on header_map or COLUMN_MAP
            if header_map is not None:
                pad_length = max(header_map.values()) + 1 if header_map else 0
            else:
                pad_length = len(self.COLUMN_MAP)

            logger.debug(f"Found {len(data_rows)} data rows (excluding header)")

            tasks = []
            for row_index, row in enumerate(data_rows, start=2):  # Start at 2 (1 is header)
                try:
                    # Pad row to expected length
                    current_len = len(row)
                    if current_len < pad_length:
                        padded_row = row + [""] * (pad_length - current_len)
                    else:
                        padded_row = row

                    # Check if row has ready status
                    status = self._get_cell(padded_row, "status", header_map=header_map)
                    if status != self.ready_status:
                        continue

                    # Parse row into VideoTask
                    task = self._parse_row(padded_row, row_index, header_map=header_map)
                    tasks.append(task)

                except ValidationError as e:
                    # Mark row as failed and continue
                    logger.error(f"Row {row_index} validation failed: {e}")
                    self._mark_row_failed(row_index, str(e))

                except Exception as e:
                    logger.exception(f"Unexpected error parsing row {row_index}: {e}")

            logger.info(f"Found {len(tasks)} tasks with status={self.ready_status}")
            return tasks

        except HttpError as e:
            raise MetadataRepositoryError(f"Google Sheets API error: {e}") from e
        except MetadataRepositoryError:
            raise
        except Exception as e:
            raise MetadataRepositoryError(f"Failed to fetch tasks: {e}") from e

    def _build_header_map(self, header: List[str]) -> dict[str, int] | None:
        """
        Build header_map from header row.

        Args:
            header: First row of the sheet (header names).

        Returns:
            Dict mapping normalized column names to indices, or None if header invalid.

        Raises:
            MetadataRepositoryError: If header is valid but missing required columns.
        """
        if not header:
            logger.debug("Header is empty, using COLUMN_MAP fallback")
            return None

        # Build header_map with normalized names (strip + lowercase)
        header_map: dict[str, int] = {}
        for idx, cell in enumerate(header):
            normalized = cell.strip().lower()
            if normalized:
                header_map[normalized] = idx

        # Check if header contains at least one expected column name
        found_expected = header_map.keys() & self.EXPECTED_HEADERS
        if not found_expected:
            logger.debug("Header does not contain any expected columns, using COLUMN_MAP fallback")
            return None

        logger.debug(f"Using header-based mapping, found columns: {sorted(found_expected)}")

        # Validate required columns are present
        missing_required = self.REQUIRED_COLUMNS - header_map.keys()
        if missing_required:
            found_cols = sorted(header_map.keys() & self.EXPECTED_HEADERS)
            raise MetadataRepositoryError(
                f"Missing required columns: {sorted(missing_required)}; found columns: {found_cols}"
            )

        return header_map

    def _ensure_header_map(self) -> None:
        """
        Ensure header_map is loaded. Fetch from sheet if not cached.

        Raises:
            MetadataRepositoryError: If fetching header fails.
        """
        if self._header_map is not None:
            return

        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range=self.range_name, majorDimension="ROWS")
                .execute()
            )

            rows = result.get("values", [])
            if not rows:
                logger.warning("Sheet is empty, using COLUMN_MAP fallback for writes")
                self._header_map = None
                return

            header = rows[0]
            self._header_map = self._build_header_map(header)

        except HttpError as e:
            raise MetadataRepositoryError(f"Failed to fetch header: {e}") from e
        except Exception as e:
            raise MetadataRepositoryError(f"Failed to ensure header_map: {e}") from e

    def _get_column_index(self, column_name: str) -> int:
        """
        Get column index by name, using header_map if available, otherwise COLUMN_MAP.

        Args:
            column_name: Column name to look up.

        Returns:
            Column index (0-indexed).

        Raises:
            MetadataRepositoryError: If column not found.
        """
        self._ensure_header_map()

        normalized_name = column_name.strip().lower()

        if self._header_map is not None and normalized_name in self._header_map:
            return self._header_map[normalized_name]

        if column_name in self.COLUMN_MAP:
            return self.COLUMN_MAP[column_name]

        raise MetadataRepositoryError(
            f"Column '{column_name}' not found in header_map or COLUMN_MAP"
        )

    def update_task_status(
        self,
        task: Task,
        status: str,
        youtube_video_id: str | None = None,
        error_message: str | None = None,
        video_file_path: str | None = None,
    ) -> None:
        """
        Update task status and related fields.

        Translates domain status IN_PROGRESS to UPLOADING for user visibility in spreadsheet.

        Args:
            task: Task to update.
            status: New status value (domain status, e.g., IN_PROGRESS).
            youtube_video_id: Platform media ID if uploaded (stored in youtube_video_id column).
            error_message: Error message if failed.
            video_file_path: Updated media reference (stored in video_file_path column).

        Raises:
            MetadataRepositoryError: If update fails.
        """
        try:
            row_index = task.row_index
            
            # Translate IN_PROGRESS to UPLOADING for spreadsheet visibility
            # UPLOADING is just a display label, not a domain status
            display_status = status
            if status == TaskStatus.IN_PROGRESS.value:
                display_status = "UPLOADING"
                logger.debug(f"Translating domain status IN_PROGRESS to UPLOADING for row {row_index}")
            
            logger.info(f"Updating row {row_index}: status={display_status} (domain: {status})")

            updates = []

            # Status column (use display status for spreadsheet)
            status_col_idx = self._get_column_index("status")
            status_col = self._column_letter(status_col_idx)
            updates.append({
                "range": f"{self._sheet_name()}!{status_col}{row_index}",
                "values": [[display_status]],
            })

            # Platform media ID (stored in youtube_video_id column for backward compatibility)
            if youtube_video_id is not None:
                video_id_col_idx = self._get_column_index("youtube_video_id")
                video_id_col = self._column_letter(video_id_col_idx)
                updates.append({
                    "range": f"{self._sheet_name()}!{video_id_col}{row_index}",
                    "values": [[youtube_video_id]],
                })

            # Error message
            if error_message is not None:
                error_col_idx = self._get_column_index("error_message")
                error_col = self._column_letter(error_col_idx)
                updates.append({
                    "range": f"{self._sheet_name()}!{error_col}{row_index}",
                    "values": [[error_message]],
                })

            # Media reference (stored in video_file_path column)
            if video_file_path is not None:
                video_path_col_idx = self._get_column_index("video_file_path")
                video_path_col = self._column_letter(video_path_col_idx)
                updates.append({
                    "range": f"{self._sheet_name()}!{video_path_col}{row_index}",
                    "values": [[video_file_path]],
                })

            # Updated timestamp
            updated_col_idx = self._get_column_index("updated_at")
            updated_col = self._column_letter(updated_col_idx)
            updates.append({
                "range": f"{self._sheet_name()}!{updated_col}{row_index}",
                "values": [[datetime.utcnow().isoformat() + "Z"]],
            })

            # Batch update
            body = {"data": updates, "valueInputOption": "RAW"}
            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.spreadsheet_id, body=body
            ).execute()

            logger.debug(f"Row {row_index} updated successfully")

        except HttpError as e:
            raise MetadataRepositoryError(f"Failed to update task status: {e}") from e
        except Exception as e:
            raise MetadataRepositoryError(f"Update failed: {e}") from e

    def increment_attempts(self, task: Task) -> None:
        """
        Increment retry attempts counter.

        Args:
            task: Task to update.

        Raises:
            MetadataRepositoryError: If update fails.
        """
        try:
            row_index = task.row_index
            current_attempts = task.attempts
            new_attempts = current_attempts + 1

            logger.debug(f"Incrementing attempts for row {row_index}: {current_attempts} -> {new_attempts}")

            updates = []

            # Attempts column
            attempts_col_idx = self._get_column_index("attempts")
            attempts_col = self._column_letter(attempts_col_idx)
            updates.append({
                "range": f"{self._sheet_name()}!{attempts_col}{row_index}",
                "values": [[new_attempts]],
            })

            # Last attempt timestamp
            last_attempt_col_idx = self._get_column_index("last_attempt_at")
            last_attempt_col = self._column_letter(last_attempt_col_idx)
            updates.append({
                "range": f"{self._sheet_name()}!{last_attempt_col}{row_index}",
                "values": [[datetime.utcnow().isoformat() + "Z"]],
            })

            # Batch update
            body = {"data": updates, "valueInputOption": "RAW"}
            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.spreadsheet_id, body=body
            ).execute()

            # Update task object
            task.attempts = new_attempts
            task.last_attempt_at = datetime.utcnow()

        except HttpError as e:
            raise MetadataRepositoryError(f"Failed to increment attempts: {e}") from e
        except Exception as e:
            raise MetadataRepositoryError(f"Increment failed: {e}") from e

    def _parse_row(
        self,
        row: List[str],
        row_index: int,
        header_map: dict[str, int] | None = None,
    ) -> Task:
        """
        Parse spreadsheet row into Task.

        Args:
            row: Row data.
            row_index: Row number in sheet (1-indexed).
            header_map: Optional dict mapping normalized column names to indices.

        Returns:
            Task object.

        Raises:
            ValidationError: If validation fails.
        """
        # Required fields
        task_id = self._get_cell(row, "task_id", header_map=header_map)
        title = self._get_cell(row, "title", header_map=header_map)
        # Read from column "video_file_path" but store as media_reference (abstract reference)
        media_reference = self._get_cell(row, "video_file_path", header_map=header_map)
        status = self._get_cell(row, "status", header_map=header_map)

        # Validate required fields
        if not task_id:
            raise ValidationError("task_id is required")
        if not title:
            raise ValidationError("title is required")
        if not media_reference:
            raise ValidationError("video_file_path (media_reference) is required")
        if not status:
            raise ValidationError("status is required")

        # Validate title length
        if len(title) > 100:
            raise ValidationError(f"title exceeds 100 characters: {len(title)}")

        # Optional fields
        description = self._get_cell(row, "description", default="", header_map=header_map)
        if len(description) > 5000:
            raise ValidationError(f"description exceeds 5000 characters: {len(description)}")

        tags_str = self._get_cell(row, "tags", default="", header_map=header_map)
        tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
        if len(tags_str) > 500:
            raise ValidationError(f"tags exceed 500 characters: {len(tags_str)}")

        category_id = self._get_cell(row, "category_id", default="22", header_map=header_map)
        # Read from column "thumbnail_path" but store as thumbnail_reference (abstract reference)
        thumbnail_reference = self._get_cell(row, "thumbnail_path", default=None, header_map=header_map)

        # Parse datetime fields
        publish_at = self._parse_datetime(
            self._get_cell(row, "publish_at", default=None, header_map=header_map)
        )

        # Parse privacy status
        privacy_status_str = self._get_cell(
            row, "privacy_status", default="private", header_map=header_map
        )
        try:
            privacy_status = PrivacyStatus(privacy_status_str)
        except ValueError:
            raise ValidationError(
                f"Invalid privacy_status: {privacy_status_str}. "
                f"Must be one of: public, unlisted, private"
            )

        # Parse status
        try:
            task_status = TaskStatus(status)
        except ValueError:
            raise ValidationError(f"Invalid status: {status}")

        # Metadata fields
        # Read from column "youtube_video_id" but store as platform_media_id (platform-agnostic)
        platform_media_id = self._get_cell(
            row, "youtube_video_id", default=None, header_map=header_map
        )
        error_message = self._get_cell(row, "error_message", default=None, header_map=header_map)

        attempts = self._parse_int(
            self._get_cell(row, "attempts", default="0", header_map=header_map)
        )
        if attempts < 0:
            raise ValidationError(f"attempts must be non-negative: {attempts}")

        last_attempt_at = self._parse_datetime(
            self._get_cell(row, "last_attempt_at", default=None, header_map=header_map)
        )
        created_at = self._parse_datetime(
            self._get_cell(row, "created_at", default=None, header_map=header_map)
        )
        updated_at = self._parse_datetime(
            self._get_cell(row, "updated_at", default=None, header_map=header_map)
        )

        return Task(
            task_id=task_id,
            row_index=row_index,
            media_reference=media_reference,
            thumbnail_reference=thumbnail_reference,
            title=title,
            description=description,
            tags=tags,
            category_id=category_id,
            publish_at=publish_at,
            privacy_status=privacy_status,
            status=task_status,
            platform_media_id=platform_media_id or None,
            error_message=error_message or None,
            attempts=attempts,
            last_attempt_at=last_attempt_at,
            created_at=created_at,
            updated_at=updated_at,
        )

    def _get_cell(
        self,
        row: List[str],
        column_name: str,
        default: Any = "",
        header_map: dict[str, int] | None = None,
    ) -> str:
        """
        Get cell value by column name.

        Args:
            row: Row data.
            column_name: Column name to look up.
            default: Default value if cell is empty or column not found.
            header_map: Optional dict mapping normalized column names to indices.
                        If provided and column_name found, uses header_map index.
                        Otherwise falls back to COLUMN_MAP.

        Returns:
            Cell value as string (stripped).
        """
        # Normalize column name for lookup
        normalized_name = column_name.strip().lower()

        # Try header_map first if provided
        if header_map is not None and normalized_name in header_map:
            index = header_map[normalized_name]
        else:
            # Fallback to COLUMN_MAP
            index = self.COLUMN_MAP.get(column_name)

        if index is None:
            return default
        if index >= len(row):
            return default
        value = row[index].strip()
        return value if value else default

    def _parse_datetime(self, value: str | None) -> datetime | None:
        """
        Parse ISO 8601 datetime string.

        Args:
            value: Datetime string or None.

        Returns:
            datetime object or None.

        Raises:
            ValidationError: If format is invalid.
        """
        if not value:
            return None

        try:
            # Try parsing ISO 8601 with Z suffix
            if value.endswith("Z"):
                return datetime.fromisoformat(value[:-1])
            else:
                return datetime.fromisoformat(value)
        except ValueError as e:
            raise ValidationError(f"Invalid datetime format: {value}. Use ISO 8601 format.") from e

    def _parse_int(self, value: str) -> int:
        """
        Parse integer from string.

        Args:
            value: String value.

        Returns:
            Integer value.

        Raises:
            ValidationError: If not a valid integer.
        """
        try:
            return int(value) if value else 0
        except ValueError as e:
            raise ValidationError(f"Invalid integer: {value}") from e

    def _mark_row_failed(self, row_index: int, error_message: str) -> None:
        """Mark a row as FAILED with error message (best effort)."""
        try:
            status_col_idx = self._get_column_index("status")
            status_col = self._column_letter(status_col_idx)

            error_col_idx = self._get_column_index("error_message")
            error_col = self._column_letter(error_col_idx)

            updates = [
                {
                    "range": f"{self._sheet_name()}!{status_col}{row_index}",
                    "values": [[TaskStatus.FAILED.value]],
                },
                {
                    "range": f"{self._sheet_name()}!{error_col}{row_index}",
                    "values": [[error_message]],
                },
            ]

            body = {"data": updates, "valueInputOption": "RAW"}
            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.spreadsheet_id, body=body
            ).execute()

            logger.info(f"Row {row_index} marked as FAILED")

        except Exception as e:
            logger.warning(f"Failed to mark row {row_index} as FAILED: {e}")

    def _sheet_name(self) -> str:
        """Extract sheet name from range (e.g., 'Videos!A:Z' -> 'Videos')."""
        return self.range_name.split("!")[0] if "!" in self.range_name else "Sheet1"

    def _column_letter(self, column_index: int) -> str:
        """Convert 0-indexed column number to Excel-style letter (0 -> A, 25 -> Z, 26 -> AA)."""
        result = ""
        while column_index >= 0:
            result = chr(column_index % 26 + ord("A")) + result
            column_index = column_index // 26 - 1
        return result
