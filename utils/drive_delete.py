#!/usr/bin/env python3
"""Delete files from Google Drive service account by ID list."""

import argparse
import csv
import json
import os
import sys

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def get_drive_service():
    """Build Google Drive API service."""
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        print("ERROR: GOOGLE_APPLICATION_CREDENTIALS env var not set", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(creds_path):
        print(f"ERROR: Credentials file not found: {creds_path}", file=sys.stderr)
        sys.exit(1)

    credentials = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=credentials)


def read_file_ids(path: str) -> list[dict]:
    """Read file IDs from input file (tsv/csv/jsonl)."""
    files = []

    with open(path, "r", encoding="utf-8") as fp:
        first_line = fp.readline()
        fp.seek(0)

        if first_line.startswith("{"):
            for line in fp:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    files.append({"id": data.get("id"), "name": data.get("name", "")})

        elif "\t" in first_line:
            reader = csv.DictReader(fp, delimiter="\t")
            for row in reader:
                files.append({"id": row.get("id"), "name": row.get("name", "")})

        else:
            reader = csv.DictReader(fp)
            for row in reader:
                files.append({"id": row.get("id"), "name": row.get("name", "")})

    return [f for f in files if f.get("id")]


def delete_files(drive, files: list[dict], dry_run: bool = True) -> tuple[int, int]:
    """Delete files by ID. Returns (success_count, error_count)."""
    success = 0
    errors = 0

    for f in files:
        file_id = f["id"]
        name = f.get("name", "")

        if dry_run:
            print(f"[DRY-RUN] Would delete: {file_id} ({name})")
            success += 1
        else:
            try:
                drive.files().delete(fileId=file_id).execute()
                print(f"[DELETED] {file_id} ({name})")
                success += 1
            except HttpError as e:
                print(f"[ERROR] {file_id} ({name}): {e.reason}", file=sys.stderr)
                errors += 1

    return success, errors


def empty_trash(drive):
    """Empty the trash."""
    try:
        drive.files().emptyTrash().execute()
        print("[OK] Trash emptied")
    except HttpError as e:
        print(f"[ERROR] Failed to empty trash: {e.reason}", file=sys.stderr)


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Delete files from Google Drive by ID list",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
WARNING: This tool permanently deletes files!

Examples:
  # Dry run (default, safe)
  python drive_delete.py --input files.tsv

  # Actually delete files
  python drive_delete.py --input files.tsv --yes

  # Delete and empty trash
  python drive_delete.py --input files.tsv --yes --empty-trash
""",
    )
    parser.add_argument("--input", required=True, help="Input file (tsv/csv/jsonl from drive_list)")
    parser.add_argument("--yes", action="store_true", help="Actually delete files (without this flag, only dry-run)")
    parser.add_argument("--empty-trash", action="store_true", help="Empty trash after deletion")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    files = read_file_ids(args.input)

    if not files:
        print("No file IDs found in input file.")
        sys.exit(0)

    print(f"Found {len(files)} files to process")
    print()

    dry_run = not args.yes

    if dry_run:
        print("=" * 50)
        print("DRY-RUN MODE (no files will be deleted)")
        print("Use --yes to actually delete files")
        print("=" * 50)
        print()

    drive = get_drive_service()
    success, errors = delete_files(drive, files, dry_run=dry_run)

    print()
    print(f"Summary: {success} {'would be ' if dry_run else ''}deleted, {errors} errors")

    if args.empty_trash and not dry_run:
        print()
        empty_trash(drive)


if __name__ == "__main__":
    main()
