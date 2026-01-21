python youtube_ui_uploader.py --file ../../.test_data/video1.mp4 --title "Test video #1" --description "Test description" --privacy scheduled --publish-at 2026-12-31T23:59:59Z
@rem Optional parameters:
@rem --cdp-port 9222                     - specify custom CDP port (default: 9222)
@rem --chrome-profile "C:\...\Default"   - use specific Chrome profile instead of CDP
@rem --close-browser-on-completion       - close browser after upload (default: keep open)
@rem --upload-timeout 600                - timeout for stalled uploads in seconds (default: 600)
