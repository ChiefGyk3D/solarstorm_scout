#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""
SolarStorm Scout - Space Weather Social Media Bot
Posts HF propagation updates to Bluesky and Mastodon.
"""

import sys
import asyncio
import logging
import time
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from solarstorm_scout.config import Config, setup_logging
from solarstorm_scout.spaceweather import fetch_space_weather_data
from solarstorm_scout.formatter import format_thread_posts
from solarstorm_scout.social import SocialMediaManager

logger = logging.getLogger(__name__)


# Anti-spam protection and tracking
# Works in both Docker (/app/logs) and local install (project_dir/logs)
def get_tracking_dir() -> Path:
    """Get path to tracking directory, works in Docker and local."""
    # Check if running in Docker
    docker_logs = Path("/app/logs")
    if docker_logs.exists() and docker_logs.is_dir():
        return docker_logs
    # Local installation
    return Path(__file__).parent.parent / "logs"


def get_last_run_file() -> Path:
    """Get path to last run tracking file."""
    return get_tracking_dir() / ".last_run"


def get_last_hamradio_file() -> Path:
    """Get path to last #HamRadio usage tracking file."""
    return get_tracking_dir() / ".last_hamradio"


LAST_RUN_FILE = get_last_run_file()
LAST_HAMRADIO_FILE = get_last_hamradio_file()
MIN_INTERVAL_MINUTES = 30  # Minimum 30 minutes between posts
HAMRADIO_INTERVAL_HOURS = 24  # Only use #HamRadio once per day


def check_rate_limit() -> bool:
    """
    Check if enough time has passed since last run to prevent spam.

    Returns:
        True if OK to post, False if too soon
    """
    if not LAST_RUN_FILE.exists():
        return True

    try:
        last_run_time = float(LAST_RUN_FILE.read_text().strip())
        time_since_last = time.time() - last_run_time
        minutes_since_last = time_since_last / 60

        if minutes_since_last < MIN_INTERVAL_MINUTES:
            wait_minutes = MIN_INTERVAL_MINUTES - minutes_since_last
            logger.warning(
                f"⚠ Rate limit: Last post was {minutes_since_last:.1f} minutes ago"
            )
            logger.warning(f"⚠ Minimum interval is {MIN_INTERVAL_MINUTES} minutes")
            logger.warning(f"⚠ Please wait {wait_minutes:.1f} more minutes")
            return False

        return True
    except Exception as e:
        logger.warning(f"Could not read last run time: {e}. Proceeding...")
        return True


def record_run_time():
    """Record current timestamp to prevent spam."""
    try:
        LAST_RUN_FILE.parent.mkdir(parents=True, exist_ok=True)
        LAST_RUN_FILE.write_text(str(time.time()))
    except Exception as e:
        logger.warning(f"Could not record run time: {e}")


def should_include_hamradio() -> bool:
    """
    Check if #HamRadio hashtag should be included in this post.
    Only includes it once per 24 hours.

    Returns:
        True if #HamRadio should be included, False otherwise
    """
    if not LAST_HAMRADIO_FILE.exists():
        return True

    try:
        last_hamradio_time = float(LAST_HAMRADIO_FILE.read_text().strip())
        time_since_last = time.time() - last_hamradio_time
        hours_since_last = time_since_last / 3600

        if hours_since_last >= HAMRADIO_INTERVAL_HOURS:
            return True
        else:
            logger.info(
                f"ℹ️  #HamRadio last used {hours_since_last:.1f} hours ago (limit: {HAMRADIO_INTERVAL_HOURS}h)"
            )
            return False
    except Exception as e:
        logger.warning(
            f"Could not read last #HamRadio time: {e}. Including #HamRadio..."
        )
        return True


def record_hamradio_usage():
    """Record current timestamp for #HamRadio usage."""
    try:
        LAST_HAMRADIO_FILE.parent.mkdir(parents=True, exist_ok=True)
        LAST_HAMRADIO_FILE.write_text(str(time.time()))
        logger.info("✓ Recorded #HamRadio usage timestamp")
    except Exception as e:
        logger.warning(f"Could not record #HamRadio usage time: {e}")


