#!/usr/bin/env python3
"""YouTube UI Uploader - Opens YouTube Studio upload dialog (Phase 3)."""

import argparse
import atexit
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import psutil
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext


# Lock file directory (in temp directory)
LOCK_DIR = Path(os.environ.get('TEMP', os.environ.get('TMPDIR', '/tmp')))

# Global variable to track current lock file (for cleanup)
_current_lock_file: Optional[Path] = None


def get_lock_file(port: int) -> Path:
    """Get lock file path for specific CDP port.
    
    Different ports get different lock files, allowing parallel execution
    with different browsers.
    """
    return LOCK_DIR / f'yt_uploader_port{port}.lock'


def acquire_lock(port: int) -> bool:
    """Acquire exclusive lock to prevent multiple instances on same port.
    
    Uses PID file with process verification to ensure the lock is valid.
    If lock file exists but process is dead or not our script - ignores stale lock.
    
    Args:
        port: CDP port number (used to create port-specific lock file)
    
    Returns:
        True if lock acquired, False if another instance is running on this port
    """
    global _current_lock_file
    
    lock_file = get_lock_file(port)
    current_pid = os.getpid()
    script_name = 'youtube_ui_uploader.py'
    
    # Check if lock file exists
    if lock_file.exists():
        try:
            lock_data = lock_file.read_text().strip().split('\n')
            if len(lock_data) >= 2:
                locked_pid = int(lock_data[0])
                locked_script = lock_data[1]
                
                # Check if process with this PID exists
                if psutil.pid_exists(locked_pid):
                    try:
                        proc = psutil.Process(locked_pid)
                        cmdline = ' '.join(proc.cmdline())
                        
                        # Verify it's actually our script
                        if script_name in cmdline and locked_script == script_name:
                            print(f"[ERROR] Another instance is already running on port {port} (PID: {locked_pid})", file=sys.stderr)
                            return False
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        # Process died or we can't access it - stale lock
                        pass
                # PID doesn't exist - stale lock, we can overwrite
        except (ValueError, IndexError):
            # Corrupted lock file - overwrite it
            pass
    
    # Write our lock
    lock_file.write_text(f"{current_pid}\n{script_name}\n")
    _current_lock_file = lock_file
    
    # Register cleanup on exit
    atexit.register(release_lock)
    
    return True


def release_lock():
    """Release the lock file."""
    global _current_lock_file
    
    try:
        if _current_lock_file and _current_lock_file.exists():
            # Only delete if it's our lock
            lock_data = _current_lock_file.read_text().strip().split('\n')
            if len(lock_data) >= 1 and int(lock_data[0]) == os.getpid():
                _current_lock_file.unlink()
    except:
        pass  # Ignore errors during cleanup
    finally:
        _current_lock_file = None


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


