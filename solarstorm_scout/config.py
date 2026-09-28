# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""
Configuration for SolarStorm Scout, on hypeman-social's config layer.

The bot used to carry its own Config class: a .env loader plus a Doppler
client that re-fetched the whole project on every lookup. hypeman-social
does the same job for Boon-Tube-Daemon, stream-daemon and Star-Daemon, with
one Doppler fetch per process and the AWS/Vault backends thrown in, so this
module is now the thin layer that says what is SolarStorm Scout's own:

  * the original BLUESKY_ENABLED / MASTODON_ENABLED switches keep working
    (hypeman's platforms read BLUESKY_ENABLE_POSTING / MASTODON_ENABLE_POSTING),
  * which social networks this bot posts to.

Everything else — LLM_*, LOG_*, DOPPLER_*, BLUESKY_*, MASTODON_* — is read
by hypeman directly; the reference is docs/CONFIGURATION.md in that project.
"""
from __future__ import annotations

import logging
import os

from hypeman_social.config import get_bool_config, get_config, get_secret, load_config
from hypeman_social.observability import configure_logging

logger = logging.getLogger(__name__)

__all__ = [
    'LEGACY_PLATFORM_FLAGS',
    'PLATFORMS',
    'apply_legacy_keys',
    'enabled_platforms',
    'get_bool_config',
    'get_config',
    'get_secret',
    'load',
    'setup_logging',
]

#: The networks this bot posts to, in posting order. hypeman knows more
#: (Discord, Matrix, Threads), but their embeds are shaped for stream and
#: video announcements, not a five-post data thread with pictures.
PLATFORMS = ('bluesky', 'mastodon')

#: The bot's original enable switches, mapped to the names hypeman reads.
#: A deployment that set BLUESKY_ENABLED=true in 2024 keeps posting.
LEGACY_PLATFORM_FLAGS = {
    'BLUESKY_ENABLED': 'BLUESKY_ENABLE_POSTING',
    'MASTODON_ENABLED': 'MASTODON_ENABLE_POSTING',
}


def load(env_file: str = '.env') -> bool:
    """
    Load the .env file (if present) and translate the legacy key names.

    Returns True when a .env file was found. Values already in the
    environment always win over the file, as before.
    """
    found = load_config(env_file)
    apply_legacy_keys()
    return found


def apply_legacy_keys() -> None:
    """
    Copy BLUESKY_ENABLED / MASTODON_ENABLED onto the names hypeman reads.

    Only fills a gap: an explicit BLUESKY_ENABLE_POSTING is never overwritten.
    """
    for old, new in LEGACY_PLATFORM_FLAGS.items():
        old_value = os.getenv(old)
        if old_value and not os.getenv(new):
            os.environ[new] = old_value
            logger.info(f"ℹ️  {old} is the old name for {new}; both keep working")


def enabled_platforms() -> list[str]:
    """Names of the networks switched on in configuration, in posting order."""
    return [name for name in PLATFORMS
            if get_bool_config(name.capitalize(), 'enable_posting', default=False)]


def setup_logging(log_level: str | None = None) -> None:
    """
    Configure logging through hypeman.

    LOG_LEVEL is honoured as before. Under systemd the timestamp is left to
    journald, and LOG_FILE / LOG_DEDUPE_SECONDS work the way they do in the
    other daemons.
    """
    configure_logging(level=log_level, force=True)
