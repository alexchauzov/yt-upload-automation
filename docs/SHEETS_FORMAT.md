# Google Sheets Format Specification

This document describes the required format for Google Sheets used as metadata source for video publishing tasks.

## Sheet Structure

The Google Sheet should contain video metadata with one video per row. The first row (header) defines column names.

### Required Columns

| Column Name | Type | Required | Description | Example |
|------------|------|----------|-------------|---------|
| `task_id` | String | Yes | Unique identifier for the task | `video_001` |
| `status` | String | Yes | Task status (see Status Values below) | `READY` |
| `title` | String | Yes | Video title (max 100 chars recommended) | `My Tutorial Video` |
| `video_file_path` | String | Yes | Path to video file (absolute or relative) | `/videos/tutorial.mp4` |

### Optional Columns

| Column Name | Type | Required | Description | Example |
|------------|------|----------|-------------|---------|
| `description` | String | No | Video description | `This is a tutorial about...` |
| `tags` | String | No | Comma-separated tags | `tutorial,python,programming` |
| `category_id` | String | No | YouTube category ID (default: 22) | `27` |
| `thumbnail_path` | String | No | Path to thumbnail image | `/thumbnails/thumb.jpg` |
| `publish_at` | DateTime | No | Scheduled publish time (ISO 8601) | `2025-12-20T10:00:00Z` |
| `privacy_status` | String | No | Privacy: public/unlisted/private | `unlisted` |
| `youtube_video_id` | String | No | YouTube video ID (set after upload) | `dQw4w9WgXcQ` |
| `error_message` | String | No | Error description if failed | `File not found` |
| `attempts` | Integer | No | Number of upload attempts | `2` |
| `last_attempt_at` | DateTime | No | Timestamp of last attempt | `2025-12-16T15:30:00Z` |
| `created_at` | DateTime | No | Task creation timestamp | `2025-12-15T10:00:00Z` |
| `updated_at` | DateTime | No | Last update timestamp | `2025-12-16T15:30:00Z` |

## Status Values

Valid status values for the `status` column:

- **`READY`** - Task is ready for processing
- **`UPLOADING`** - Upload in progress
- **`SCHEDULED`** - Successfully uploaded and scheduled
- **`FAILED`** - Upload failed (see `error_message`)
- **`VALIDATED`** - Validation passed (dry-run mode)
- **`DRY_RUN_OK`** - Dry-run validation successful

## Validation Rules

The following validation rules are enforced when reading tasks:

### Required Fields
- `task_id` must be non-empty
- `title` must be non-empty
- `video_file_path` must be non-empty
- `status` must be a valid status value

### Field Constraints
- `title`: Maximum 100 characters (YouTube limit)
- `description`: Maximum 5000 characters (YouTube limit)
- `tags`: Maximum 500 characters total
- `category_id`: Must be a valid YouTube category ID (1-44)
- `privacy_status`: Must be one of: `public`, `unlisted`, `private`
- `publish_at`: Must be ISO 8601 format, future datetime
- `attempts`: Must be non-negative integer

### Data Type Validation
- DateTime fields must be valid ISO 8601 format
- Integer fields must be valid integers
- Enum fields (status, privacy_status) must match allowed values

## Example Sheet

| task_id | status | title | video_file_path | description | tags | publish_at | privacy_status |
|---------|--------|-------|----------------|-------------|------|------------|---------------|
| vid_001 | READY | Python Tutorial | /videos/tutorial.mp4 | Learn Python basics | python,tutorial | 2025-12-20T10:00:00Z | unlisted |
| vid_002 | SCHEDULED | Advanced Tips | /videos/advanced.mp4 | Advanced techniques | python,advanced | 2025-12-21T14:00:00Z | public |
| vid_003 | FAILED | Old Video | /videos/old.mp4 | | | | private |

## Configuration

The repository implementation uses the following environment variables:

- **`GOOGLE_SHEETS_ID`** - The Google Sheets document ID (from URL)
- **`GOOGLE_SHEETS_RANGE`** - Sheet name and range (e.g., `Videos!A:Z`)
- **`GOOGLE_APPLICATION_CREDENTIALS`** - Path to service account JSON file
- **`SHEETS_READY_STATUS`** - Status to filter for (default: `READY`)

## Service Account Setup

1. Create a Google Cloud project
2. Enable Google Sheets API v4
3. Create a service account
4. Download service account JSON credentials
5. Share your Google Sheet with the service account email (viewer + editor access)

## Update Behavior

When a task is processed, the following columns are automatically updated:

- **`status`** - Updated to reflect current state (UPLOADING → SCHEDULED/FAILED)
- **`youtube_video_id`** - Set after successful upload
- **`error_message`** - Set if upload fails
- **`attempts`** - Incremented on each upload attempt
- **`last_attempt_at`** - Set to current timestamp on each attempt
- **`updated_at`** - Set to current timestamp on any update

## Error Handling

If a row fails validation:
- Status is set to `FAILED`
- `error_message` is populated with validation error details
- Row is skipped for processing

Common validation errors:
- Missing required fields
- Invalid datetime format
- File path doesn't exist
- Invalid category ID
- Title/description exceeds length limits
