# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""
Chart Renderer for SolarStorm Scout
Generates matplotlib charts from NOAA JSON data.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime, timezone

import aiohttp
import matplotlib

matplotlib.use('Agg')  # Non-interactive backend for server use
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


async def plot_xray_flux(period: str = '6h') -> io.BytesIO | None:
    """
    Fetch GOES X-ray flux data from NOAA and generate a chart.
    
    Args:
        period: Time period ('6h', '1d', '3d', '7d')
    
    Returns:
        BytesIO object containing PNG image, or None on error
    """
    period_map = {
        '6h': '6-hour',
        '1d': '1-day',
        '3d': '3-day',
        '7d': '7-day'
    }
    
    period_file = period_map.get(period.lower(), '6-hour')
    json_url = f"https://services.swpc.noaa.gov/json/goes/primary/xrays-{period_file}.json"
    
    try:
        async with aiohttp.ClientSession() as session, session.get(json_url, timeout=30) as resp:
            if resp.status != 200:
                logger.error(f"Failed to fetch GOES data: {resp.status}")
                return None
            
            data = await resp.json()
        
        if not data:
            logger.error("No GOES X-ray data received")
            return None
        
        # Parse data - data has two entries per timestamp (one for each wavelength)
        data_dict = {}  # {timestamp: {'short': flux, 'long': flux}}
        
        for entry in data:
            try:
                time_tag = entry.get('time_tag', '')
                dt = datetime.fromisoformat(time_tag.replace('Z', '+00:00'))
                flux = float(entry.get('flux', 0))
                energy = entry.get('energy', '')  # String like "0.05-0.4nm" or "0.1-0.8nm"
                
                if flux <= 0:
                    continue
                
                # Initialize timestamp entry if not exists
                if dt not in data_dict:
                    data_dict[dt] = {'short': None, 'long': None}
                
                # Categorize by wavelength
                if '0.05-0.4' in energy:
                    data_dict[dt]['short'] = flux
                elif '0.1-0.8' in energy:
                    data_dict[dt]['long'] = flux
                    
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping invalid entry: {e}")
                continue
        
        # Convert to sorted lists
        timestamps = sorted(data_dict.keys())
        flux_short = [data_dict[ts]['short'] for ts in timestamps]
        flux_long = [data_dict[ts]['long'] for ts in timestamps]
        
        if not timestamps:
            logger.error("No valid GOES data points")
            return None
        
        # Create dark-themed plot
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(10, 6), facecolor='#1a1a1a')
        ax.set_facecolor('#0d0d0d')
        
        # Plot data
        ax.plot(timestamps, flux_long, color='#FF6B6B', linewidth=2, label='0.1-0.8 nm', alpha=0.9)
        ax.plot(timestamps, flux_short, color='#4ECDC4', linewidth=2, label='0.05-0.4 nm', alpha=0.9)
        
        # Set logarithmic scale
        ax.set_yscale('log')
        ax.set_ylim(1e-9, 1e-2)
        
        # Add flare classification lines
        ax.axhline(y=1e-3, color='#FF3838', linestyle='--', linewidth=1, alpha=0.5)
        ax.text(timestamps[len(timestamps)//20], 1e-3, 'X', color='#FF3838', fontsize=10, va='bottom')
        
        ax.axhline(y=1e-4, color='#FF8C42', linestyle='--', linewidth=1, alpha=0.5)
        ax.text(timestamps[len(timestamps)//20], 1e-4, 'M', color='#FF8C42', fontsize=10, va='bottom')
        
        ax.axhline(y=1e-5, color='#FFD93D', linestyle='--', linewidth=1, alpha=0.5)
        ax.text(timestamps[len(timestamps)//20], 1e-5, 'C', color='#FFD93D', fontsize=10, va='bottom')
        
        ax.axhline(y=1e-6, color='#6BCF7F', linestyle='--', linewidth=1, alpha=0.5)
        ax.text(timestamps[len(timestamps)//20], 1e-6, 'B', color='#6BCF7F', fontsize=10, va='bottom')
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M', tz=timezone.utc))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.xticks(rotation=45, ha='right')
        
        # Labels and title
        ax.set_xlabel('Time (UTC)', fontsize=11, color='#FFFFFF')
        ax.set_ylabel('Watts/m²', fontsize=11, color='#FFFFFF')
        ax.set_title(f'GOES Solar X-Ray Flux ({period_file})', fontsize=13, color='#FFFFFF', pad=15)
        
        # Legend
        ax.legend(loc='upper left', framealpha=0.8, facecolor='#0d0d0d', edgecolor='#555555')
        
        # Grid
        ax.grid(True, alpha=0.2, linestyle=':', color='#555555')
        
        # Tight layout
        plt.tight_layout()
        
        # Save to BytesIO
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120, facecolor='#1a1a1a', edgecolor='none')
        buf.seek(0)
        plt.close(fig)
        
        logger.info(f"Successfully generated GOES X-ray flux chart ({period_file})")
        return buf
        
    except Exception:
        logger.exception("Error generating X-ray flux chart")
        return None
