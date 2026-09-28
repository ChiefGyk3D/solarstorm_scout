# Changelog

All notable changes to SolarStorm Scout will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-09-28

### Added
- **On-air briefing (optional).** With `LLM_ENABLE=true`, a local LLM (Ollama
  by default; Gemini if configured) opens each thread with a short "radio
  weatherperson" read of the run's numbers. The reply is cleaned, fitted to
  the post, checked against the data (a stated K-index, A-index, SFI, flare
  class or NOAA scale must match what the feeds show; negated mentions like
  "no M-class flares" are fine) and run through hypeman's guardrails, which
  reject invented events (CMEs, solar wind, sunspot numbers, clock times,
  weekdays, arrival forecasts), hype words, hashtags and links. One stricter
  retry; then the thread goes out without the briefing. Nothing about the
  briefing can fail or delay the data posts. Same `LLM_*` settings as
  Boon-Tube-Daemon and stream-daemon.
- Thread numbering follows what is in the thread: `(1/5)…(5/5)` as before,
  `(1/6)…(6/6)` when the briefing opens it.
- `python3 -m solarstorm_scout.demo` previews the briefing too when the LLM
  is enabled, so a model or prompt can be judged before it goes on the air.
- A pytest suite (formatter, forecaster, posting flow, config) run in CI;
  `requirements-dev.txt` locks pytest and ruff alongside the runtime deps.

### Changed
- **Built on hypeman-social** ([ChiefGyk3D/hypeman](https://github.com/ChiefGyk3D/hypeman)),
  the shared core behind Boon-Tube-Daemon, stream-daemon and Star-Daemon.
  Bluesky and Mastodon posting, the LLM layer, configuration and secrets
  (Doppler, and now AWS Secrets Manager and Vault) and logging come from the
  library; the bot's own copies of the Bluesky/Mastodon posters and the
  Config class are gone. Image posts use hypeman 0.3.0's `images`
  attachment, added for this bot. A fix in the library now reaches all
  four daemons.
- `BLUESKY_ENABLE_POSTING` / `MASTODON_ENABLE_POSTING` are the switch names
  hypeman reads; the original `BLUESKY_ENABLED` / `MASTODON_ENABLED` keep
  working and are translated at startup.
- Mastodon posts use the account's default visibility instead of forcing
  `public`. Accounts default to public, so nothing changes unless you set
  otherwise.
- The NOAA pictures and the X-ray chart are fetched or rendered once per
  run and reused for every network, instead of once per network.
- Logging goes through hypeman: `LOG_LEVEL` as before, timestamps left to
  journald under systemd, `LOG_FILE` / `LOG_DEDUPE_SECONDS` available.
- Doppler is read once per run rather than once per setting.
- Python 3.11+ (already required by numpy; the packaging metadata now says so).

### Removed
- `solarstorm_scout.config.Config`; use `solarstorm_scout.config` helpers or
  `hypeman_social.config` directly.

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

[1.1.0]: https://github.com/chiefgyk3d/solarstorm_scout/releases/tag/v1.1.0
[1.0.0]: https://github.com/chiefgyk3d/solarstorm-scout/releases/tag/v1.0.0
