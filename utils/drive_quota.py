#!/usr/bin/env python3
"""Show Google Drive storage quota for service account."""

import os
import sys

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


def main():
    load_dotenv()

    drive = get_drive_service()

    about = drive.about().get(fields="storageQuota,user").execute()
    quota = about.get("storageQuota", {})
    user = about.get("user", {})

    limit = int(quota.get("limit", -1))
    usage = int(quota.get("usage", 0))
    usage_in_drive = int(quota.get("usageInDrive", 0))
    usage_in_trash = int(quota.get("usageInDriveTrash", 0))

    if limit > 0:
        free = limit - usage
        percent_used = (usage / limit) * 100
    else:
        free = -1
        percent_used = 0

    print("Google Drive Storage Quota")
    print("=" * 40)
    if user:
        print(f"Account:          {user.get('emailAddress', 'N/A')}")
    print(f"Total Quota:      {format_bytes(limit)}")
    print(f"Used:             {format_bytes(usage)} ({percent_used:.1f}%)")
    print(f"Free:             {format_bytes(free)}")
    print(f"Usage in Drive:   {format_bytes(usage_in_drive)}")
    print(f"Usage in Trash:   {format_bytes(usage_in_trash)}")


if __name__ == "__main__":
    main()
