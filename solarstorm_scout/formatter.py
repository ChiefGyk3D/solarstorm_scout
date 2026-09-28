# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""
Message Formatter for SolarStorm Scout
Formats space weather data into social media posts.
Bluesky: 300 char max per post
Mastodon: 500 char max per post

The thread is five data posts, numbered (1/5) to (5/5). When the forecaster
has an on-air briefing for this run it opens the thread as one more post and
the numbering shifts to /6; when it does not, the thread is exactly what it
has always been. Numbering is worked out from what is actually in the thread,
so neither case is a special one.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

#: Character limits per network.
CHAR_LIMITS = {'bluesky': 300, 'mastodon': 500}

#: Header of the optional AI briefing post; the numbering is appended.
BRIEFING_HEADER = "🎙️ SPACE WX BRIEFING"

#: Room kept back when budgeting the briefing, so a stray double space or
#: an emoji the model insisted on cannot push the post past the limit.
BRIEFING_MARGIN = 6

# Image URLs from NOAA (actual image files)
DRAP_IMAGE_URL = (
    "https://services.swpc.noaa.gov/images/animations/d-rap/global/d-rap/latest.png"
)
AURORA_IMAGE_URL = (
    "https://services.swpc.noaa.gov/images/animations/ovation/north/latest.jpg"
)
# GOES X-Ray chart is generated locally from JSON data (not a static image)


def ensure_char_limit(text: str, limit: int) -> str:
    """
    Ensure text fits within character limit.
    Raises warning if text is too long (should not happen with proper formatting).

    Args:
        text: Text to check
        limit: Maximum character count

    Returns:
        Text (unchanged if within limit, error logged if not)
    """
    if len(text) > limit:
        logger.error(f"Post exceeds {limit} char limit: {len(text)} chars")
        logger.error(f"Content: {text[:100]}...")
        # This should never happen - our formatting should always fit
        raise ValueError(f"Post formatting error: {len(text)} > {limit} chars")
    return text


def char_limit_for(platform: str) -> int:
    """Character limit for a network; unknown names get Bluesky's, the tighter one."""
    return CHAR_LIMITS.get(platform.lower(), CHAR_LIMITS['bluesky'])


def build_hashtags(include_hamradio: bool) -> str:
    """The hashtag line every post ends with."""
    hashtags = "#SolarStormScout"
    if include_hamradio:
        hashtags += " #HamRadio"
    return hashtags


def briefing_char_budget(platform: str, include_hamradio: bool = True) -> int:
    """
    Characters the forecaster may use for the briefing on this network.

    The limit, minus the header and its numbering, the blank lines around
    the body, the hashtag line, and a small safety margin.
    """
    header = f"{BRIEFING_HEADER} (1/6)\n\n"
    footer = f"\n\n{build_hashtags(include_hamradio)}"
    return char_limit_for(platform) - len(header) - len(footer) - BRIEFING_MARGIN


def format_thread_posts(
    data: dict,
    platform: str = "bluesky",
    include_hamradio: bool = True,
    briefing: str | None = None,
) -> list[dict]:
    """
    Format space weather data into a thread of posts.

    The data posts, in order:
    1. Solar Indices + NOAA Scales
    2. Band Conditions + Best Bands Now
    3. D-Region Absorption (with D-RAP image)
    4. Aurora Forecast (with aurora image)
    5. GOES Solar X-Ray Flux (with generated chart)

    With a briefing, the AI weatherperson's read of the numbers opens the
    thread as one more post and everything is numbered out of six.

    Args:
        data: Space weather data dictionary from spaceweather.fetch_space_weather_data()
        platform: 'bluesky' (300 chars) or 'mastodon' (500 chars)
        include_hamradio: Whether to include #HamRadio hashtag (limited to once per day)
        briefing: Optional on-air briefing text, already fitted to
            briefing_char_budget() for this platform. None means no briefing post.

    Returns:
        List of dicts with 'text', 'image_url', and 'alt_text' keys
    """
    char_limit = char_limit_for(platform)

    # (formatter, image_url, alt_text) in thread order; numbering comes last
    # so the count reflects what is really there.
    parts = []
    if briefing:
        parts.append((
            lambda i, n: format_briefing_post(briefing, i, n, char_limit, include_hamradio),
            None,
            "",
        ))
    parts.extend([
        (lambda i, n: format_solar_indices_post(data, char_limit, include_hamradio, i, n),
         None, ""),
        (lambda i, n: format_band_conditions_post(data, char_limit, include_hamradio, i, n),
         None, ""),
        (lambda i, n: format_absorption_post(data, char_limit, include_hamradio, i, n),
         DRAP_IMAGE_URL,
         "D-Region Absorption Prediction map showing HF radio wave absorption"),
        (lambda i, n: format_aurora_post(data, char_limit, include_hamradio, i, n),
         AURORA_IMAGE_URL,
         "Aurora oval forecast showing auroral activity in northern hemisphere"),
        (lambda i, n: format_xray_post(data, char_limit, include_hamradio, i, n),
         "GENERATE_CHART",  # Special marker to generate chart
         "GOES Solar X-Ray Flux chart for past 6 hours"),
    ])

    total = len(parts)
    return [
        {"text": render(index, total), "image_url": image_url, "alt_text": alt_text}
        for index, (render, image_url, alt_text) in enumerate(parts, start=1)
    ]


