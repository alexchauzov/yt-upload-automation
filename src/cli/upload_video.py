"""
CLI script for uploading videos to YouTube.

Usage:
    python -m src.cli.upload_video --file video.mp4 --title "My Video"
"""

import argparse
import sys
from typing import Optional

from src.core.config import get_config
from src.adapters.youtube import YouTubeUploader


def parse_args(argv: list[str] | None = None):
    """
    Parse command-line arguments for video upload.

    Args:
        argv: List of command-line arguments (defaults to sys.argv)

    Returns:
        Parsed arguments object
    """
    parser = argparse.ArgumentParser(
        description="Upload a video to YouTube",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.cli.upload_video --file video.mp4 --title "My Video"
  python -m src.cli.upload_video --file video.mp4 --title "My Video" --description "Test" --privacy-status unlisted
  python -m src.cli.upload_video --file video.mp4 --title "My Video" --tags "tag1,tag2,tag3"
        """
    )

    parser.add_argument(
        "--file",
        required=True,
        help="Path to video file to upload"
    )

    parser.add_argument(
        "--title",
        required=True,
        help="Video title"
    )

    parser.add_argument(
        "--description",
        default="",
        help="Video description (optional)"
    )

    parser.add_argument(
        "--tags",
        default=None,
        help="Comma-separated list of tags (optional)"
    )

    parser.add_argument(
        "--privacy-status",
        default="unlisted",
        choices=["public", "unlisted", "private"],
        help="Privacy status: public, unlisted, or private (default: unlisted)"
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None):
    """
    Main entry point for video upload CLI.

    Args:
        argv: List of command-line arguments (defaults to sys.argv)
    """
    # Parse arguments
    args = parse_args(argv)

    # Parse tags if provided
    tags = None
    if args.tags:
        tags = [tag.strip() for tag in args.tags.split(",") if tag.strip()]

    try:
        # Get configuration
        config = get_config()

        # Create uploader
        uploader = YouTubeUploader(config)

        # Upload video
        video_id = uploader.upload_video(
            file_path=args.file,
            title=args.title,
            description=args.description,
            tags=tags,
            privacy_status=args.privacy_status
        )

        # Print success message
        print(f"Uploaded video successfully. id={video_id}")
        print(f"Watch at: https://youtube.com/watch?v={video_id}")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
