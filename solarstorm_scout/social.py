# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""
Social Media Poster for SolarStorm Scout, on hypeman-social's platforms.

Bluesky and Mastodon used to be implemented here: login, rich-text facets,
reply chains, image upload, each its own copy of code that Boon-Tube-Daemon,
stream-daemon and Star-Daemon also carried. hypeman-social is that code,
shared. What stays here is the bot's own business: turning the data into a
thread, fetching the NOAA pictures once per run, rendering the X-ray chart,
and walking each network through the thread post by post.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

import aiohttp
from hypeman_social.social import SocialPlatform

from .chart_renderer import plot_xray_flux
from .config import enabled_platforms
from .formatter import briefing_char_budget, format_thread_posts
from .platforms import BlueskyPlatform, MastodonPlatform

logger = logging.getLogger(__name__)

#: hypeman platform classes for the networks this bot posts to (see
#: platforms.py for the thin layer over them). Each one reads its own
#: configuration (BLUESKY_HANDLE, MASTODON_ACCESS_TOKEN, ...) through
#: hypeman's config and secret chain.
PLATFORM_CLASSES: dict[str, type[SocialPlatform]] = {
    'bluesky': BlueskyPlatform,
    'mastodon': MastodonPlatform,
}

#: Marker in a post's image_url meaning "render the X-ray chart" rather than
#: "download this".
GENERATE_CHART = "GENERATE_CHART"

#: Something that produces the briefing for one network, given the data and
#: the characters available, or None to leave it out.
BriefingSource = Callable[[dict, int, str], "str | None"]


async def download_image(
    url: str, session: aiohttp.ClientSession | None = None
) -> bytes | None:
    """Download image from URL."""
    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                return await resp.read()
            logger.error(f"Image download returned HTTP {resp.status}: {url}")
    except Exception as e:  # noqa: BLE001  # post goes out without the image; error is logged
        logger.error(f"Failed to download image from {url}: {e}")
    finally:
        if close_session:
            await session.close()

    return None


class ImageCache:
    """
    Pictures for this run, fetched or rendered once and reused per network.

    Two networks used to mean two downloads of the same D-RAP map and two
    renders of the same chart. A miss is remembered too, so a NOAA image
    that is down is asked for once, not once per post.
    """

    def __init__(self, session: aiohttp.ClientSession | None = None):
        self.session = session
        self._images: dict[str, bytes | None] = {}

    async def get(self, image_url: str) -> bytes | None:
        if image_url in self._images:
            return self._images[image_url]

        if image_url == GENERATE_CHART:
            logger.info("Generating GOES X-ray flux chart...")
            chart = await plot_xray_flux("6h")
            data = chart.getvalue() if chart else None
            if data is None:
                logger.warning("Failed to generate X-ray chart")
        else:
            data = await download_image(image_url, self.session)

        self._images[image_url] = data
        return data


class SocialMediaManager:
    """Manages posting the thread to every configured network."""

    def __init__(self):
        self.platforms: list[tuple[str, SocialPlatform]] = []

    def add_platform(self, name: str, platform: SocialPlatform | None = None) -> bool:
        """
        Authenticate one network and keep it if that works.

        Args:
            name: 'bluesky' or 'mastodon'.
            platform: An instance to use instead of constructing one; for tests.

        Returns:
            True if the platform authenticated and will be posted to.
        """
        key = name.lower()
        if platform is None:
            cls = PLATFORM_CLASSES.get(key)
            if cls is None:
                logger.error(f"✗ Unknown platform: {name}")
                return False
            platform = cls()

        if platform.authenticate():
            self.platforms.append((key, platform))
            return True
        return False

    def configure_all(self) -> list[str]:
        """
        Bring up every network that is switched on in configuration.

        Returns:
            Names of the platforms that authenticated.
        """
        enabled = enabled_platforms()
        if not enabled:
            logger.error(
                "✗ No social media platforms enabled! Set BLUESKY_ENABLE_POSTING=true "
                "and/or MASTODON_ENABLE_POSTING=true"
            )
            return []

        for name in enabled:
            if self.add_platform(name):
                logger.info(f"✓ {name.capitalize()} platform added")
            else:
                logger.warning(f"✗ Failed to add {name.capitalize()} platform")

        return self.get_platform_names()

    async def post_thread(
        self,
        platform: SocialPlatform,
        posts: list[dict],
        images: ImageCache | None = None,
    ) -> bool:
        """
        Post a thread to one network, each post replying to the one before.

        Args:
            platform: An authenticated hypeman platform.
            posts: Dicts with 'text', 'image_url' and 'alt_text', in order.
            images: Shared picture cache for this run.

        Returns:
            True if every post went out. A failure part-way leaves the
            earlier posts up and reports False; the next scheduled run
            posts a fresh thread.
        """
        images = images or ImageCache()
        reply_to = None

        for index, post_data in enumerate(posts, start=1):
            stream_data = None
            image_url = post_data.get("image_url")
            if image_url:
                data = await images.get(image_url)
                if data:
                    stream_data = {"images": [{"data": data, "alt": post_data.get("alt_text", "")}]}
                else:
                    logger.warning(f"Posting {platform.name} message {index} without its image")

            post_id = platform.safe_post(
                post_data["text"], reply_to_id=reply_to, stream_data=stream_data
            )
            if not post_id:
                logger.error(f"✗ {platform.name} message {index}/{len(posts)} failed; thread incomplete")
                return False

            reply_to = post_id
            logger.info(f"Posted {platform.name} message {index}/{len(posts)}")

        logger.info(f"✓ Posted {platform.name} thread ({len(posts)} posts)")
        return True

    async def post_to_all(
        self,
        data: dict,
        session: aiohttp.ClientSession | None = None,
        include_hamradio: bool = True,
        briefing_source: BriefingSource | None = None,
    ) -> dict:
        """
        Post the thread to all configured platforms.

        Args:
            data: Space weather data dict
            session: Optional aiohttp session for the image downloads
            include_hamradio: Whether to include #HamRadio hashtag
            briefing_source: Produces the on-air briefing for a network, or
                None. Called as (data, max_chars, platform); a None result
                means the thread goes out without a briefing post.

        Returns:
            Dict with platform names as keys and success status as values
        """
        results = {}
        images = ImageCache(session)

        for key, platform in self.platforms:
            try:
                briefing = None
                if briefing_source is not None:
                    briefing = briefing_source(
                        data, briefing_char_budget(key, include_hamradio), key
                    )

                posts = format_thread_posts(data, key, include_hamradio, briefing)
                results[platform.name] = await self.post_thread(platform, posts, images)
            except Exception as e:  # noqa: BLE001  # one platform failing must not block the other; error is logged
                logger.error(f"Error posting to {platform.name}: {e}")
                results[platform.name] = False

        return results

    def get_platform_count(self) -> int:
        """Get number of configured platforms."""
        return len(self.platforms)

    def get_platform_names(self) -> list[str]:
        """Get list of configured platform names."""
        return [platform.name for _, platform in self.platforms]
