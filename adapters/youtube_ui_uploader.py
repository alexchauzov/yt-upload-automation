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
    page.goto("https://studio.youtube.com", wait_until="domcontentloaded", timeout=30000)

    print("[3/3] Waiting for YouTube Studio to load...")
    # Wait for Create button to appear (indicates Studio is ready)
    page.wait_for_function(
        """() => document.querySelector('button[aria-label="Create"]') !== null""",
        timeout=30000
    )
    print("[OK] YouTube Studio opened")

    return browser, page


def open_upload_dialog(page: Page) -> None:
    """Open the YouTube Studio upload dialog.

    Args:
        page: Playwright page object with YouTube Studio already loaded
    """
    print("[4/7] Clicking Create button...")

    # Click the Create button
    page.click('button[aria-label="Create"]', timeout=30000)

    print("[5/7] Waiting for menu...")

    # Wait for menu to appear
    page.wait_for_selector('tp-yt-paper-listbox', timeout=10000)

    print("[6/7] Clicking Upload videos...")

    # Click "Upload videos" menu item
    page.click('tp-yt-paper-item:has-text("Upload videos")', timeout=10000)

    print("[7/7] Waiting for upload dialog...")

    # Wait for upload dialog using JavaScript (bypasses Shadow DOM issues)
    page.wait_for_function(
        """() => {
            const dialog = document.querySelector('ytcp-uploads-dialog');
            const fileInput = document.querySelector('input[type="file"]');
            return dialog !== null || fileInput !== null;
        }""",
        timeout=30000
    )

    print("[OK] Upload dialog opened")


