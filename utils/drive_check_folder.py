#!/usr/bin/env python3
"""Check access to a Google Drive folder."""

import argparse
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
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    return build("drive", "v3", credentials=credentials)


def check_folder(drive, folder_id: str):
    """Check folder access and print details."""
    print(f"Checking folder: {folder_id}")
    print("=" * 60)

    try:
        result = drive.files().get(
            fileId=folder_id,
            fields="id,name,mimeType,driveId,owners,capabilities,shared,webViewLink",
        ).execute()

        print(f"ID:        {result.get('id')}")
        print(f"Name:      {result.get('name')}")
        print(f"MIME Type: {result.get('mimeType')}")
        print(f"Drive ID:  {result.get('driveId', 'N/A (My Drive)')}")
        print(f"Shared:    {result.get('shared', 'N/A')}")
        print(f"Web Link:  {result.get('webViewLink', 'N/A')}")

        owners = result.get("owners", [])
        if owners:
            print()
            print("Owners:")
            for owner in owners:
                print(f"  - {owner.get('emailAddress')} ({owner.get('displayName', 'N/A')})")

        caps = result.get("capabilities", {})
        if caps:
            print()
            print("Capabilities (service account can...):")
            relevant_caps = [
                ("canAddChildren", "add files to folder"),
                ("canRemoveChildren", "remove files from folder"),
                ("canListChildren", "list folder contents"),
                ("canCopy", "copy files"),
                ("canDelete", "delete"),
                ("canEdit", "edit"),
                ("canShare", "share"),
                ("canMoveItemWithinDrive", "move within drive"),
            ]
            for cap_key, cap_desc in relevant_caps:
                value = caps.get(cap_key)
                if value is not None:
                    status = "YES" if value else "NO"
                    print(f"  {cap_desc}: {status}")

        print()
        print("Access check: OK")

    except HttpError as e:
        print(f"ERROR: {e.resp.status} - {e.reason}", file=sys.stderr)
        if e.resp.status == 404:
            print("  Folder not found or no access", file=sys.stderr)
        elif e.resp.status == 403:
            print("  Permission denied", file=sys.stderr)
        sys.exit(1)


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Check access to a Google Drive folder")
    parser.add_argument("folder_id", nargs="?", help="Folder ID to check (or uses RUNS_FOLDER_ID env var)")
    args = parser.parse_args()

    folder_id = args.folder_id or os.getenv("RUNS_FOLDER_ID")

    if not folder_id:
        print("ERROR: No folder_id provided and RUNS_FOLDER_ID env var not set", file=sys.stderr)
        print("Usage: python drive_check_folder.py <folder_id>", file=sys.stderr)
        sys.exit(1)

    drive = get_drive_service()
    check_folder(drive, folder_id)


if __name__ == "__main__":
    main()