async def main():
    """Main bot execution."""
    # Setup logging
    log_level = Config().get("LOG_LEVEL", "INFO")
    setup_logging(log_level)

    logger.info("=" * 50)
    logger.info("🌞 SolarStorm Scout Starting")
    logger.info("=" * 50)

    # Anti-spam check
    if not check_rate_limit():
        logger.error("Exiting due to rate limit")
        sys.exit(1)

    # Load configuration
    config = Config()

    # Validate configuration
    if not config.validate_config():
        logger.error("Configuration validation failed!")
        sys.exit(1)

    # Setup social media manager
    social = SocialMediaManager()

    # Add platforms
    if config.is_bluesky_enabled():
        try:
            handle, password = config.get_bluesky_config()
            if social.add_bluesky(handle, password):
                logger.info("✓ Bluesky platform added")
            else:
                logger.warning("✗ Failed to add Bluesky platform")
        except Exception as e:
            logger.error(f"Error setting up Bluesky: {e}")

    if config.is_mastodon_enabled():
        try:
            api_url, token, client_id, client_secret = config.get_mastodon_config()
            if social.add_mastodon(api_url, token, client_id, client_secret):
                logger.info("✓ Mastodon platform added")
            else:
                logger.warning("✗ Failed to add Mastodon platform")
        except Exception as e:
            logger.error(f"Error setting up Mastodon: {e}")

    # Check if any platforms were added
    if social.get_platform_count() == 0:
        logger.error("No social media platforms configured successfully!")
        sys.exit(1)

    logger.info(f"Configured platforms: {', '.join(social.get_platform_names())}")

    # Fetch space weather data
    logger.info("Fetching space weather data from NOAA...")
    try:
        data = await fetch_space_weather_data()
        logger.info("✓ Space weather data fetched successfully")

        # Log key data points
        logger.info(f"  Solar Flux: {data.get('solar_flux', 'N/A')} sfu")
        logger.info(f"  K-index: {data.get('k_index', 'N/A')}")
        logger.info(f"  Conditions: {data.get('propagation_conditions', 'N/A')}")
        logger.info(f"  X-Ray: {data.get('xray_class', 'N/A')}")

        # Validate critical data is present
        critical_fields = ["solar_flux", "k_index", "xray_class"]
        missing_fields = [
            field for field in critical_fields if data.get(field) == "N/A"
        ]

        if missing_fields:
            logger.error(
                f"Critical data missing from NOAA: {', '.join(missing_fields)}"
            )
            logger.error(
                "Cannot post without complete space weather data. Will retry on next scheduled run."
            )
            sys.exit(1)

    except Exception as e:
        logger.error(f"Failed to fetch space weather data: {e}")
        sys.exit(1)

    # Check if we should include #HamRadio hashtag
    include_hamradio = should_include_hamradio()
    if include_hamradio:
        logger.info("✓ Including #HamRadio hashtag in this thread")
    else:
        logger.info("ℹ️  Skipping #HamRadio hashtag (used recently)")

    # Format posts (we'll post to each platform separately with platform-specific formatting)
    logger.info("Posting to social media...")
    try:
        results = await social.post_to_all(data, include_hamradio=include_hamradio)

        # Log results
        success_count = sum(1 for v in results.values() if v)
        logger.info(f"Posted to {success_count}/{len(results)} platforms")

        for platform, success in results.items():
            if success:
                logger.info(f"  ✓ {platform}: Success")
            else:
                logger.warning(f"  ✗ {platform}: Failed")

        if success_count == 0:
            logger.error("Failed to post to any platforms!")
            sys.exit(1)

        # Record successful post time to prevent spam
        record_run_time()

        # Record #HamRadio usage if it was included
        if include_hamradio:
            record_hamradio_usage()

    except Exception as e:
        logger.error(f"Failed to post to social media: {e}")
        sys.exit(1)

    logger.info("=" * 50)
    logger.info("🌞 SolarStorm Scout Completed Successfully")
    logger.info("=" * 50)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
