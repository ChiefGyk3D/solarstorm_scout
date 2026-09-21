# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""
Space Weather Data Fetcher for SolarStorm Scout
Fetches real-time data from NOAA Space Weather Prediction Center.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

import aiohttp

logger = logging.getLogger(__name__)


# NOAA Space Weather API endpoints
NOAA_SOLAR_FLUX_URL = "https://services.swpc.noaa.gov/json/f107_cm_flux.json"  # CORRECT endpoint
NOAA_K_INDEX_URL = "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json"
NOAA_SCALES_URL = "https://services.swpc.noaa.gov/products/noaa-scales.json"
NOAA_XRAY_JSON_URL = "https://services.swpc.noaa.gov/json/goes/primary/xray-flares-latest.json"
NOAA_XRAY_6H_URL = "https://services.swpc.noaa.gov/json/goes/primary/xrays-6-hour.json"
NOAA_AURORA_FORECAST_URL = "https://services.swpc.noaa.gov/text/aurora-nowcast-hemi-power.txt"


def estimate_fof2_from_sfi(sfi_value: float) -> float:
    """
    Estimate critical frequency (foF2) from Solar Flux Index.
    
    Based on empirical relationship: foF2 ≈ sqrt(SFI/150) * base_frequency
    During solar minimum (SFI~70): foF2 ≈ 4-5 MHz
    During solar maximum (SFI~200+): foF2 ≈ 10-12 MHz
    
    Args:
        sfi_value: Solar Flux Index (70-300 typical range)
    
    Returns:
        Estimated foF2 in MHz
    """
    base_fof2 = 7.0
    scale = math.sqrt(max(sfi_value, 50) / 100.0)
    return base_fof2 * scale


def calculate_d_layer_absorption(utc_hour: int, solar_flux: float, k_index: float) -> tuple[float, str]:
    """
    Calculate D-layer absorption prediction.
    
    D-layer absorption is maximum at solar noon and minimal at night.
    Solar flares and high SFI increase absorption.
    
    Args:
        utc_hour: Current UTC hour (0-23)
        solar_flux: Solar Flux Index
        k_index: Planetary K-index
    
    Returns:
        Tuple of (absorption_factor, description)
        absorption_factor: 0.0 = no absorption, 1.0 = complete absorption
    """
    # Calculate solar zenith angle approximation
    hour_angle = abs(utc_hour - 12)
    
    if hour_angle > 6:
        # Night time - minimal D-layer absorption
        base_absorption = 0.05
        time_desc = "Night"
    else:
        # Day time - absorption increases toward solar noon
        base_absorption = 0.3 + (0.4 * (1.0 - hour_angle / 6.0))
        time_desc = "Day"
    
    # Adjust for solar activity
    sfi_factor = min(solar_flux / 150.0, 2.0)
    base_absorption *= sfi_factor
    
    # K-index impact (geomagnetic storms increase absorption)
    if k_index >= 5:
        base_absorption += 0.2
    
    absorption = min(base_absorption, 1.0)
    
    # Generate description
    if absorption < 0.2:
        desc = f"Low ({time_desc})"
        emoji = "🟢"
    elif absorption < 0.4:
        desc = f"Moderate ({time_desc})"
        emoji = "🟡"
    elif absorption < 0.6:
        desc = f"High ({time_desc})"
        emoji = "🟠"
    else:
        desc = f"Very High ({time_desc})"
        emoji = "🔴"
    
    return absorption, f"{emoji} {desc}"


