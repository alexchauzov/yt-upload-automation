"""Main CLI application for YouTube video publishing."""
import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from adapters.google_sheets_repository import GoogleSheetsMetadataRepository
from adapters.local_storage import LocalFileStorage
from adapters.youtube_backend import YouTubeApiBackend
from domain.services import PublishService


def setup_logging(verbose: bool = False) -> None:
    """
    Configure logging.

    Args:
        verbose: Enable debug logging if True.
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Reduce noise from Google API client
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)


def create_publish_service(dry_run: bool = False, max_retries: int = 3) -> PublishService:
    """
    Create and wire up PublishService with dependencies.

    Args:
        dry_run: Enable dry-run mode (validate only, don't upload).
        max_retries: Maximum retry attempts for retryable errors.

    Returns:
        Configured PublishService instance.

    Raises:
        SystemExit: If configuration is invalid.
    """
    logger = logging.getLogger(__name__)

    try:
        # Initialize storage
        storage_base_path = os.getenv("STORAGE_BASE_PATH")
        storage = LocalFileStorage(base_path=storage_base_path)
        logger.debug(f"Storage initialized: base_path={storage_base_path or 'current directory'}")

        # Initialize metadata repository
        metadata_repo = GoogleSheetsMetadataRepository()
        logger.debug("Metadata repository initialized: Google Sheets")

        # Initialize video backend (skip in dry-run mode to avoid OAuth)
        if dry_run:
            video_backend = None  # Not used in dry-run
            logger.info("DRY RUN mode enabled - will validate only, no uploads")
        else:
            video_backend = YouTubeApiBackend()
            logger.debug("Video backend initialized: YouTube API")

        # Create publish service
        service = PublishService(
            metadata_repo=metadata_repo,
            storage=storage,
            video_backend=video_backend,
            max_retries=max_retries,
            dry_run=dry_run,
        )

        logger.info("PublishService initialized successfully")
        return service

    except Exception as e:
        logger.error(f"Failed to initialize service: {e}")
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="YouTube Publisher - Automated video publishing from Google Sheets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  GOOGLE_SHEETS_ID              Google Sheets document ID (required)
  GOOGLE_SHEETS_RANGE           Sheet range (default: Videos!A:Z)
  GOOGLE_APPLICATION_CREDENTIALS Path to service account JSON (required)
  YOUTUBE_CLIENT_SECRETS_FILE   Path to OAuth2 client secrets (default: client_secrets.json)
  YOUTUBE_TOKEN_FILE            Path to store OAuth token (default: .data/youtube_token.pickle)
  STORAGE_BASE_PATH             Base path for video files (default: current directory)
  SHEETS_READY_STATUS           Status to filter tasks (default: READY)

Examples:
  # Normal run - publish all READY tasks
  python -m app.main

  # Dry-run mode - validate only, don't upload
  python -m app.main --dry-run

  # Verbose logging
  python -m app.main --verbose

  # Custom max retries
  python -m app.main --max-retries 5
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate tasks without uploading (sets status to DRY_RUN_OK)",
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retry attempts for retryable errors (default: 3)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging",
    )

    args = parser.parse_args()

    # Load environment variables
    env_file = Path(".env")
    if env_file.exists():
        load_dotenv(env_file)
        print(f"Loaded environment from {env_file}")

    # Setup logging
    setup_logging(verbose=args.verbose)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("YouTube Publisher - Starting")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("MODE: DRY RUN (validation only)")
    else:
        logger.info("MODE: PRODUCTION (will upload videos)")

    # Create service
    service = create_publish_service(
        dry_run=args.dry_run,
        max_retries=args.max_retries,
    )

    # Execute publishing workflow
    try:
        logger.info("Starting publish workflow...")
        stats = service.publish_all_ready_tasks()

        logger.info("=" * 60)
        logger.info("Workflow completed")
        logger.info("=" * 60)
        logger.info(f"  Processed: {stats['processed']}")
        logger.info(f"  Succeeded: {stats['succeeded']}")
        logger.info(f"  Failed:    {stats['failed']}")
        logger.info(f"  Skipped:   {stats['skipped']}")
        logger.info("=" * 60)

        # Exit with error code if any tasks failed
        if stats["failed"] > 0:
            sys.exit(1)

    except KeyboardInterrupt:
        logger.warning("\nInterrupted by user")
        sys.exit(130)

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
