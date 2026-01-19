#!/usr/bin/env python3
"""YouTube UI Uploader - CLI with Playwright browser automation (Phase 2)."""

import argparse
import sys
import time
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


def main():
    parser = argparse.ArgumentParser(
        description="YouTube UI Uploader (Phase 2: Browser automation)",
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

        time.sleep(3)

        browser.close()
        print("\n[EXIT] Browser closed")

    except Exception as e:
        print(f"Error: Failed to open browser: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
