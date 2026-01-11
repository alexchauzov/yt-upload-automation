#!/usr/bin/env python3
"""Show service account identity and Drive API user info."""

import json
import os
import sys

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build


def main():
    load_dotenv()

    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        print("ERROR: GOOGLE_APPLICATION_CREDENTIALS env var not set", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(creds_path):
        print(f"ERROR: Credentials file not found: {creds_path}", file=sys.stderr)
        sys.exit(1)

    print("Service Account Identity")
    print("=" * 50)
    print(f"Credentials file: {creds_path}")
    print()

    with open(creds_path, "r") as f:
        sa_info = json.load(f)

    print("From JSON file:")
    print(f"  client_email: {sa_info.get('client_email', 'N/A')}")
    print(f"  project_id:   {sa_info.get('project_id', 'N/A')}")
    print()

    credentials = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    drive = build("drive", "v3", credentials=credentials)

    print("From Drive API (about.get):")
    try:
        about = drive.about().get(fields="user,storageQuota").execute()

        user = about.get("user", {})
        if user:
            print(f"  emailAddress: {user.get('emailAddress', 'N/A')}")
            print(f"  displayName:  {user.get('displayName', 'N/A')}")
            print(f"  kind:         {user.get('kind', 'N/A')}")
            print(f"  me:           {user.get('me', 'N/A')}")
        else:
            print("  user: N/A")

        quota = about.get("storageQuota", {})
        if quota:
            print()
            print("Storage Quota:")
            print(f"  limit:             {quota.get('limit', 'N/A')}")
            print(f"  usage:             {quota.get('usage', 'N/A')}")
            print(f"  usageInDrive:      {quota.get('usageInDrive', 'N/A')}")
            print(f"  usageInDriveTrash: {quota.get('usageInDriveTrash', 'N/A')}")

    except Exception as e:
        print(f"  ERROR: {e}")


if __name__ == "__main__":
    main()
