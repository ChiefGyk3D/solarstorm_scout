"""Shared fixtures: a realistic data dict and a clean environment."""

import pytest


@pytest.fixture
def data():
    """What spaceweather.fetch_space_weather_data() returns on a quiet day."""
    return {
        'timestamp': '2026-09-28T18:00:00+00:00',
        'solar_flux': 145,
        'k_index': 2,
        'a_index': 13,
        'aurora_power': 12.0,
        'xray_class': 'B4.2',
        'xray_flux': 4.2e-7,
        'r_scale': '0',
        's_scale': '0',
        'g_scale': '0',
        'fof2': 8.4,
        'muf_dx': 33.7,
        'd_region_absorption': '🟡 Moderate (Day)',
        'absorption_factor': 0.31,
        'propagation_conditions': '🟢 Good',
        'band_conditions': {
            '160m': {'emoji': '🟡', 'quality': 'Fair', 'desc': ''},
            '80m': {'emoji': '🟡', 'quality': 'Fair', 'desc': ''},
            '40m': {'emoji': '🟢', 'quality': 'Good', 'desc': ''},
            '30m': {'emoji': '🟢', 'quality': 'Good', 'desc': ''},
            '20m': {'emoji': '🟢', 'quality': 'Good', 'desc': ''},
            '17m': {'emoji': '🟢', 'quality': 'Good', 'desc': ''},
            '15m': {'emoji': '🟢', 'quality': 'Good', 'desc': ''},
            '12m': {'emoji': '🟢', 'quality': 'Good', 'desc': ''},
            '10m': {'emoji': '🟢', 'quality': 'Good', 'desc': ''},
            '6m': {'emoji': '🔴', 'quality': 'Closed', 'desc': ''},
        },
        'best_bands_now': '20m, 17m, 15m, 12m',
    }


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """No Doppler, no LLM, no platform switched on unless a test says so."""
    for key in (
        'DOPPLER_TOKEN', 'LLM_ENABLE', 'LLM_PROVIDER',
        'BLUESKY_ENABLED', 'BLUESKY_ENABLE_POSTING',
        'MASTODON_ENABLED', 'MASTODON_ENABLE_POSTING',
    ):
        monkeypatch.delenv(key, raising=False)
