# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""
Message Formatter for SolarStorm Scout
Formats space weather data into social media posts.
Bluesky: 300 char max per post
Mastodon: 500 char max per post
"""

import logging
from typing import List, Dict, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Image URLs from NOAA (actual image files)
DRAP_IMAGE_URL = "https://services.swpc.noaa.gov/images/animations/d-rap/global/d-rap/latest.png"
AURORA_IMAGE_URL = "https://services.swpc.noaa.gov/images/animations/ovation/north/latest.jpg"
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


def format_thread_posts(data: Dict, platform: str = 'bluesky') -> List[Dict]:
    """
    Format space weather data into a thread of posts.
    
    Creates 5 posts:
    1. Solar Indices + NOAA Scales
    2. Band Conditions + Best Bands Now  
    3. D-Region Absorption (with D-RAP image)
    4. Aurora Forecast (with aurora image)
    5. GOES Solar X-Ray Flux (with generated chart)
    
    Args:
        data: Space weather data dictionary from spaceweather.fetch_space_weather_data()
        platform: 'bluesky' (300 chars) or 'mastodon' (500 chars)
    
    Returns:
        List of dicts with 'text', 'image_url', and 'alt_text' keys
    """
    char_limit = 300 if platform == 'bluesky' else 500
    posts = []
    
    # Post 1: Solar Indices + NOAA Scales
    post1 = format_solar_indices_post(data, char_limit)
    posts.append({
        'text': post1,
        'image_url': None,
        'alt_text': ''
    })
    
    # Post 2: Band Conditions
    post2 = format_band_conditions_post(data, char_limit)
    posts.append({
        'text': post2,
        'image_url': None,
        'alt_text': ''
    })
    
    # Post 3: D-Region Absorption (with D-RAP map)
    post3 = format_absorption_post(data, char_limit)
    posts.append({
        'text': post3,
        'image_url': DRAP_IMAGE_URL,
        'alt_text': 'D-Region Absorption Prediction map showing HF radio wave absorption'
    })
    
    # Post 4: Aurora Forecast (with aurora oval)
    post4 = format_aurora_post(data, char_limit)
    posts.append({
        'text': post4,
        'image_url': AURORA_IMAGE_URL,
        'alt_text': 'Aurora oval forecast showing auroral activity in northern hemisphere'
    })
    
    # Post 5: GOES X-Ray Flux (with generated chart)
    post5 = format_xray_post(data, char_limit)
    posts.append({
        'text': post5,
        'image_url': 'GENERATE_CHART',  # Special marker to generate chart
        'alt_text': 'GOES Solar X-Ray Flux chart for past 6 hours'
    })
    
    return posts


def format_solar_indices_post(data: Dict, char_limit: int) -> str:
    """Format Post 1: Solar Indices + NOAA Scales."""
    sfi = data.get('solar_flux', 'N/A')
    a_idx = data.get('a_index', 'N/A')
    k_idx = data.get('k_index', 'N/A')
    fof2 = data.get('fof2', 'N/A')
    muf = data.get('muf_dx', 'N/A')
    absorption = data.get('absorption_factor', 0)
    r_scale = data.get('r_scale', 'N/A')
    s_scale = data.get('s_scale', 'N/A')
    g_scale = data.get('g_scale', 'N/A')
    
    # Format absorption percentage
    abs_pct = f"{int(absorption * 100)}%" if isinstance(absorption, float) else "N/A"
    
    post = f"""☀️ SOLAR INDICES (1/5)

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

#SolarStormScout #HamRadio"""
    
    return ensure_char_limit(post, char_limit)


def format_band_conditions_post(data: Dict, char_limit: int) -> str:
    """Format Post 2: Band Conditions."""
    bands = data.get('band_conditions', {})
    best_now = data.get('best_bands_now', 'N/A')
    fof2 = data.get('fof2', 'N/A')
    muf = data.get('muf_dx', 'N/A')
    
    # Format band list - group to save space
    band_lines = []
    for band_name in ['160m', '80m', '40m', '30m', '20m', '17m', '15m', '12m', '10m', '6m']:
        if band_name in bands:
            b = bands[band_name]
            band_lines.append(f"{band_name}: {b['emoji']} {b['quality']}")
    
    # Split into chunks to fit character limit
    if char_limit == 300:  # Bluesky - need to condense, show all bands
        # Show all 10 bands with compact formatting
        bands_text = "\n".join(band_lines)
    else:  # Mastodon - can fit more
        bands_text = "\n".join(band_lines)
    
    post = f"""📻 BAND CONDITIONS (2/5)

{bands_text}

🎯 Best Now: {best_now}

Based on MUF={muf}MHz

#SolarStormScout #HamRadio"""
    
    return ensure_char_limit(post, char_limit)


