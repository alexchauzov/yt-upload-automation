#!/usr/bin/env python3
"""YouTube UI Uploader - Opens YouTube Studio upload dialog (Phase 3)."""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, Browser


def validate_iso8601_utc(timestamp_str: str) -> str:
    """Validate ISO 8601 UTC timestamp (YYYY-MM-DDTHH:MM:SSZ).

    Args:
        timestamp_str: Timestamp string to validate

    Returns:
        Validated timestamp string

    Raises:
        ValueError: If timestamp format is invalid
    """
    try:
        datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ")
        return timestamp_str
    except ValueError:
        raise ValueError(f"--publish-at must be in ISO 8601 UTC format (YYYY-MM-DDTHH:MM:SSZ), got: {timestamp_str}")


def open_youtube_studio(profile_dir: Path) -> tuple[Browser, Page]:
    """Launch browser and open YouTube Studio.

    Args:
        profile_dir: Path to persisted browser profile directory

    Returns:
        Tuple of (browser, page) for cleanup later
    """
    print("[1/3] Launching browser...")

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=False,
        channel="chromium",
    )

    if len(browser.pages) == 0:
        page = browser.new_page()
    else:
        page = browser.pages[0]

    print("[2/3] Opening YouTube Studio...")
    page.goto("https://studio.youtube.com", wait_until="domcontentloaded")

    print("[3/3] Waiting for YouTube Studio to load...")
    try:
        page.wait_for_selector(
            'input[type="email"], ytcp-app',
            timeout=30000
        )
    except Exception:
        pass

    print("[OK] YouTube Studio opened")

    return browser, page


def open_upload_dialog(page: Page) -> None:
    """Open the YouTube Studio upload dialog.

    Args:
        page: Playwright page object with YouTube Studio already loaded
    """
    print("[4/6] Clicking Create button...")

    # Click the Create button (camera with plus icon)
    page.click('button[aria-label*="Create"], ytcp-button#create-icon button', timeout=30000)

    print("[5/6] Clicking Upload videos...")

    # Wait for menu to appear, then click "Upload videos"
    page.click('text="Upload videos", tp-yt-paper-item:has-text("Upload videos")', timeout=10000)

    print("[6/6] Waiting for upload dialog...")

    # Wait for upload dialog/file input to appear
    try:
        page.wait_for_selector(
            'input[type="file"][accept*="video"], ytcp-uploads-dialog',
            timeout=15000
        )
    except Exception:
        pass  # Continue even if exact selector doesn't match

    print("[OK] Upload dialog opened")


def main():
    parser = argparse.ArgumentParser(
        description="YouTube UI Uploader (Phase 3: Upload dialog)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Required arguments
    parser.add_argument("--file", required=True, help="Path to video file")
    parser.add_argument("--title", required=True, help="Video title")
    parser.add_argument(
        "--privacy",
        required=True,
        choices=["private", "unlisted", "public", "scheduled"],
        help="Privacy setting",
    )

    # Optional argument
    parser.add_argument(
        "--publish-at",
        help="Publish timestamp (ISO 8601 UTC: YYYY-MM-DDTHH:MM:SSZ), required if privacy=scheduled",
    )

    args = parser.parse_args()

    # Validate file exists
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    # Validate scheduled privacy requirements
    if args.privacy == "scheduled":
        if not args.publish_at:
            print("Error: --publish-at is required when privacy=scheduled", file=sys.stderr)
            sys.exit(1)

        # Validate ISO 8601 UTC format
        try:
            validate_iso8601_utc(args.publish_at)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Warn if publish-at provided for non-scheduled privacy
        if args.publish_at:
            print("Warning: --publish-at is ignored when privacy is not 'scheduled'")

    # Print success output
    print(f"File: {file_path.absolute()}")
    print(f"Title: {args.title}")
    print(f"Privacy: {args.privacy}")
    if args.privacy == "scheduled" and args.publish_at:
        print(f"Publish at: {args.publish_at}")

    print()

    profile_dir = Path(".pw_profile_youtube")
    profile_dir.mkdir(exist_ok=True)

    try:
        browser, page = open_youtube_studio(profile_dir)

        # Wait for user to login/authorize
        input("\nPress Enter after you've logged in to continue...")

        # NEW: Phase 3 - open upload dialog
        open_upload_dialog(page)

        # Wait for user to complete actions in browser
        input("\nPress Enter to close browser...")

        browser.close()
        print("\n[EXIT] Browser closed")

    except Exception as e:
        print(f"Error: Failed to open browser: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