def format_briefing_post(
    briefing: str, index: int, total: int, char_limit: int, include_hamradio: bool = True
) -> str:
    """Format the optional opening post: the forecaster's on-air briefing."""
    post = f"""{BRIEFING_HEADER} ({index}/{total})

{briefing.strip()}

{build_hashtags(include_hamradio)}"""

    return ensure_char_limit(post, char_limit)


def format_solar_indices_post(
    data: dict, char_limit: int, include_hamradio: bool = True, index: int = 1, total: int = 5
) -> str:
    """Format the Solar Indices + NOAA Scales post."""
    sfi = data.get("solar_flux", "N/A")
    a_idx = data.get("a_index", "N/A")
    k_idx = data.get("k_index", "N/A")
    fof2 = data.get("fof2", "N/A")
    muf = data.get("muf_dx", "N/A")
    absorption = data.get("absorption_factor", 0)
    r_scale = data.get("r_scale", "N/A")
    s_scale = data.get("s_scale", "N/A")
    g_scale = data.get("g_scale", "N/A")

    # Format absorption percentage
    abs_pct = f"{int(absorption * 100)}%" if isinstance(absorption, float) else "N/A"

    hashtags = build_hashtags(include_hamradio)

    post = f"""☀️ SOLAR INDICES ({index}/{total})

SFI: {sfi}
A-index: {a_idx}
K-index: {k_idx}
foF2: {fof2} MHz
MUF (DX): {muf} MHz
D-Layer: {abs_pct}

📊 NOAA Scales
📻R{r_scale} Radio Blackout
☢️S{s_scale} Radiation Storm
🧲G{g_scale} Geomagnetic Storm

{hashtags}"""

    return ensure_char_limit(post, char_limit)


def format_band_conditions_post(
    data: dict, char_limit: int, include_hamradio: bool = True, index: int = 2, total: int = 5
) -> str:
    """Format the Band Conditions post."""
    bands = data.get("band_conditions", {})
    best_now = data.get("best_bands_now", "N/A")
    muf = data.get("muf_dx", "N/A")

    # Format band list - group to save space
    band_lines = []
    for band_name in [
        "160m",
        "80m",
        "40m",
        "30m",
        "20m",
        "17m",
        "15m",
        "12m",
        "10m",
        "6m",
    ]:
        if band_name in bands:
            b = bands[band_name]
            band_lines.append(f"{band_name}: {b['emoji']} {b['quality']}")

    # Split into chunks to fit character limit
    if char_limit == 300:  # Bluesky - need to condense, show all bands
        # Show all 10 bands with compact formatting
        bands_text = "\n".join(band_lines)
    else:  # Mastodon - can fit more
        bands_text = "\n".join(band_lines)

    hashtags = build_hashtags(include_hamradio)

    post = f"""📻 BAND CONDITIONS ({index}/{total})

{bands_text}

🎯 Best Now: {best_now}

Based on MUF={muf}MHz

{hashtags}"""

    return ensure_char_limit(post, char_limit)


def format_absorption_post(
    data: dict, char_limit: int, include_hamradio: bool = True, index: int = 3, total: int = 5
) -> str:
    """Format the D-Region Absorption post."""
    absorption = data.get("d_region_absorption", "N/A")

    # Get current time for context
    now = datetime.now(UTC)
    hour = now.hour

    # Time-based guidance
    if 10 <= hour <= 16:
        time_note = "Peak daytime"
    elif hour < 6 or hour > 20:
        time_note = "Low nighttime"
    else:
        time_note = "Transitional"

    # Band recommendations
    if "High" in str(absorption) or "Very High" in str(absorption):
        band_rec = "Try 80m/40m"
    elif "Moderate" in str(absorption):
        band_rec = "Mid bands OK"
    else:
        band_rec = "All bands good"

    # Condensed helper for character limits
    if char_limit == 300:  # Bluesky - super condensed
        helper = "🔴High=HF bad 🟡Med 🟢Low=HF good\nTry 40m/80m high absorption"
    else:  # Mastodon - more detail
        helper = "Real-time HF absorption from solar X-rays\n🔴Red=High (HF challenging) 🟡Yellow=Moderate 🟢Green/Blue=Low (HF good)\nHigher absorption = lower frequencies work better"

    hashtags = build_hashtags(include_hamradio)

    post = f"""📡 D-REGION ABSORPTION ({index}/{total})
{absorption}

⏰ {time_note} - {now.strftime('%H:%M')}Z
💡 {band_rec}

{helper}

{hashtags}"""

    return ensure_char_limit(post, char_limit)