def calculate_band_conditions(fof2: float, muf: float, absorption: float, k_index: float, utc_hour: int) -> dict:
    """
    Calculate band-by-band HF propagation conditions.
    
    Returns dict with band names as keys and status dicts as values.
    Each status dict contains: emoji, quality, description
    """
    bands = {
        '160m': {'freq': 1.9, 'desc': 'Regional/DX at night'},
        '80m': {'freq': 3.6, 'desc': 'Reliable day/night'},
        '40m': {'freq': 7.1, 'desc': 'Most reliable'},
        '30m': {'freq': 10.1, 'desc': 'CW/digital DX'},
        '20m': {'freq': 14.2, 'desc': 'Premier DX'},
        '17m': {'freq': 18.1, 'desc': 'Underused gem'},
        '15m': {'freq': 21.2, 'desc': 'Solar-dependent'},
        '12m': {'freq': 24.9, 'desc': 'Solar-dependent'},
        '10m': {'freq': 28.5, 'desc': 'Magic band'},
        '6m': {'freq': 50.1, 'desc': 'VHF magic'},
    }
    
    conditions = {}
    is_night = (utc_hour < 6 or utc_hour > 18)
    
    for band, info in bands.items():
        freq = info['freq']
        
        # Check if band is above MUF (closed)
        if freq > muf:
            conditions[band] = {'emoji': '🔴', 'quality': 'Closed', 'desc': info['desc']}
            continue
        
        # Check if band is too close to foF2 (marginal)
        if freq > fof2 * 2.5:
            conditions[band] = {'emoji': '🟡', 'quality': 'Fair', 'desc': info['desc']}
            continue
        
        # Low bands better at night
        if band in ['160m', '80m']:
            if is_night:
                conditions[band] = {'emoji': '🟢', 'quality': 'Good', 'desc': info['desc']}
            else:
                conditions[band] = {'emoji': '🟡', 'quality': 'Fair', 'desc': info['desc']}
            continue
        
        # High bands need good solar flux
        if band in ['15m', '12m', '10m', '6m']:
            if fof2 > 7.0 and k_index < 4:
                conditions[band] = {'emoji': '🟢', 'quality': 'Good', 'desc': info['desc']}
            elif fof2 > 5.0:
                conditions[band] = {'emoji': '🟡', 'quality': 'Fair', 'desc': info['desc']}
            else:
                conditions[band] = {'emoji': '🔴', 'quality': 'Poor', 'desc': info['desc']}
            continue
        
        # Mid bands (40m, 30m, 20m, 17m) - generally reliable
        if k_index < 4 and absorption < 0.5:
            conditions[band] = {'emoji': '🟢', 'quality': 'Good', 'desc': info['desc']}
        else:
            conditions[band] = {'emoji': '🟡', 'quality': 'Fair', 'desc': info['desc']}
    
    return conditions


def get_best_bands_now(utc_hour: int, fof2: float) -> str:
    """
    Get recommended bands for current time.
    
    Returns string with recommended bands.
    """
    is_day = (6 <= utc_hour <= 18)
    
    if is_day:
        if fof2 > 8.0:
            return "20m, 17m, 15m, 12m"
        elif fof2 > 6.0:
            return "40m, 30m, 20m, 17m"
        else:
            return "40m, 30m, 20m"
    else:
        # Night
        if fof2 > 7.0:
            return "80m, 40m, 30m, 20m"
        else:
            return "80m, 40m, 30m"


