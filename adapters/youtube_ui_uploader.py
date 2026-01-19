#!/usr/bin/env python3
"""YouTube UI Uploader - Opens YouTube Studio upload dialog (Phase 3)."""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Union
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext


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


def open_youtube_studio(profile_dir: Optional[Path] = None, cdp_url: Optional[str] = None) -> tuple[Union[Browser, BrowserContext], Page]:
    """Launch browser and open YouTube Studio.

    Args:
        profile_dir: Path to persisted browser profile directory (for launch mode)
        cdp_url: CDP endpoint URL (for CDP connection mode)

    Returns:
        Tuple of (browser or context, page) for cleanup later
    """
    playwright = sync_playwright().start()

    # Mode 1: CDP connection
    if cdp_url:
        print("[1/3] Connecting to Chrome via CDP...")
        print(f"[INFO] CDP endpoint: {cdp_url}")

        try:
            browser = playwright.chromium.connect_over_cdp(cdp_url)
        except Exception as e:
            error_msg = str(e).lower()
            print(f"Error: Failed to connect to Chrome via CDP: {e}", file=sys.stderr)

            if "connect" in error_msg or "refused" in error_msg or "timeout" in error_msg:
                print("\n[CDP CONNECTION ERROR]", file=sys.stderr)
                print("Could not connect to Chrome remote debugging port.", file=sys.stderr)
                print("Solution: Start Chrome with --remote-debugging-port=9222", file=sys.stderr)
                print('Example: chrome.exe --remote-debugging-port=9222', file=sys.stderr)

            sys.exit(1)

        print("[INFO] Connected to Chrome via CDP")

        # Get page from existing context or create new
        contexts = browser.contexts
        if contexts and len(contexts) > 0:
            context = contexts[0]
            if len(context.pages) > 0:
                page = context.pages[0]
                print("[INFO] Reusing existing page")
            else:
                page = context.new_page()
                print("[INFO] Created new page in existing context")
        else:
            # No contexts yet, create new page in default context
            page = browser.new_page()
            print("[INFO] Created new page in new context")

    # Mode 2: Launch with profile (existing behavior)
    else:
        print("[1/3] Launching browser...")
        print("[INFO] Requested browser channel: chrome")

        try:
            browser = playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                channel="chrome",
            )
        except Exception as e:
            error_msg = str(e).lower()
            print(f"Error: Failed to launch Chrome browser (channel='chrome'): {e}", file=sys.stderr)

            if "lock" in error_msg or "already in use" in error_msg or "cannot create" in error_msg:
                print("\n[LOCKED PROFILE ERROR]", file=sys.stderr)
                print("The Chrome profile is locked because Chrome is already running.", file=sys.stderr)
                print("Solution: Close ALL Chrome windows and try again.", file=sys.stderr)
            else:
                print("Make sure Google Chrome is installed on your system.", file=sys.stderr)

            sys.exit(1)

        if len(browser.pages) == 0:
            page = browser.new_page()
        else:
            page = browser.pages[0]

    # Common code for both modes
    print(f"[INFO] Browser type: chromium")
    print(f"[INFO] User agent: {page.evaluate('navigator.userAgent')}")

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

    # Optional arguments
    parser.add_argument(
        "--publish-at",
        help="Publish timestamp (ISO 8601 UTC: YYYY-MM-DDTHH:MM:SSZ), required if privacy=scheduled",
    )
    parser.add_argument(
        "--chrome-profile",
        help='Path to an existing Chrome profile directory (e.g. "C:\\Users\\...\\AppData\\Local\\Google\\Chrome\\User Data\\Default"). Use this to reuse a trusted logged-in session.',
    )
    parser.add_argument(
        "--connect-cdp",
        help='Connect to existing Chrome started with --remote-debugging-port (e.g. "http://127.0.0.1:9222"). Bypasses profile locking and login detection.',
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

    # Validate mutually exclusive options
    if args.connect_cdp and args.chrome_profile:
        print("Error: Cannot use both --connect-cdp and --chrome-profile", file=sys.stderr)
        sys.exit(1)

    # Print success output
    print(f"File: {file_path.absolute()}")
    print(f"Title: {args.title}")
    print(f"Privacy: {args.privacy}")
    if args.privacy == "scheduled" and args.publish_at:
        print(f"Publish at: {args.publish_at}")

    print()

    # Mode selection
    if args.connect_cdp:
        print(f"[INFO] Using CDP connection mode")
        print(f"[INFO] Endpoint: {args.connect_cdp}")
        print("[INFO] NOTE: Chrome must be running with --remote-debugging-port")
        print()

        try:
            browser, page = open_youtube_studio(cdp_url=args.connect_cdp)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.chrome_profile:
        profile_dir = Path(args.chrome_profile)
        if not profile_dir.exists():
            print(f"Error: Chrome profile directory not found: {args.chrome_profile}", file=sys.stderr)
            sys.exit(1)
        print(f"[INFO] Using Chrome profile: {profile_dir}")
        print("[INFO] NOTE: Close all Chrome windows before running, otherwise the profile may be locked.")
        print()

        try:
            browser, page = open_youtube_studio(profile_dir=profile_dir)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    else:
        # Default: Playwright-managed profile
        profile_dir = Path(".pw_profile_youtube")
        profile_dir.mkdir(exist_ok=True)
        print(f"[INFO] Using Playwright-managed profile: {profile_dir}")
        print()

        try:
            browser, page = open_youtube_studio(profile_dir=profile_dir)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Wait for user to complete actions in browser
    print("[INFO] Browser ready. YouTube Studio is open.")
    input("\nPress Enter to close browser...")

    browser.close()
    print("\n[EXIT] Browser closed")


if __name__ == "__main__":
    main()
