# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""
Configuration and Secrets Management for SolarStorm Scout
Supports .env files and Doppler secrets manager.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    logger.warning("python-dotenv not available, .env file support disabled")

try:
    from dopplersdk import DopplerSDK
    DOPPLER_AVAILABLE = True
except ImportError:
    DOPPLER_AVAILABLE = False
    logger.debug("dopplersdk not available, Doppler support disabled")


class Config:
    """Configuration manager supporting .env and Doppler."""
    
    def __init__(self, env_file: str | None = None):
        """
        Initialize configuration.
        
        Args:
            env_file: Path to .env file (optional)
        """
        self.doppler_client = None
        self.doppler_enabled = False
        
        # Load .env file if available
        if env_file and DOTENV_AVAILABLE:
            env_path = Path(env_file)
            if env_path.exists():
                load_dotenv(env_path)
                logger.info(f"Loaded .env file from {env_file}")
            else:
                logger.warning(f".env file not found: {env_file}")
        elif DOTENV_AVAILABLE:
            # Try default .env in current directory
            if Path('.env').exists():
                load_dotenv()
                logger.info("Loaded .env file from current directory")
        
        # Initialize Doppler if configured
        doppler_token = os.getenv('DOPPLER_TOKEN')
        if doppler_token and DOPPLER_AVAILABLE:
            try:
                self.doppler_client = DopplerSDK()
                self.doppler_client.set_access_token(doppler_token)
                self.doppler_enabled = True
                logger.info("✓ Doppler secrets manager initialized")
            except Exception as e:  # noqa: BLE001  # fall back to .env; error is logged
                logger.error(f"Failed to initialize Doppler: {e}")
    
    def get(self, key: str, default: str | None = None) -> str | None:
        """
        Get configuration value.
        Priority: Doppler > Environment Variable (.env) > Default
        
        .env provides base configuration, Doppler overrides if values exist
        
        Args:
            key: Configuration key
            default: Default value if not found
        
        Returns:
            Configuration value or default
        """
        # Start with .env value as base
        value = os.getenv(key)
        
        # Try Doppler override if enabled
        if self.doppler_enabled and self.doppler_client:
            try:
                # Doppler SDK fetches all secrets at once
                # Use secrets.list() to get all secrets
                project = os.getenv('DOPPLER_PROJECT')
                config = os.getenv('DOPPLER_CONFIG')
                
                if not project or not config:
                    if not hasattr(self, '_doppler_config_warning'):
                        logger.warning("DOPPLER_PROJECT and DOPPLER_CONFIG must be set in .env to use Doppler")
                        self._doppler_config_warning = True
                    return value if value is not None else default
                
                secrets = self.doppler_client.secrets.list(project=project, config=config)
                # Check if this key exists in Doppler
                if secrets and hasattr(secrets, 'secrets') and key in secrets.secrets:
                    doppler_value = secrets.secrets[key].get('computed')
                    if doppler_value:  # Only override if Doppler has a value
                        logger.debug(f"Using Doppler value for {key}")
                        return doppler_value
            except Exception as e:  # noqa: BLE001  # fall back to .env; first failure is logged
                # Log first failure to help with debugging
                if not hasattr(self, '_doppler_error_logged'):
                    logger.warning(f"Doppler fetch failed: {e}")
                    self._doppler_error_logged = True
        
        # Return .env value or default
        return value if value is not None else default
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """
        Get boolean configuration value.
        
        Args:
            key: Configuration key
            default: Default value if not found
        
        Returns:
            Boolean value
        """
        value = self.get(key)
        if value is None:
            return default
        
        # Handle common boolean representations
        return value.lower() in ('true', '1', 'yes', 'on', 'enabled')
    
    def get_int(self, key: str, default: int = 0) -> int:
        """
        Get integer configuration value.
        
        Args:
            key: Configuration key
            default: Default value if not found
        
        Returns:
            Integer value
        """
        value = self.get(key)
        if value is None:
            return default
        
        try:
            return int(value)
        except ValueError:
            logger.warning(f"Invalid integer value for {key} ({len(value)} characters), using default {default}")
            return default
    
    def get_float(self, key: str, default: float = 0.0) -> float:
        """
        Get float configuration value.
        
        Args:
            key: Configuration key
            default: Default value if not found
        
        Returns:
            Float value
        """
        value = self.get(key)
        if value is None:
            return default
        
        try:
            return float(value)
        except ValueError:
            logger.warning(f"Invalid float value for {key} ({len(value)} characters), using default {default}")
            return default
    
    def require(self, key: str) -> str:
        """
        Get required configuration value, raise error if not found.
        
        Args:
            key: Configuration key
        
        Returns:
            Configuration value
        
        Raises:
            ValueError: If key not found
        """
        value = self.get(key)
        if value is None:
            raise ValueError(f"Required configuration key not found: {key}")
        return value
    
    def get_posting_interval(self) -> float:
        """
        Get posting interval in hours.
        Default: 1.5 hours
        
        Returns:
            Posting interval in hours
        """
        return self.get_float('POSTING_INTERVAL_HOURS', 1.5)
    
    def is_bluesky_enabled(self) -> bool:
        """Check if Bluesky posting is enabled."""
        return self.get_bool('BLUESKY_ENABLED', False)
    
    def is_mastodon_enabled(self) -> bool:
        """Check if Mastodon posting is enabled."""
        return self.get_bool('MASTODON_ENABLED', False)
    
    def get_bluesky_config(self) -> tuple:
        """
        Get Bluesky configuration.
        
        Returns:
            Tuple of (handle, app_password)
        
        Raises:
            ValueError: If required config missing
        """
        handle = self.get('BLUESKY_HANDLE')
        password = self.get('BLUESKY_APP_PASSWORD')
        
        if not handle or not password:
            raise ValueError("Bluesky configuration incomplete: need BLUESKY_HANDLE and BLUESKY_APP_PASSWORD")
        
        return handle, password
    
    def get_mastodon_config(self) -> tuple:
        """
        Get Mastodon configuration.
        
        Returns:
            Tuple of (api_base_url, access_token, client_id, client_secret)
            client_id and client_secret may be None
        
        Raises:
            ValueError: If required config missing
        """
        api_base_url = self.get('MASTODON_API_BASE_URL')
        access_token = self.get('MASTODON_ACCESS_TOKEN')
        client_id = self.get('MASTODON_CLIENT_ID')
        client_secret = self.get('MASTODON_CLIENT_SECRET')
        
        if not api_base_url or not access_token:
            raise ValueError("Mastodon configuration incomplete: need MASTODON_API_BASE_URL and MASTODON_ACCESS_TOKEN")
        
        return api_base_url, access_token, client_id, client_secret
    
    def validate_config(self) -> bool:
        """
        Validate that at least one platform is configured.
        
        Returns:
            True if configuration is valid
        """
        has_platform = False
        
        if self.is_bluesky_enabled():
            try:
                self.get_bluesky_config()
                has_platform = True
                logger.info("✓ Bluesky configuration valid")
            except ValueError as e:
                logger.error(f"✗ Bluesky configuration invalid: {e}")
        
        if self.is_mastodon_enabled():
            try:
                self.get_mastodon_config()
                has_platform = True
                logger.info("✓ Mastodon configuration valid")
            except ValueError as e:
                logger.error(f"✗ Mastodon configuration invalid: {e}")
        
        if not has_platform:
            logger.error("✗ No social media platforms configured!")
            return False
        
        return True


def setup_logging(log_level: str = 'INFO'):
    """
    Setup logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
