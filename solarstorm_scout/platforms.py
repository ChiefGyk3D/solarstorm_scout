# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""
hypeman-social's Bluesky and Mastodon platforms, with two things this bot
needs that landed in hypeman 0.3.0:

  * pictures that *are* the post (``stream_data['images']``: the D-RAP map,
    the aurora oval, the X-ray chart), each with alt text;
  * Mastodon authenticating with an access token alone, the way the bot's
    .env.example has always described it.

On hypeman 0.3.0 or later the library does both and these classes are plain
passthroughs. On 0.2.0 they fill the gap themselves. Once the lock resolves
0.3.0 this module can go and social.py can import the library classes
directly; nothing else changes.
"""
from __future__ import annotations

import logging
import re

from hypeman_social.config import get_bool_config, get_config
from hypeman_social.social import bluesky as _bluesky
from hypeman_social.social import mastodon as _mastodon
from hypeman_social.social.base import platform_secret

try:  # hypeman >= 0.3.0 attaches images and accepts token-only Mastodon itself
    from hypeman_social.social.base import attached_images  # noqa: F401

    LIBRARY_HAS_IMAGES = True
except ImportError:
    LIBRARY_HAS_IMAGES = False

logger = logging.getLogger(__name__)

#: Bluesky and Mastodon both stop at four pictures per post.
MAX_IMAGES_PER_POST = 4

_IMAGE_SIGNATURES = (
    (b'\x89PNG\r\n\x1a\n', 'image/png'),
    (b'\xff\xd8\xff', 'image/jpeg'),
    (b'GIF87a', 'image/gif'),
    (b'GIF89a', 'image/gif'),
)


def sniff_image_mime(data: bytes, fallback: str = 'image/png') -> str:
    """The media type of an image from its first bytes."""
    for signature, mime in _IMAGE_SIGNATURES:
        if data.startswith(signature):
            return mime
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'
    return fallback


def images_in(stream_data: dict | None) -> list[dict]:
    """
    ``stream_data['images']`` as ``{data, alt, mime_type}`` dicts, bytes only.

    Entries without bytes are dropped with a warning, never raised: a
    missing picture must not cost the post. Capped at four.
    """
    entries = (stream_data or {}).get('images') or []
    resolved = []
    for index, entry in enumerate(entries):
        if len(resolved) >= MAX_IMAGES_PER_POST:
            logger.warning(f"⚠ Post carries more than {MAX_IMAGES_PER_POST} images; dropping the rest")
            break
        data = entry.get('data') if isinstance(entry, dict) else None
        if not isinstance(data, (bytes, bytearray)) or not data:
            logger.warning(f"⚠ Image {index + 1} has no data; skipping")
            continue
        data = bytes(data)
        resolved.append({
            'data': data,
            'alt': str(entry.get('alt') or ''),
            'mime_type': entry.get('mime_type') or sniff_image_mime(data),
        })
    return resolved


def _library_handles_images() -> bool:
    """Read at call time so tests can exercise both paths."""
    return LIBRARY_HAS_IMAGES


class BlueskyPlatform(_bluesky.BlueskyPlatform):
    """hypeman's Bluesky platform, attaching images on hypeman 0.2.0."""

    def post(self, message, reply_to_id=None, platform_name=None, stream_data=None):
        images = [] if _library_handles_images() else images_in(stream_data)
        if not images:
            return super().post(message, reply_to_id, platform_name, stream_data)
        if not self.enabled or not self.client:
            return None

        try:
            models, client_utils = _bluesky.models, _bluesky.client_utils

            # Hashtags become tag facets, as the library does; these posts
            # carry no URLs, so no link facets or cards are needed.
            builder = client_utils.TextBuilder()
            last = 0
            for match in re.finditer(r'#\w+', message):
                if match.start() > last:
                    builder.text(message[last:match.start()])
                builder.tag(match.group(), match.group()[1:])
                last = match.end()
            if last < len(message):
                builder.text(message[last:])

            uploaded = []
            for index, image in enumerate(images):
                try:
                    blob = self.client.upload_blob(image['data']).blob
                    uploaded.append(models.AppBskyEmbedImages.Image(alt=image['alt'], image=blob))
                except Exception as e:  # noqa: BLE001  # the text still goes out; error is logged
                    logger.warning(f"⚠ Could not upload image {index + 1} to Bluesky: {e}")
            embed = models.AppBskyEmbedImages.Main(images=uploaded) if uploaded else None

            reply_ref = None
            if reply_to_id:
                parent = self.client.app.bsky.feed.get_posts({'uris': [reply_to_id]}).posts[0]
                reply = getattr(parent.record, 'reply', None)
                root_ref = reply.root if reply else models.create_strong_ref(parent)
                reply_ref = models.AppBskyFeedPost.ReplyRef(
                    parent=models.create_strong_ref(parent), root=root_ref)

            response = self.client.send_post(builder, reply_to=reply_ref, embed=embed)
            return response.uri if hasattr(response, 'uri') else None
        except Exception as e:  # noqa: BLE001  # reported as None to the caller; error is logged
            logger.error(f"✗ Bluesky post failed: {type(e).__name__}: {e}")
            return None


class MastodonPlatform(_mastodon.MastodonPlatform):
    """hypeman's Mastodon platform: token-only auth and images on hypeman 0.2.0."""

    def authenticate(self):
        if _library_handles_images():
            return super().authenticate()
        if not get_bool_config('Mastodon', 'enable_posting', default=False):
            return False
        if not _mastodon.MASTODON_AVAILABLE:
            logger.error("✗ Mastodon enabled but Mastodon.py is not installed")
            return False

        access_token = platform_secret('Mastodon', 'access_token')
        api_base_url = get_config('Mastodon', 'api_base_url')
        client_id = platform_secret('Mastodon', 'client_id')
        client_secret = platform_secret('Mastodon', 'client_secret')
        if not access_token or not api_base_url:
            logger.warning("✗ Mastodon missing credentials: access_token and/or api_base_url")
            return False

        try:
            kwargs = {'access_token': access_token, 'api_base_url': api_base_url}
            if client_id and client_secret:
                kwargs.update(client_id=client_id, client_secret=client_secret)
            self.client = _mastodon.Mastodon(**kwargs)
            self.enabled = True
            self.authenticated = True
            logger.info("✓ Mastodon authenticated")
            return True
        except Exception as e:  # noqa: BLE001  # reported as False to the caller; only the type is logged
            logger.warning(f"✗ Mastodon authentication failed: {type(e).__name__}")
            return False

    def post(self, message, reply_to_id=None, platform_name=None, stream_data=None):
        images = [] if _library_handles_images() else images_in(stream_data)
        if not images:
            return super().post(message, reply_to_id, platform_name, stream_data)
        if not self.enabled or not self.client:
            return None

        try:
            media_ids = []
            for index, image in enumerate(images):
                try:
                    media = self.client.media_post(
                        image['data'], mime_type=image['mime_type'], description=image['alt'] or None)
                    media_ids.append(media['id'])
                except Exception as e:  # noqa: BLE001  # the text still goes out; error is logged
                    logger.warning(f"⚠ Could not upload image {index + 1} to Mastodon: {e}")
            status = self.client.status_post(
                message, in_reply_to_id=reply_to_id, media_ids=media_ids or None)
            return str(status['id'])
        except Exception as e:  # noqa: BLE001  # reported as None to the caller; error is logged
            logger.error(f"✗ Mastodon post failed: {type(e).__name__}: {e}")
            return None