async def fetch_space_weather_data(session: aiohttp.ClientSession | None = None) -> dict:
    """
    Fetch comprehensive space weather data from NOAA.
    
    Returns:
        Dictionary containing:
        - solar_flux: Current Solar Flux Index (SFI)
        - k_index: Current planetary K-index
        - aurora_power: Aurora power index
        - xray_class: Current X-ray flux class (A, B, C, M, X)
        - d_region_absorption: D-layer absorption prediction
        - propagation_conditions: Overall HF propagation assessment
        - timestamp: Data fetch timestamp
    """
    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True
    
    try:
        data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'solar_flux': 'N/A',
            'k_index': 'N/A',
            'aurora_power': 'N/A',
            'xray_class': 'N/A',
            'xray_flux': 'N/A',
            'd_region_absorption': 'N/A',
            'propagation_conditions': 'N/A',
            'fof2': 'N/A',
        }
        
        # Fetch Solar Flux Index (F10.7cm)
        try:
            async with session.get(NOAA_SOLAR_FLUX_URL, timeout=10) as resp:
                if resp.status == 200:
                    flux_data = await resp.json()
                    if flux_data:
                        # Look for most recent Noon report first (most reliable)
                        for entry in reversed(flux_data):
                            if entry.get('reporting_schedule') == 'Noon':
                                data['solar_flux'] = int(entry.get('flux', 0))
                                break
                        # Fallback to latest entry if no Noon report
                        if data['solar_flux'] == 'N/A' and flux_data:
                            data['solar_flux'] = int(flux_data[-1].get('flux', 0))
                        logger.info(f"Fetched Solar Flux: {data['solar_flux']}")
        except Exception as e:  # noqa: BLE001  # one NOAA feed failing must not lose the others; error is logged
            logger.error(f"Error fetching solar flux: {e}")
        
        # Fetch K-index
        try:
            async with session.get(NOAA_K_INDEX_URL, timeout=10) as resp:
                if resp.status == 200:
                    k_data = await resp.json()
                    if k_data:
                        data['k_index'] = int(k_data[-1].get('kp_index', 0))
                        logger.info(f"Fetched K-index: {data['k_index']}")
        except Exception as e:  # noqa: BLE001  # one NOAA feed failing must not lose the others; error is logged
            logger.error(f"Error fetching K-index: {e}")
        
        # Calculate A-index from K-index
        if isinstance(data['k_index'], int):
            data['a_index'] = int((data['k_index'] ** 2) * 3.3)
        else:
            data['a_index'] = 'N/A'
        
        # Fetch NOAA Scales (R/S/G)
        try:
            async with session.get(NOAA_SCALES_URL, timeout=10) as resp:
                if resp.status == 200:
                    scales_data = await resp.json()
                    if isinstance(scales_data, dict) and '0' in scales_data:
                        current = scales_data['0']
                        data['r_scale'] = current.get('R', {}).get('Scale', 'N/A')
                        data['s_scale'] = current.get('S', {}).get('Scale', 'N/A')
                        data['g_scale'] = current.get('G', {}).get('Scale', 'N/A')
                        logger.info(f"Fetched NOAA Scales - R:{data['r_scale']} S:{data['s_scale']} G:{data['g_scale']}")
        except Exception as e:  # noqa: BLE001  # one NOAA feed failing must not lose the others; error is logged
            logger.error(f"Error fetching NOAA scales: {e}")
            data['r_scale'] = 'N/A'
            data['s_scale'] = 'N/A'
            data['g_scale'] = 'N/A'
        
        # Fetch X-ray data
        try:
            async with session.get(NOAA_XRAY_6H_URL, timeout=10) as resp:
                if resp.status == 200:
                    xray_data = await resp.json()
                    if xray_data:
                        latest = xray_data[-1]
                        flux = latest.get('flux')
                        if flux and flux > 0:
                            data['xray_flux'] = flux
                            # Classify X-ray flux
                            if flux >= 1e-4:
                                data['xray_class'] = f"X{flux/1e-4:.1f}"
                            elif flux >= 1e-5:
                                data['xray_class'] = f"M{flux/1e-5:.1f}"
                            elif flux >= 1e-6:
                                data['xray_class'] = f"C{flux/1e-6:.1f}"
                            elif flux >= 1e-7:
                                data['xray_class'] = f"B{flux/1e-7:.1f}"
                            else:
                                data['xray_class'] = f"A{flux/1e-8:.1f}"
                        logger.info(f"Fetched X-ray class: {data['xray_class']}")
        except Exception as e:  # noqa: BLE001  # one NOAA feed failing must not lose the others; error is logged
            logger.error(f"Error fetching X-ray data: {e}")
        
        # Fetch Aurora forecast (parse text format)
        try:
            async with session.get(NOAA_AURORA_FORECAST_URL, timeout=10) as resp:
                if resp.status == 200:
                    aurora_text = await resp.text()
                    # Parse aurora power from text (last value in file)
                    lines = aurora_text.strip().split('\n')
                    for line in reversed(lines):
                        line = line.strip()
                        if line and not line.startswith('#'):
                            parts = line.split()
                            if len(parts) >= 3:
                                try:
                                    data['aurora_power'] = float(parts[2])
                                    logger.info(f"Fetched Aurora power: {data['aurora_power']}")
                                    break
                                except (ValueError, IndexError):
                                    continue
        except Exception as e:  # noqa: BLE001  # one NOAA feed failing must not lose the others; error is logged
            logger.error(f"Error fetching aurora data: {e}")
        
        # Calculate derived values if we have the data
        if isinstance(data['solar_flux'], (int, float)):
            data['fof2'] = round(estimate_fof2_from_sfi(data['solar_flux']), 1)
            
            # Calculate D-region absorption
            utc_hour = datetime.now(timezone.utc).hour
            k_val = data['k_index'] if isinstance(data['k_index'], (int, float)) else 2.0
            absorption, abs_desc = calculate_d_layer_absorption(utc_hour, data['solar_flux'], k_val)
            data['d_region_absorption'] = abs_desc
            data['absorption_factor'] = absorption
            
            # Calculate MUF for DX (assume 3000km path)
            muf_dx = data['fof2'] * 4.0  # Simplified MUF calculation for long distance
            data['muf_dx'] = round(muf_dx, 1)
            
            # Overall propagation assessment
            sfi = data['solar_flux']
            k_idx = k_val
            
            if sfi > 150 and k_idx < 3:
                data['propagation_conditions'] = "🟢 Excellent"
            elif sfi > 120 and k_idx < 4:
                data['propagation_conditions'] = "🟢 Good"
            elif sfi > 90 and k_idx < 5:
                data['propagation_conditions'] = "🟡 Fair"
            elif sfi > 70:
                data['propagation_conditions'] = "🟠 Poor"
            else:
                data['propagation_conditions'] = "🔴 Very Poor"
            
            # Band conditions
            utc_hour = datetime.now(timezone.utc).hour
            data['band_conditions'] = calculate_band_conditions(
                data['fof2'], muf_dx, absorption, k_val, utc_hour
            )
            
            # Recommended bands for current time
            data['best_bands_now'] = get_best_bands_now(utc_hour, data['fof2'])
        
        return data
        
    finally:
        if close_session:
            await session.close()