def format_absorption_post(data: Dict, char_limit: int) -> str:
    """Format Post 3: D-Region Absorption."""
    absorption = data.get('d_region_absorption', 'N/A')
    
    # Get current time for context
    now = datetime.utcnow()
    hour = now.hour
    
    # Time-based guidance
    if 10 <= hour <= 16:
        time_note = "Peak daytime"
    elif hour < 6 or hour > 20:
        time_note = "Low nighttime"
    else:
        time_note = "Transitional"
    
    # Band recommendations
    if 'High' in str(absorption) or 'Very High' in str(absorption):
        band_rec = "Try 80m/40m"
    elif 'Moderate' in str(absorption):
        band_rec = "Mid bands OK"
    else:
        band_rec = "All bands good"
    
    # Condensed helper for character limits
    if char_limit == 300:  # Bluesky - super condensed
        helper = "🔴High=HF bad 🟡Med 🟢Low=HF good\nTry 40m/80m high absorption"
    else:  # Mastodon - more detail
        helper = "Real-time HF absorption from solar X-rays\n🔴Red=High (HF challenging) 🟡Yellow=Moderate 🟢Green/Blue=Low (HF good)\nHigher absorption = lower frequencies work better"
    
    post = f"""📡 D-REGION ABSORPTION (3/5)
{absorption}

⏰ {time_note} - {now.strftime('%H:%M')}Z
💡 {band_rec}

{helper}

#SolarStormScout #HamRadio"""
    
    return ensure_char_limit(post, char_limit)


def format_aurora_post(data: Dict, char_limit: int) -> str:
    """Format Post 3: Aurora Forecast."""
    aurora_power = data.get('aurora_power', 'N/A')
    k_idx = data.get('k_index', 'N/A')
    
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
    
    power_str = f"{aurora_power} GW" if isinstance(aurora_power, (int, float)) else aurora_power
    
    # Condensed helper
    if char_limit == 300:  # Bluesky
        helper = "🟢2m/6m scatter 🟡Enhanced 🔴Intense\nPoint N, SSB/CW, K≥4 best"
    else:  # Mastodon
        helper = "🟢Green=2m/6m scatter possible 🟡Yellow=Enhanced 🔴Red=Intense aurora\nPoint antennas north, use SSB/CW modes. Best during K≥4 activity."
    
    post = f"""🌌 AURORA FORECAST (4/5)
{aurora_desc}

Power: {power_str}
K-index: {k_idx}
{visibility}

📻 {radio}

{helper}

#SolarStormScout #HamRadio"""
    
    return ensure_char_limit(post, char_limit)


def format_xray_post(data: Dict, char_limit: int) -> str:
    """Format Post 4: GOES X-Ray Flux."""
    xray_class = data.get('xray_class', 'N/A')
    
    # Impact assessment
    if xray_class == 'N/A':
        impact = "Data N/A"
        advice = ""
    else:
        class_letter = xray_class[0] if xray_class else 'A'
        
        if class_letter == 'X':
            impact = "🔴 MAJOR FLARE"
            advice = "HF blackouts likely!"
        elif class_letter == 'M':
            impact = "🟡 MEDIUM FLARE"
            advice = "Minor HF disruption"
        elif class_letter == 'C':
            impact = "🟢 SMALL FLARE"
            advice = "Minimal impact"
        else:
            impact = "⚪ QUIET"
            advice = "Background levels"
    
    now = datetime.utcnow()
    
    # Condensed helper
    if char_limit == 300:  # Bluesky
        helper = "X=Major/HF blackout M=Med/regional C=Minor B=Weak\nRed=long λ Cyan=short λ"
    else:  # Mastodon
        helper = "Flare Classes: X=Major (HF blackouts) M=Medium (regional HF degradation) C=Minor (slight absorption) B=Weak (normal)\nRed line=0.1-0.8nm Cyan=0.05-0.4nm. Spikes=flares causing radio blackouts. Higher flux=worse HF."
    
    post = f"""☀️ X-RAY FLUX (5/5)
Past 6hr

Current: {xray_class}
{impact}

{advice}

{helper}

NOAA SWPC {now.strftime('%H:%M')}Z

#SolarStormScout #HamRadio"""
    
    return ensure_char_limit(post, char_limit)


def get_post_stats(posts: List[Dict], platform: str) -> Dict:
    """
    Get statistics about formatted posts.
    
    Args:
        posts: List of post dicts
        platform: Platform name
    
    Returns:
        Dict with stats
    """
    limit = 300 if platform == 'bluesky' else 500
    stats = {
        'platform': platform,
        'limit': limit,
        'count': len(posts),
        'posts': []
    }
    
    for i, post in enumerate(posts):
        text = post['text']
        stats['posts'].append({
            'number': i + 1,
            'length': len(text),
            'remaining': limit - len(text),
            'has_image': post.get('image_url') is not None
        })
    
    return stats