def upload_video_file(
    page: Page,
    file_path: Path,
    title: str,
    privacy: str,
    description: Optional[str] = None,
    publish_at: Optional[str] = None
) -> None:
    """Upload a video file with specified metadata.

    Args:
        page: Playwright page object with upload dialog open
        file_path: Path to the video file
        title: Video title
        privacy: Privacy setting (private, unlisted, public, scheduled)
        description: Video description (optional)
        publish_at: ISO 8601 UTC timestamp for scheduled publishing
    """
    print("\n[UPLOAD] Starting video upload...")

    # Step 1: Select the video file
    print("[1/8] Selecting video file (it might take a while)...")
    print(f"[INFO] File: {file_path.absolute()}")
    
    # Find file input and set the file directly
    file_input = page.evaluate_handle(
        """() => document.querySelector('input[type="file"]')"""
    )
    file_input.as_element().set_input_files(str(file_path.absolute()))
    
    print(f"[INFO] File selected: {file_path.name}")

    # Step 2: Wait for form to be ready (title and description inputs appear)
    print("[2/8] Waiting for metadata form...")
    
    page.wait_for_function(
        """() => {
            const titleInput = document.querySelector('ytcp-social-suggestions-textbox#title-textarea');
            const descInput = document.querySelector('ytcp-social-suggestions-textbox#description-textarea');
            return titleInput !== null && descInput !== null;
        }""",
        timeout=60000
    )
    
    print("[OK] Metadata form ready")

    # Step 3: Fill in the title
    print("[3/8] Setting video title...")
    
    # Clear existing title and type new one
    page.evaluate(
        """(title) => {
            const titleBox = document.querySelector('ytcp-social-suggestions-textbox#title-textarea');
            const input = titleBox.querySelector('div#textbox');
            if (input) {
                input.textContent = title;
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }""",
        title
    )
    
    print(f"[INFO] Title set: {title}")

    # Set description if provided
    if description:
        print("[3/8] Setting video description...")
        page.evaluate(
            """(desc) => {
                const descBox = document.querySelector('ytcp-social-suggestions-textbox#description-textarea');
                const input = descBox ? descBox.querySelector('div#textbox') : null;
                if (input) {
                    input.textContent = desc;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }""",
            description
        )
        print(f"[INFO] Description set: {description[:50]}{'...' if len(description) > 50 else ''}")

    # Step 4: Click through wizard steps (Next buttons)
    print("[4/8] Navigating through upload steps...")
    
    # Click "Next" to go to "Video elements" page
    page.click('ytcp-button#next-button', timeout=10000)
    page.wait_for_timeout(1000)
    
    # Click "Next" to go to "Checks" page
    page.click('ytcp-button#next-button', timeout=10000)
    page.wait_for_timeout(1000)
    
    # Click "Next" to go to "Visibility" page
    page.click('ytcp-button#next-button', timeout=10000)
    page.wait_for_timeout(1000)

    # Step 5: Set privacy/visibility
    print("[5/8] Setting visibility...")
    
    if privacy == "private":
        page.click('tp-yt-paper-radio-button[name="PRIVATE"]', timeout=10000)
        print("[INFO] Privacy set: Private")
        
    elif privacy == "unlisted":
        page.click('tp-yt-paper-radio-button[name="UNLISTED"]', timeout=10000)
        print("[INFO] Privacy set: Unlisted")
        
    elif privacy == "public":
        page.click('tp-yt-paper-radio-button[name="PUBLIC"]', timeout=10000)
        print("[INFO] Privacy set: Public")
        
    elif privacy == "scheduled":
        # Click Schedule radio button
        page.click('#second-container-expand-button', timeout=10000)
        print("[INFO] Privacy set: Scheduled")
        
        if publish_at:
            # Parse the ISO 8601 timestamp
            dt = datetime.strptime(publish_at, "%Y-%m-%dT%H:%M:%SZ")
            
            # Set the date
            date_str = dt.strftime("%b %d, %Y")  # e.g., "Dec 31, 2026"
            page.click('#datepicker-trigger span.ytcp-text-dropdown-trigger', timeout=10000)
            page.fill('#dialog.ytcp-date-picker input.tp-yt-paper-input', date_str)
            page.press('#dialog.ytcp-date-picker input.tp-yt-paper-input', 'Enter')
            
            # Set the time
            time_str = dt.strftime("%H:%M")  # e.g., "23:23"
            page.click('#time-of-day-container.ytcp-datetime-picker input.tp-yt-paper-input', timeout=10000)
            page.fill('#time-of-day-container.ytcp-datetime-picker input.tp-yt-paper-input', time_str)

            print(f"[INFO] Scheduled for: {publish_at}")

    # Wait a moment for settings to apply
    page.wait_for_timeout(1000)

    # Step 6: Wait for file upload to complete before proceeding
    print("[6/8] Waiting for file upload to complete...")
    
    last_progress = ""
    while True:
        progress_info = page.evaluate(
            """() => {
                const progress = document.querySelector('ytcp-video-upload-progress');
                
                if (!progress) {
                    return { done: true, percent: '100%', status: 'Upload complete' };
                }
                
                // Try to get status text
                const statusEl = progress.querySelector('.progress-label');
                
                const status = statusEl ? statusEl.textContent.trim() : '';
                
                // Check if upload is done (look for completion indicators)
                const uploadComplete = status.toLowerCase().includes('checks complete. no issues found.');
                
                return { done: uploadComplete, status };
            }"""
        )
        
        # Build progress string
        current_progress = f"{progress_info.get('status', '')}".strip()
        
        # Only print if progress changed
        if current_progress and current_progress != last_progress:
            print(f"[UPLOAD] {current_progress}")
            last_progress = current_progress
        
        # Exit when upload is complete
        if progress_info.get('done'):
            break
            
        page.wait_for_timeout(1000)  # Check every second
    
    print("[OK] File upload complete")

    # Step 7: Click save to finalize
    print("[7/8] Saving video...")
    # page.click('ytcp-button#done-button', timeout=10000)
    # page.press('#time-of-day-container.ytcp-datetime-picker input.tp-yt-paper-input', 'Enter')
    page.press('ytcp-button#done-button', 'Enter')

    # Wait for save confirmation
    print("[SAVE] Waiting for confirmation...")
    page.wait_for_function(
        """() => {
            const closeButton = document.querySelector('ytcp-button#close-button');
            const successDialog = document.querySelector('ytcp-uploads-still-processing-dialog, ytcp-video-share-dialog');
            return closeButton !== null || successDialog !== null;
        }""",
        timeout=60000
    )

    # Step 8: Get video link
    print("[8/8] Getting video link...")
    
    video_link = page.evaluate(
        """() => {
            // Try to find the video link in the success dialog
            const linkInput = document.querySelector('ytcp-video-share-dialog a.ytcp-video-share-dialog');
            if (linkInput) {
                return linkInput.href || linkInput.textContent.trim();
            }
            
            // Alternative: look for the link in other places
            const shareLink = document.querySelector('.share-panel-url, input[readonly][value*="youtu"]');
            if (shareLink) {
                return shareLink.value || shareLink.textContent.trim();
            }
            
            // Try to find any youtube video link
            const anyLink = document.querySelector('a[href*="youtu.be"], a[href*="youtube.com/watch"]');
            if (anyLink) {
                return anyLink.href;
            }
            
            return null;
        }"""
    )
    
    if video_link:
        print(f"[OK] Video scheduled successfully!")
        print(f"[LINK] {video_link}")
    else:
        print("[OK] Video saved successfully!")
        print("[WARN] Could not retrieve video link")


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
        "--description",
        help="Video description",
    )
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
        # Default: CDP connection to localhost:9222
        default_cdp_url = "http://127.0.0.1:9222"
        print(f"[INFO] Using CDP connection mode (default)")
        print(f"[INFO] Endpoint: {default_cdp_url}")
        print("[INFO] NOTE: Chrome must be running with --remote-debugging-port=9222")
        print()

        try:
            browser, page = open_youtube_studio(cdp_url=default_cdp_url)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Open upload dialog and upload the video
    print("[INFO] Browser ready. YouTube Studio is open.")

    open_upload_dialog(page)

    upload_video_file(
        page=page,
        file_path=file_path,
        title=args.title,
        privacy=args.privacy,
        description=args.description,
        publish_at=args.publish_at
    )

    print("\n[EXIT] Video uploaded successfully")


if __name__ == "__main__":
    main()
