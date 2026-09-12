# Changelog

All notable changes to SolarStorm Scout will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- Bumped `aiohttp` 3.13.3 → 3.14.3. The pin sat below 3.13.4, which carried a
  security fix Dependabot had been flagging since April.

### Changed
- Bumped `atproto` 0.0.65 → 0.0.72, `Mastodon.py` 2.1.4 → 2.2.2,
  `python-dotenv` 1.2.1 → 1.2.3, `matplotlib` 3.10.7 → 3.11.2 and
  `numpy` 2.3.4 → 2.4.6.

### Fixed
- CI's lint job ran `ruff check penguin-overlord/` and
  `bandit -r penguin-overlord/` — a directory that does not exist in this
  repository, copy-pasted from the sibling project. Both steps are wrapped in
  `continue-on-error`, so the job reported success while linting and
  security-scanning nothing at all. Now pointed at `solarstorm_scout/`.

## [1.0.0] - 2024-11-14

### Added
- Initial release of SolarStorm Scout
- Real-time space weather data fetching from NOAA SWPC APIs
- Support for Bluesky and Mastodon posting with threading
- 4-part threaded updates (Propagation, D-Region, Aurora, X-Ray)
- 300 character limit per post for optimal readability
- Configuration via .env files
- Optional Doppler secrets manager support
- systemd service and timer installation
- Docker deployment with Ofelia scheduler
- Comprehensive README and Quick Start guide
- Automated installation script for systemd
- Configurable posting interval (default: 1.5 hours)
- Logging with configurable levels
- HF propagation conditions with Solar Flux and K-index
- D-Region absorption predictions with time-based context
- Aurora forecast with visibility and VHF notes
- GOES X-Ray flux monitoring with flare classifications

### Features
- Dual platform posting (Bluesky + Mastodon)
- Thread support with reply chains
- Physics-based propagation calculations
- Professional formatting with emojis and hashtags
- Multiple deployment options
- Unattended operation via timers
- Error handling and retry logic
- Clean logging output

### Technical
- Python 3.8+ support
- Async/await architecture using aiohttp
- Modular design with separate concerns
- Type hints throughout codebase
- MPL-2.0 licensed

## [Unreleased]

### Planned
- Web dashboard for viewing posted updates
- Historical data tracking and graphs
- Custom message templates
- Additional platform support (Twitter/X, Discord)
- RSS feed generation
- Email digest option
- Webhook notifications
- Band-specific condition alerts
- Solar cycle tracking
- Contest calendar integration

---

[1.0.0]: https://github.com/chiefgyk3d/solarstorm-scout/releases/tag/v1.0.0