def format_aurora_post(
    data: dict, char_limit: int, include_hamradio: bool = True, index: int = 4, total: int = 5
) -> str:
    """Format the Aurora Forecast post."""
    aurora_power = data.get("aurora_power", "N/A")
    k_idx = data.get("k_index", "N/A")

    # Aurora description
    if isinstance(aurora_power, (int, float)) and isinstance(k_idx, (int, float)):
        if k_idx >= 7 or aurora_power >= 100:
            aurora_desc = "🔴 STRONG"
            visibility = "Mid-lat visible"
            radio = "VHF aurora scatter!"
        elif k_idx >= 5 or aurora_power >= 50:
            aurora_desc = "🟡 MODERATE"
            visibility = "High-lat good"
            radio = "2m/6m auroral-E"
        elif k_idx >= 4 or aurora_power >= 20:
            aurora_desc = "🟢 MINOR"
            visibility = "Polar regions"
            radio = "VHF enhanced"
        else:
            aurora_desc = "⚪ QUIET"
            visibility = "Minimal"
            radio = "Normal VHF"
    else:
        aurora_desc = "N/A"
        visibility = "Data N/A"
        radio = ""

    power_str = (
        f"{aurora_power} GW" if isinstance(aurora_power, (int, float)) else aurora_power
    )

    # Condensed helper
    if char_limit == 300:  # Bluesky
        helper = "🟢2m/6m scatter 🟡Enhanced 🔴Intense\nPoint N, SSB/CW, K≥4 best"
    else:  # Mastodon
        helper = "🟢Green=2m/6m scatter possible 🟡Yellow=Enhanced 🔴Red=Intense aurora\nPoint antennas north, use SSB/CW modes. Best during K≥4 activity."

    hashtags = build_hashtags(include_hamradio)

    post = f"""🌌 AURORA FORECAST ({index}/{total})
{aurora_desc}

Power: {power_str}
K-index: {k_idx}
{visibility}

📻 {radio}

{helper}

{hashtags}"""

    return ensure_char_limit(post, char_limit)


def format_xray_post(
    data: dict, char_limit: int, include_hamradio: bool = True, index: int = 5, total: int = 5
) -> str:
    """Format the GOES X-Ray Flux post."""
    xray_class = data.get("xray_class", "N/A")

    # Impact assessment
    if xray_class == "N/A":
        impact = "Data N/A"
        advice = ""
    else:
        class_letter = xray_class[0] if xray_class else "A"

        if class_letter == "X":
            impact = "🔴 MAJOR FLARE"
            advice = "HF blackouts likely!"
        elif class_letter == "M":
            impact = "🟡 MEDIUM FLARE"
            advice = "Minor HF disruption"
        elif class_letter == "C":
            impact = "🟢 SMALL FLARE"
            advice = "Minimal impact"
        else:
            impact = "⚪ QUIET"
            advice = "Background levels"

    now = datetime.now(UTC)

    # Condensed helper
    if char_limit == 300:  # Bluesky
        helper = (
            "X=Major/HF blackout M=Med/regional C=Minor B=Weak\nRed=long λ Cyan=short λ"
        )
    else:  # Mastodon
        helper = "Flare Classes: X=Major (HF blackouts) M=Medium (regional HF degradation) C=Minor (slight absorption) B=Weak (normal)\nRed line=0.1-0.8nm Cyan=0.05-0.4nm. Spikes=flares causing radio blackouts. Higher flux=worse HF."

    hashtags = build_hashtags(include_hamradio)

    post = f"""☀️ X-RAY FLUX ({index}/{total})
Past 6hr

Current: {xray_class}
{impact}

{advice}

{helper}

NOAA SWPC {now.strftime('%H:%M')}Z

{hashtags}"""

    return ensure_char_limit(post, char_limit)


def get_post_stats(posts: list[dict], platform: str) -> dict:
    """
    Get statistics about formatted posts.

    Args:
        posts: List of post dicts
        platform: Platform name

    Returns:
        Dict with stats
    """
    limit = char_limit_for(platform)
    stats = {"platform": platform, "limit": limit, "count": len(posts), "posts": []}

    for i, post in enumerate(posts):
        text = post["text"]
        stats["posts"].append(
            {
                "number": i + 1,
                "length": len(text),
                "remaining": limit - len(text),
                "has_image": post.get("image_url") is not None,
            }
        )

    return stats
