# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""
Social Media Poster for SolarStorm Scout
Supports Bluesky and Mastodon with threading and images.
"""

import logging
import re
import io
import aiohttp
from typing import Optional, List, Dict
from pathlib import Path
from atproto import Client, client_utils, models
from mastodon import Mastodon
from .formatter import format_thread_posts
from .chart_renderer import plot_xray_flux

logger = logging.getLogger(__name__)


async def download_image(
    url: str, session: Optional[aiohttp.ClientSession] = None
) -> Optional[bytes]:
    """Download image from URL."""
    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True

    try:
        async with session.get(url, timeout=30) as resp:
            if resp.status == 200:
                return await resp.read()
    except Exception as e:
        logger.error(f"Failed to download image from {url}: {e}")
    finally:
        if close_session:
            await session.close()

    return None


class BlueskyPoster:
    """Bluesky social platform with threading and image support."""

    def __init__(self, handle: str, app_password: str):
        """
        Initialize Bluesky poster.

        Args:
            handle: Bluesky handle (e.g., username.bsky.social)
            app_password: App-specific password from Bluesky settings
        """
        self.handle = handle
        self.app_password = app_password
        self.client = None
        self.authenticated = False

    def authenticate(self) -> bool:
        """
        Authenticate with Bluesky.

        Returns:
            True if authentication successful
        """
        try:
            self.client = Client()
            self.client.login(self.handle, self.app_password)
            self.authenticated = True
            logger.info(f"✓ Bluesky authenticated as {self.handle}")
            return True
        except Exception as e:
            logger.error(f"✗ Bluesky authentication failed: {e}")
            self.authenticated = False
            return False

    async def post_thread(
        self, posts: List[Dict], session: Optional[aiohttp.ClientSession] = None
    ) -> bool:
        """
        Post a thread to Bluesky with images.

        Args:
            posts: List of post dicts with 'text', 'image_url', and 'alt_text'
            session: Optional aiohttp session for downloading images

        Returns:
            True if thread posted successfully
        """
        if not self.authenticated or not self.client:
            logger.error("Not authenticated with Bluesky")
            return False

        try:
            reply_to = None

            for i, post_data in enumerate(posts):
                message = post_data["text"]
                image_url = post_data.get("image_url")
                alt_text = post_data.get("alt_text", "")

                # Use TextBuilder for rich text with hashtags
                text_builder = client_utils.TextBuilder()

                # Pattern for hashtags
                hashtag_pattern = r"#\w+"
                last_pos = 0

                for match in re.finditer(hashtag_pattern, message):
                    # Add text before hashtag
                    if match.start() > last_pos:
                        text_builder.text(message[last_pos : match.start()])

                    # Add hashtag as tag
                    hashtag = match.group()
                    text_builder.tag(hashtag, hashtag[1:])  # Remove # for tag
                    last_pos = match.end()

                # Add remaining text
                if last_pos < len(message):
                    text_builder.text(message[last_pos:])

                # Handle image
                embed = None
                if image_url:
                    # Check if we need to generate chart or download image
                    if image_url == "GENERATE_CHART":
                        # Generate GOES X-ray chart
                        logger.info("Generating GOES X-ray flux chart...")
                        chart_buf = await plot_xray_flux("6h")
                        if chart_buf:
                            img_data = chart_buf.getvalue()
                        else:
                            img_data = None
                            logger.warning("Failed to generate X-ray chart")
                    else:
                        # Download image from URL
                        img_data = await download_image(image_url, session)

                    if img_data:
                        try:
                            upload = self.client.upload_blob(img_data)
                            embed = models.AppBskyEmbedImages.Main(
                                images=[
                                    models.AppBskyEmbedImages.Image(
                                        alt=alt_text, image=upload.blob
                                    )
                                ]
                            )
                            logger.info(f"Added image to post {i+1}")
                        except Exception as e:
                            logger.warning(
                                f"Failed to upload image for post {i+1}: {e}"
                            )

                # Post with reply_to for threading
                if reply_to:
                    post = self.client.send_post(
                        text_builder, reply_to=reply_to, embed=embed
                    )
                else:
                    post = self.client.send_post(text_builder, embed=embed)

                reply_to = models.AppBskyFeedPost.ReplyRef(
                    parent=models.ComAtprotoRepoStrongRef.Main(
                        cid=post.cid, uri=post.uri
                    ),
                    root=models.ComAtprotoRepoStrongRef.Main(
                        cid=post.cid if not reply_to else reply_to.root.cid,
                        uri=post.uri if not reply_to else reply_to.root.uri,
                    ),
                )

                logger.info(f"Posted Bluesky message {i+1}/{len(posts)}")

            logger.info(f"✓ Posted Bluesky thread ({len(posts)} posts)")
            return True

        except Exception as e:
            logger.error(f"✗ Error posting Bluesky thread: {e}")
            return False


class MastodonPoster:
    """Mastodon social platform with threading and image support."""

    def __init__(
        self,
        api_base_url: str,
        access_token: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        """
        Initialize Mastodon poster.

        Args:
            api_base_url: Mastodon instance URL
            access_token: Access token for authentication
            client_id: OAuth client ID (optional)
            client_secret: OAuth client secret (optional)
        """
        self.api_base_url = api_base_url
        self.access_token = access_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.client = None
        self.authenticated = False

    def authenticate(self) -> bool:
        """
        Authenticate with Mastodon.

        Returns:
            True if authentication successful
        """
        try:
            if self.client_id and self.client_secret:
                self.client = Mastodon(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    access_token=self.access_token,
                    api_base_url=self.api_base_url,
                )
            else:
                # Simplified authentication with just access token
                self.client = Mastodon(
                    access_token=self.access_token, api_base_url=self.api_base_url
                )

            # Verify credentials
            self.client.account_verify_credentials()
            self.authenticated = True
            logger.info(f"✓ Mastodon authenticated at {self.api_base_url}")
            return True

        except Exception as e:
            logger.error(f"✗ Mastodon authentication failed: {e}")
            self.authenticated = False
            return False

    async def post_thread(
        self, posts: List[Dict], session: Optional[aiohttp.ClientSession] = None
    ) -> bool:
        """
        Post a thread to Mastodon with images.

        Args:
            posts: List of post dicts with 'text', 'image_url', and 'alt_text'
            session: Optional aiohttp session for downloading images

        Returns:
            True if thread posted successfully
        """
        if not self.authenticated or not self.client:
            logger.error("Not authenticated with Mastodon")
            return False

        try:
            reply_to_id = None

            for i, post_data in enumerate(posts):
                message = post_data["text"]
                image_url = post_data.get("image_url")
                alt_text = post_data.get("alt_text", "")

                # Handle image
                media_ids = []
                if image_url:
                    # Check if we need to generate chart or download image
                    if image_url == "GENERATE_CHART":
                        # Generate GOES X-ray chart
                        logger.info("Generating GOES X-ray flux chart...")
                        chart_buf = await plot_xray_flux("6h")
                        if chart_buf:
                            img_data = chart_buf.getvalue()
                        else:
                            img_data = None
                            logger.warning("Failed to generate X-ray chart")
                    else:
                        # Download image from URL
                        img_data = await download_image(image_url, session)

                    if img_data:
                        try:
                            # Write to temp file for Mastodon.py
                            import tempfile
                            import os

                            with tempfile.NamedTemporaryFile(
                                delete=False, suffix=".png"
                            ) as tmp:
                                tmp.write(img_data)
                                tmp_path = tmp.name

                            media = self.client.media_post(
                                tmp_path, description=alt_text
                            )
                            media_ids.append(media["id"])
                            logger.info(f"Added image to post {i+1}")

                            # Clean up temp file
                            os.unlink(tmp_path)
                        except Exception as e:
                            logger.warning(
                                f"Failed to upload image for post {i+1}: {e}"
                            )

                # Post with in_reply_to_id for threading
                status = self.client.status_post(
                    message,
                    in_reply_to_id=reply_to_id,
                    media_ids=media_ids if media_ids else None,
                    visibility="public",
                )

                reply_to_id = status["id"]
                logger.info(f"Posted Mastodon message {i+1}/{len(posts)}")

            logger.info(f"✓ Posted Mastodon thread ({len(posts)} posts)")
            return True

        except Exception as e:
            logger.error(f"✗ Error posting Mastodon thread: {e}")
            return False


class SocialMediaManager:
    """Manages posting to multiple social media platforms."""

    def __init__(self):
        self.platforms = []

    def add_bluesky(self, handle: str, app_password: str) -> bool:
        """
        Add Bluesky platform.

        Returns:
            True if added and authenticated successfully
        """
        poster = BlueskyPoster(handle, app_password)
        if poster.authenticate():
            self.platforms.append(("Bluesky", poster))
            return True
        return False

    def add_mastodon(
        self,
        api_base_url: str,
        access_token: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> bool:
        """
        Add Mastodon platform.

        Returns:
            True if added and authenticated successfully
        """
        poster = MastodonPoster(api_base_url, access_token, client_id, client_secret)
        if poster.authenticate():
            self.platforms.append(("Mastodon", poster))
            return True
        return False

    async def post_to_all(
        self,
        data: Dict,
        session: Optional[aiohttp.ClientSession] = None,
        include_hamradio: bool = True,
    ) -> dict:
        """
        Post thread to all configured platforms.

        Args:
            data: Space weather data dict
            session: Optional aiohttp session
            include_hamradio: Whether to include #HamRadio hashtag

        Returns:
            Dict with platform names as keys and success status as values
        """
        results = {}

        for platform_name, poster in self.platforms:
            try:
                # Format posts for this platform
                platform = "bluesky" if platform_name == "Bluesky" else "mastodon"
                posts = format_thread_posts(data, platform, include_hamradio)

                success = await poster.post_thread(posts, session)
                results[platform_name] = success
            except Exception as e:
                logger.error(f"Error posting to {platform_name}: {e}")
                results[platform_name] = False

        return results

    def get_platform_count(self) -> int:
        """Get number of configured platforms."""
        return len(self.platforms)

    def get_platform_names(self) -> List[str]:
        """Get list of configured platform names."""
        return [name for name, _ in self.platforms]
