# Google Drive & Sheets Utilities

CLI utilities for managing Google Drive service account storage and Google Sheets operations.

## Purpose

These utilities help diagnose and manage Google Drive/Sheets for service accounts:
- Verify service account identity and authentication (`drive_whoami`)
- Check access permissions to folders (`drive_check_folder`)
- Check current storage quota usage (`drive_quota`)
- List all files owned by service account (`drive_list`)
- Bulk delete files to free up space (`drive_delete`)
- Reset and verify spreadsheet data (`sheets_reset_verify`)

This is useful when acceptance tests need to reset spreadsheet state, when debugging Drive API access issues, or when managing accumulated test files.

## Prerequisites

Set the environment variable pointing to your service account JSON:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service_account.json
```

Or create a `.env` file in the project root:

```env
GOOGLE_APPLICATION_CREDENTIALS=.data/service_account.json
```

## Utilities

### drive_whoami.py

Show service account identity and verify authentication.

```bash
python utils/drive_whoami.py
```

Output:
```
Service Account Identity
==================================================
Credentials file: .data/service_account.json

From JSON file:
  client_email: sa-name@project.iam.gserviceaccount.com
  project_id:   my-project-123

From Drive API (about.get):
  emailAddress: sa-name@project.iam.gserviceaccount.com
  displayName:  sa-name
  kind:         drive#user
  me:           True
```

### drive_check_folder.py

Check access to a Google Drive folder.

```bash
# Check specific folder
python utils/drive_check_folder.py 1ABC...xyz

# Or use RUNS_FOLDER_ID from env
python utils/drive_check_folder.py
```

Output:
```
Checking folder: 1ABC...xyz
============================================================
ID:        1ABC...xyz
Name:      acceptance-test-runs
MIME Type: application/vnd.google-apps.folder
Drive ID:  N/A (My Drive)
Shared:    True

Owners:
  - owner@example.com (Owner Name)

Capabilities (service account can...):
  add files to folder: YES
  remove files from folder: YES
  list folder contents: YES
  copy files: YES
  delete: NO
  edit: YES

Access check: OK
```

### drive_quota.py

Show storage quota for the service account.

```bash
python utils/drive_quota.py
```

Output:
```
Google Drive Storage Quota
========================================
Account:          sa-name@project.iam.gserviceaccount.com
Total Quota:      15.00 GB
Used:             14.85 GB (99.0%)
Free:             0.15 GB
Usage in Drive:   14.80 GB
Usage in Trash:   0.05 GB
```

### drive_list.py

List all files owned by the service account.

```bash
# List all files (table view)
python utils/drive_list.py

# Save to TSV file
python utils/drive_list.py --out files.tsv

# Save to CSV
python utils/drive_list.py --out files.csv --format csv

# Save to JSON Lines
python utils/drive_list.py --out files.jsonl --format jsonl

# Filter by name prefix
python utils/drive_list.py --name-prefix "yt-upload-automation"

# Filter by age (older than 7 days)
python utils/drive_list.py --older-than-days 7

# Filter by MIME type
python utils/drive_list.py --mime-type "application/vnd.google-apps.spreadsheet"

# Combine filters
python utils/drive_list.py --name-prefix "yt-upload" --older-than-days 1 --out old_runs.tsv
```

### drive_delete.py

Delete files by ID from an input file.

```bash
# DRY-RUN (default, safe) - shows what would be deleted
python utils/drive_delete.py --input files.tsv

# Actually delete files (requires --yes)
python utils/drive_delete.py --input files.tsv --yes

# Delete and empty trash
python utils/drive_delete.py --input files.tsv --yes --empty-trash
```

### sheets_reset_verify.py

Reset runtime spreadsheet from template and verify data match. Uses Sheets API `copyTo` which works with service accounts (unlike Drive `files.copy` which requires create permissions).

**Additional env vars:**
```bash
export TEMPLATE_SPREADSHEET_ID=your_template_spreadsheet_id
export RUNTIME_SPREADSHEET_ID=your_runtime_spreadsheet_id
```

```bash
# Reset runtime from template, then verify match
python utils/sheets_reset_verify.py

# Only verify (no reset)
python utils/sheets_reset_verify.py --verify-only

# Only reset (no verify)
python utils/sheets_reset_verify.py --reset-only

# Override IDs via command line
python utils/sheets_reset_verify.py --template-id ABC123 --runtime-id XYZ789
```

Output:
```
============================================================
RESET
============================================================
Resetting runtime spreadsheet...
  Template: 1ABC...
  Runtime:  1XYZ...

Template sheets: ['Videos', 'Config']
Runtime sheets (before): ['Videos', 'Config']

  Copying sheet 'Videos'...
    -> Created sheet ID 123456789 ('Copy of Videos')
  Copying sheet 'Config'...
    -> Created sheet ID 987654321 ('Copy of Config')

Applying batch update (delete old + rename new)...
Runtime sheets (after): ['Videos', 'Config']

Reset complete.

============================================================
VERIFY
============================================================
Verifying spreadsheet match...

Sheet names match: ['Config', 'Videos']

  Checking sheet 'Config'...
    OK (5 rows, 2 cols)
  Checking sheet 'Videos'...
    OK (10 rows, 15 cols)

============================================================
SUCCESS
```

## Typical Workflow

### 1. Check quota

```bash
python utils/drive_quota.py
```

### 2. List files and export

```bash
python utils/drive_list.py --out all_files.tsv
```

### 3. Review and edit the list

Open `all_files.tsv` in a spreadsheet or text editor. Remove rows for files you want to keep.

### 4. Dry-run deletion

```bash
python utils/drive_delete.py --input all_files.tsv
```

Review the output to confirm correct files will be deleted.

### 5. Delete files

```bash
python utils/drive_delete.py --input all_files.tsv --yes
```

### 6. Empty trash (optional)

```bash
python utils/drive_delete.py --input all_files.tsv --yes --empty-trash
```

Or run step 5 with `--empty-trash` flag.

### 7. Verify quota

```bash
python utils/drive_quota.py
```

## WARNING

**These utilities can permanently delete files!**

- Always use dry-run first (`--input` without `--yes`)
- Review the file list before deletion
- Files in trash still count toward quota until emptied
- `--empty-trash` permanently removes ALL trashed files (not just the ones you deleted)
- There is no undo for `--empty-trash`

## File Formats

The utilities support three output/input formats:

| Format | Extension | Description |
|--------|-----------|-------------|
| TSV | `.tsv` | Tab-separated values (default) |
| CSV | `.csv` | Comma-separated values |
| JSONL | `.jsonl` | JSON Lines (one JSON object per line) |

All formats include these fields:
- `id` - Google Drive file ID
- `name` - File name
- `mimeType` - MIME type
- `size` - Size in bytes
- `createdTime` - Creation timestamp
- `modifiedTime` - Last modification timestamp
- `parents` - Parent folder IDs (comma-separated)