async def get_aurora_description(aurora_power: float, k_index: float) -> str:
    """
    Generate aurora forecast description.
    
    Args:
        aurora_power: Aurora power index (GW)
        k_index: Planetary K-index
    
    Returns:
        Description string with emoji
    """
    if k_index >= 7 or aurora_power >= 100:
        return "🔴 Strong - Visible at lower latitudes"
    elif k_index >= 5 or aurora_power >= 50:
        return "🟡 Moderate - Good aurora at high latitudes"
    elif k_index >= 4 or aurora_power >= 20:
        return "🟢 Minor - Possible aurora near poles"
    else:
        return "⚪ Quiet - No significant aurora"


def get_xray_impact_description(xray_class: str) -> str:
    """
    Get impact description for X-ray flux level.
    
    Args:
        xray_class: X-ray class (e.g., "C2.1", "M5.0", "X1.0")
    
    Returns:
        Impact description
    """
    if xray_class == 'N/A':
        return "N/A"
    
    class_letter = xray_class[0] if xray_class else 'A'
    
    if class_letter == 'X':
        return "🔴 Major flare - Radio blackouts likely"
    elif class_letter == 'M':
        return "🟡 Medium flare - Minor radio disruption"
    elif class_letter == 'C':
        return "🟢 Small flare - Minimal impact"
    else:
        return "⚪ Quiet - Background levels"
