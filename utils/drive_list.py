#!/usr/bin/env python3
"""List files owned by Google Drive service account."""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build


def format_bytes(size_bytes: int) -> str:
    """Format bytes to human readable string."""
    if size_bytes < 0:
        return "N/A"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"


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
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    return build("drive", "v3", credentials=credentials)


def list_files(drive, name_prefix: str = None, older_than_days: int = None, mime_type: str = None):
    """List all files owned by service account."""
    query_parts = ["'me' in owners", "trashed = false"]

    if name_prefix:
        escaped = name_prefix.replace("'", "\\'")
        query_parts.append(f"name contains '{escaped}'")

    if mime_type:
        escaped = mime_type.replace("'", "\\'")
        query_parts.append(f"mimeType = '{escaped}'")

    if older_than_days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S")
        query_parts.append(f"modifiedTime < '{cutoff_str}'")

    query = " and ".join(query_parts)

    files = []
    page_token = None

    while True:
        response = drive.files().list(
            q=query,
            fields="nextPageToken, files(id, name, mimeType, size, createdTime, modifiedTime, parents)",
            pageSize=1000,
            pageToken=page_token,
        ).execute()

        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")

        if not page_token:
            break

    files.sort(key=lambda f: int(f.get("size", 0)), reverse=True)
    return files


def print_table(files):
    """Print files as human-readable table."""
    if not files:
        print("No files found.")
        return

    print(f"{'ID':<45} {'Size':>12} {'Name':<50} {'Modified':<20} {'Type'}")
    print("-" * 150)

    for f in files:
        file_id = f.get("id", "")
        name = f.get("name", "")[:50]
        mime = f.get("mimeType", "")
        size = int(f.get("size", 0))
        modified = f.get("modifiedTime", "")[:19].replace("T", " ")

        print(f"{file_id:<45} {format_bytes(size):>12} {name:<50} {modified:<20} {mime}")

    print("-" * 150)
    total_size = sum(int(f.get("size", 0)) for f in files)
    print(f"Total: {len(files)} files, {format_bytes(total_size)}")


def write_output(files, path: str, fmt: str):
    """Write files to output file."""
    fieldnames = ["id", "name", "mimeType", "size", "createdTime", "modifiedTime", "parents"]

    with open(path, "w", newline="", encoding="utf-8") as fp:
        if fmt == "jsonl":
            for f in files:
                row = {k: f.get(k, "") for k in fieldnames}
                row["parents"] = ",".join(f.get("parents", []))
                fp.write(json.dumps(row) + "\n")

        elif fmt == "csv":
            writer = csv.DictWriter(fp, fieldnames=fieldnames)
            writer.writeheader()
            for f in files:
                row = {k: f.get(k, "") for k in fieldnames}
                row["parents"] = ",".join(f.get("parents", []))
                writer.writerow(row)

        else:  # tsv
            fp.write("\t".join(fieldnames) + "\n")
            for f in files:
                row = [str(f.get(k, "")) if k != "parents" else ",".join(f.get("parents", [])) for k in fieldnames]
                fp.write("\t".join(row) + "\n")

    print(f"Written {len(files)} files to {path} ({fmt})", file=sys.stderr)


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="List files owned by service account")
    parser.add_argument("--out", help="Output file path")
    parser.add_argument("--format", choices=["tsv", "csv", "jsonl"], default="tsv", help="Output format (default: tsv)")
    parser.add_argument("--name-prefix", help="Filter by name prefix")
    parser.add_argument("--older-than-days", type=int, help="Filter files older than N days")
    parser.add_argument("--mime-type", help="Filter by MIME type")
    args = parser.parse_args()

    drive = get_drive_service()
    files = list_files(
        drive,
        name_prefix=args.name_prefix,
        older_than_days=args.older_than_days,
        mime_type=args.mime_type,
    )

    print_table(files)

    if args.out:
        write_output(files, args.out, args.format)


if __name__ == "__main__":
    main()