def ensure_chrome_running(port: int = 9222, user_data_dir: Optional[str] = None) -> bool:
    """Ensure Chrome is running with remote debugging enabled.

    Args:
        port: Remote debugging port (default: 9222)
        user_data_dir: Chrome user data directory (optional)

    Returns:
        True if Chrome is running or was successfully started
    """
    import urllib.request
    import urllib.error
    
    # Check if Chrome is already running with remote debugging
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2)
        print(f"[INFO] Chrome already running with remote debugging on port {port}")
        return True
    except (urllib.error.URLError, ConnectionRefusedError, TimeoutError):
        pass
    
    # Chrome not running, try to start it
    print(f"[INFO] Starting Chrome with remote debugging on port {port}...")
    
    # Default user data directory for YouTube automation
    if not user_data_dir:
        if sys.platform == 'win32':
            user_data_dir = os.path.join(os.environ.get('USERPROFILE', ''), 
                                          'AppData', 'Local', 'Google', 'Chrome', 'User Data', 'YT-Automation')
        else:
            user_data_dir = os.path.join(os.environ.get('HOME', ''), '.config', 'google-chrome-yt-automation')
    
    # Try common Chrome locations (cross-platform)
    if sys.platform == 'win32':
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
    else:
        chrome_paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ]
    
    chrome_exe = None
    for path in chrome_paths:
        if Path(path).exists():
            chrome_exe = path
            break
    
    if not chrome_exe:
        print("[ERROR] Chrome executable not found. Please install Chrome or specify path.", file=sys.stderr)
        return False
    
    # Start Chrome with remote debugging
    try:
        # Start Chrome in detached mode so it keeps running after script exits
        if sys.platform == 'win32':
            # Use shell=False and proper creationflags for Windows
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            
            subprocess.Popen(
                [chrome_exe, 
                 f"--remote-debugging-port={port}",
                 f"--user-data-dir={user_data_dir}"],
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True
            )
        else:
            subprocess.Popen(
                [chrome_exe, 
                 f"--remote-debugging-port={port}",
                 f"--user-data-dir={user_data_dir}"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
        
        # Wait for Chrome to start (max 10 seconds)
        print("[INFO] Waiting for Chrome to start...")
        for i in range(20):
            time.sleep(0.5)
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1)
                print("[OK] Chrome started successfully")
                return True
            except (urllib.error.URLError, ConnectionRefusedError, TimeoutError):
                continue
        
        print("[ERROR] Chrome started but remote debugging not responding", file=sys.stderr)
        return False
        
    except Exception as e:
        print(f"[ERROR] Failed to start Chrome: {e}", file=sys.stderr)
        return False


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
        page = None
        
        if contexts and len(contexts) > 0:
            context = contexts[0]
            # Find first non-closed page to reuse
            for existing_page in context.pages:
                if not existing_page.is_closed():
                    page = existing_page
                    print("[INFO] Reusing existing open page")
                    break
            
            # No open pages found, create new
            if not page:
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


def check_upload_status(page: Page) -> dict:
    """Check the current upload/processing status.

    Args:
        page: Playwright page object

    Returns:
        Dict with keys:
            - done: bool - whether process is complete (success or error)
            - success: bool - whether it completed successfully
            - status: str - current status text
            - error: str or None - error message if failed
    """
    return page.evaluate(
        """() => {
            const progress = document.querySelector('ytcp-video-upload-progress');
            
            // No progress element - this is suspicious, fail safe
            if (!progress) {
                return { done: true, success: false, status: 'Progress element not found', error: 'Upload progress element disappeared unexpectedly - possible page error' };
            }
            
            // Get status text
            const statusEl = progress.querySelector('.progress-label');
            const status = statusEl ? statusEl.textContent.trim() : '';
            const statusLower = status.toLowerCase();
            
            // Check for success indicators
            if (statusLower.includes('checks complete. no issues found')) {
                return { done: true, success: true, status: status, error: null };
            }
            
            // Check for error indicators
            const errorKeywords = ['failed', 'error', 'problem', 'issue found', 'can\\'t upload', 'unable to'];
            for (const keyword of errorKeywords) {
                if (statusLower.includes(keyword)) {
                    return { done: true, success: false, status: status, error: status };
                }
            }
            
            // Helper function to check if element is actually visible
            function isElementVisible(element) {
                if (!element) return false;
                
                // Check if element is hidden via display or visibility
                const style = window.getComputedStyle(element);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                    return false;
                }
                
                // Check if element has offsetParent (null means hidden)
                // Note: this doesn't work for position: fixed, so we check style first
                if (element.offsetParent === null && style.position !== 'fixed') {
                    return false;
                }
                
                // Check if any parent is hidden
                let parent = element.parentElement;
                while (parent) {
                    const parentStyle = window.getComputedStyle(parent);
                    if (parentStyle.display === 'none' || parentStyle.visibility === 'hidden') {
                        return false;
                    }
                    parent = parent.parentElement;
                }
                
                return true;
            }
            
            // Check for retry button (indicates error state)
            const retryButton = document.querySelector('ytcp-button#retry-button, button[aria-label*="Retry"], .retry-button');
            if (isElementVisible(retryButton)) {
                return { done: true, success: false, status: status, error: 'Upload failed - retry button appeared' };
            }
            
            // Check for error dialogs or messages
            const errorDialog = document.querySelector('.error-message, .ytcp-error-message, [class*="error"]');
            if (isElementVisible(errorDialog) && errorDialog.textContent.trim()) {
                const errorText = errorDialog.textContent.trim();
                if (errorText.toLowerCase().includes('error') || errorText.toLowerCase().includes('failed')) {
                    return { done: true, success: false, status: status, error: errorText };
                }
            }
            
            // Still in progress
            return { done: false, success: false, status: status, error: null };
        }"""
    )


def upload_video_file(
    page: Page,
    file_path: Path,
    title: str,
    privacy: str,
    description: Optional[str] = None,
    publish_at: Optional[str] = None,
    upload_timeout: int = 600
) -> None:
    """Upload a video file with specified metadata.

    Args:
        page: Playwright page object with upload dialog open
        file_path: Path to the video file
        title: Video title
        privacy: Privacy setting (private, unlisted, public, scheduled)
        description: Video description (optional)
        publish_at: ISO 8601 UTC timestamp for scheduled publishing
        upload_timeout: Timeout in seconds for upload stall detection (default 600)
    """
    print("\n[UPLOAD] Starting video upload...")

    # Step 1: Select the video file
    print("[1/8] Selecting video file (it might take a while)...")
    # resolve() normalizes the path and removes ".." components
    print(f"[INFO] File: {file_path.resolve()}")
    
    # Find file input and set the file directly
    cdp = page.context.new_cdp_session(page)

    # Use depth=-1 and pierce=True to traverse Shadow DOM
    doc = cdp.send("DOM.getDocument", {"depth": -1, "pierce": True})
    root_id = doc["root"]["nodeId"]

    res = cdp.send("DOM.querySelector", {
        "nodeId": root_id,
        "selector": 'input[type="file"]'
    })
    node_id = res.get("nodeId")
    if not node_id:
        raise RuntimeError("input[type=file] not found")

    # Get backendNodeId - this is critical for setFileInputFiles to work properly
    node_info = cdp.send("DOM.describeNode", {"nodeId": node_id})
    backend_node_id = node_info["node"]["backendNodeId"]

    # Use resolve() to normalize path (removes "..") and forward slashes for Chromium
    file_path_str = str(file_path.resolve()).replace("\\", "/")
    print(f"[INFO] File path for CDP: {file_path_str}")

    cdp.send("DOM.setFileInputFiles", {
        "backendNodeId": backend_node_id,
        "files": [file_path_str],
    })
    
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
    print('[INFO] Click "Next" to go to "Video elements" page...')
    page.click('ytcp-button#next-button', timeout=10000)
    page.wait_for_timeout(1000)
    
    # Click "Next" to go to "Checks" page
    print('[INFO] Click "Next" to go to "Checks" page...')
    page.click('ytcp-button#next-button', timeout=10000)
    page.wait_for_timeout(1000)
    
    # Click "Next" to go to "Visibility" page
    print('[INFO] Click "Next" to go to "Visibility" page...')
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
            page.fill('#time-of-day-container.ytcp-datetime-picker input.tp-yt-paper-input', time_str)
            
            # Trigger blur event to apply the time value
            page.evaluate("""() => {
                const input = document.querySelector('#time-of-day-container.ytcp-datetime-picker input.tp-yt-paper-input');
                if (input) input.blur();
            }""")

            print(f"[INFO] Scheduled for: {publish_at}")

    # Wait a moment for settings to apply
    page.wait_for_timeout(1000)

    # Step 6: Wait for file upload to complete before proceeding
    print("[6/8] Waiting for file upload to complete...")
    
    last_progress = ""
    stall_counter = 0  # Count seconds without progress change
    
    while True:
        progress_info = check_upload_status(page)
        
        # Build progress string
        current_progress = f"{progress_info.get('status', '')}".strip()
        
        # Track progress changes for stall detection
        if current_progress and current_progress != last_progress:
            print(f"[UPLOAD] {current_progress}")
            last_progress = current_progress
            stall_counter = 0  # Reset stall counter on progress change
        else:
            stall_counter += 1
            
            # Check for stall timeout
            if stall_counter >= upload_timeout:
                stall_minutes = upload_timeout // 60
                print(f"[ERROR] Upload stalled - status unchanged for {stall_minutes} minutes", file=sys.stderr)
                print(f"[ERROR] Last status: {last_progress or 'unknown'}", file=sys.stderr)
                print("[HINT] For large files or slow connections, increase --upload-timeout", file=sys.stderr)
                sys.exit(1)
        
        # Exit when upload is complete (success or error)
        if progress_info.get('done'):
            if progress_info.get('success'):
                print("[OK] File upload complete")
            else:
                error_msg = progress_info.get('error') or 'Unknown error'
                print(f"[ERROR] Upload failed: {error_msg}", file=sys.stderr)
                sys.exit(1)
            break
            
        page.wait_for_timeout(1000)  # Check every second

    # Step 7: Click save to finalize
    print("[7/8] Saving video...")
    page.click('ytcp-button#done-button', timeout=10000)

    # Wait for "Video Scheduled" confirmation dialog
    print("[SAVE] Waiting for confirmation dialog...")
    page.wait_for_function(
        """() => {
            const dialogTitle = document.querySelector('tp-yt-paper-dialog#dialog h1#dialog-title');
            return dialogTitle && dialogTitle.innerText.includes('Video scheduled');
        }""",
        timeout=60000
    )
    print("[OK] Video scheduled confirmation received")

    # Step 8: Get video link and close dialog
    print("[8/8] Getting video link...")
    
    video_link = page.evaluate(
        """() => {
            // Try to find the video link in the success dialog
            const linkInput = document.querySelector('tp-yt-paper-dialog#dialog a#share-url');
 
            return linkInput?.href;
        }"""
    )
    
    if video_link:
        print(f"[OK] Video scheduled successfully!")
        print(f"[LINK] {video_link}")
    else:
        print("[OK] Video saved successfully!")
        print("[WARN] Could not retrieve video link")
    
    # Close the confirmation dialog
    print("[CLEANUP] Closing confirmation dialog...")
    page.click('tp-yt-paper-dialog#dialog ytcp-button#close-button', timeout=10000)
    page.wait_for_timeout(1000)  # Wait for dialog to fully close
    print("[OK] Dialog closed, page ready for reuse")


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
        "--cdp-port",
        type=int,
        help='Port for Chrome remote debugging connection (default: 9222). Only localhost (127.0.0.1) connections are allowed for security. Chrome will be started automatically if not running.',
    )
    parser.add_argument(
        "--upload-timeout",
        type=int,
        default=600,
        help="Timeout in seconds for upload stall detection (default: 600). If upload status doesn't change for this duration, script exits with error. Increase for large files or slow connections.",
    )
    parser.add_argument(
        "--close-browser-on-completion",
        action="store_true",
        help="Close browser after upload completes (default: keep browser open for result verification)",
    )

    args = parser.parse_args()
    
    # Determine CDP port (for lock and browser)
    cdp_port = args.cdp_port if args.cdp_port else 9222
    
    # Acquire lock to prevent multiple instances on same port
    # (skip lock for chrome_profile mode - different mechanism)
    if not args.chrome_profile:
        if not acquire_lock(cdp_port):
            sys.exit(1)

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
    if args.cdp_port and args.chrome_profile:
        print("Error: Cannot use both --cdp-port and --chrome-profile", file=sys.stderr)
        sys.exit(1)

    # Print success output
    print(f"File: {file_path.absolute()}")
    print(f"Title: {args.title}")
    print(f"Privacy: {args.privacy}")
    if args.privacy == "scheduled" and args.publish_at:
        print(f"Publish at: {args.publish_at}")

    print()

    # Mode selection
    if args.cdp_port:
        # CDP mode with custom port
        cdp_url = f"http://127.0.0.1:{args.cdp_port}"
        print(f"[INFO] Using CDP connection mode")
        print(f"[INFO] Endpoint: {cdp_url} (localhost only)")
        print()
        
        # Ensure Chrome is running
        if not ensure_chrome_running(port=args.cdp_port):
            print("[ERROR] Failed to start Chrome. Please start it manually.", file=sys.stderr)
            sys.exit(1)

        try:
            browser, page = open_youtube_studio(cdp_url=cdp_url)
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
        print(f"[INFO] Endpoint: {default_cdp_url} (localhost only)")
        print()
        
        # Ensure Chrome is running
        if not ensure_chrome_running(port=9222):
            print("[ERROR] Failed to start Chrome. Please start it manually.", file=sys.stderr)
            sys.exit(1)

        try:
            browser, page = open_youtube_studio(cdp_url=default_cdp_url)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Open upload dialog and upload the video
    print("[INFO] Browser ready. YouTube Studio is open.")

    try:
        open_upload_dialog(page)

        upload_video_file(
            page=page,
            file_path=file_path,
            title=args.title,
            privacy=args.privacy,
            description=args.description,
            publish_at=args.publish_at,
            upload_timeout=args.upload_timeout
        )

        print("\n[EXIT] Video uploaded successfully")
    
    finally:
        # Close browser only if explicitly requested
        if args.close_browser_on_completion:
            try:
                browser.close()
                print("[INFO] Browser closed")
            except:
                pass
        else:
            print("[INFO] Browser left open for result verification")


if __name__ == "__main__":
    main()
