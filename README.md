# 🌞 SolarStorm Scout

<div align="center">
  <img src="media/banner.png" alt="SolarStorm Scout Banner" width="400">
</div>

**Space Weather Social Media Bot** - Automated HF propagation updates for Bluesky and Mastodon

**🔴 Live Now:** Follow [@solarstormscout.bsky.social](https://bsky.app/profile/solarstormscout.bsky.social) on Bluesky | [@solarstormscout@social.chiefgyk3d.com](https://social.chiefgyk3d.com/@solarstormscout) on Mastodon

SolarStorm Scout fetches real-time space weather data from NOAA and posts threaded updates about:
- HF Propagation Conditions
- D-Region Absorption Predictions
- Aurora Forecasts
- GOES Solar X-Ray Flux
- Optionally, an AI "radio weatherperson" briefing that reads the numbers out in plain language (local Ollama server by default)

Perfect for amateur radio operators, space weather enthusiasts, and anyone interested in HF propagation!

> **⚠️ Note**: Space weather conditions can change rapidly. Data represents conditions at post time. For real-time updates, visit [NOAA Space Weather Prediction Center](https://www.swpc.noaa.gov/).

## 🔕 Content Filtering

All posts include the **#SolarStormScout** hashtag. Since Bluesky and Mastodon don't currently provide options to control what appears in general/live feeds, users can filter out these automated posts by muting or blocking the hashtag:

- **Bluesky**: Settings → Moderation → Muted words → Add "#SolarStormScout"
- **Mastodon**: Preferences → Filters → Add filter for "#SolarStormScout"

This allows users who prefer not to see automated space weather updates to opt out while still allowing those interested to follow the account directly.

## 🎯 Features

- ✅ **Dual Platform Support**: Post to Bluesky and/or Mastodon
- ✅ **Thread Support**: Posts 5-part threads with detailed information
- ✅ **On-Air Briefing (optional)**: A local LLM opens the thread as a radio weatherperson; if anything about it is off, the thread goes out without it
- ✅ **300 Character Limit**: Each post optimized for readability
- ✅ **Configurable Interval**: Default 1.5 hours, fully customizable
- ✅ **Multiple Deployment Options**: systemd timer, Docker, or manual
- ✅ **Secrets Management**: Support for .env files, Doppler, AWS Secrets Manager and Vault
- ✅ **Real-time NOAA Data**: Direct from Space Weather Prediction Center
- ✅ **Professional Formatting**: Clean, informative posts with hashtags
- ✅ **Shared Core**: Built on [hypeman-social](https://github.com/ChiefGyk3D/hypeman), the same posting, LLM and config layer as Boon-Tube-Daemon, stream-daemon and Star-Daemon

## 📋 Thread Format

Each update consists of 5 posts (6 when the on-air briefing is enabled and passes its checks; the numbering adjusts):

### Opening Post (optional): On-Air Briefing

When `LLM_ENABLE=true`, the thread opens with the forecaster's read of this run's numbers, in the voice of a radio weatherperson:

> 🎙️ SPACE WX BRIEFING (1/6)
>
> Good evening, operators! The Sun is behaving itself with the solar flux at 145 and a quiet K-index of 2, so the bands are wide open. Point the beam at 20m and 17m for DX tonight.

The briefing is written from the same data the rest of the thread shows, and it is checked before it goes out: any invented detail (a CME, a time, a sunspot number), any number that disagrees with the data (a K-index or flare class the feeds do not show), or a reply that will not fit means the post is dropped and the thread goes out as the five data posts below. See [On-Air Briefing (LLM)](#-on-air-briefing-llm).

### Post 1: Solar Indices
<img src="media/solar_indices.png" alt="Solar Indices Post" width="500">

- Solar Flux Index (SFI)
- A-index & K-index
- Critical frequency (foF2)
- Maximum Usable Frequency (MUF)
- D-Layer absorption percentage
- NOAA Scales (R/S/G)

### Post 2: Band Conditions
<img src="media/band_conditions.png" alt="Band Conditions Post" width="500">

- 160m through 6m band-by-band conditions
- Quality indicators with emojis (🟢 Good, 🟡 Fair, 🔴 Closed)
- Best bands for current conditions
- MUF reference

### Post 3: D-Region Absorption
<img src="media/d-region.png" alt="D-Region Absorption Post" width="500">

- Current absorption status with D-RAP map image
- Time-based context (day/night)
- Band recommendations for conditions

### Post 4: Aurora Forecast
<img src="media/aurora.png" alt="Aurora Forecast Post" width="500">

- Aurora power level with aurora oval image
- K-index
- Visibility predictions
- VHF propagation notes

### Post 5: GOES X-Ray Flux
<img src="media/x-ray.png" alt="X-Ray Flux Post" width="500">

- Current X-ray classification
- 6-hour trend chart (generated)
- Solar flare impact assessment
- Radio blackout warnings

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher (3.10 not supported due to numpy requirements)
- Active Bluesky and/or Mastodon account
- Linux system with systemd (for systemd installation)
- Docker (for Docker installation)

### Option 1: Automated Installation with Installer Script (Recommended)

The installer script supports both Python and Docker deployments.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ChiefGyk3D/solarstorm_scout.git
   cd solarstorm_scout
   ```

2. **Create configuration:**
   ```bash
   cp .env.example .env
   nano .env  # Edit with your credentials
   ```

3. **Run installer:**
   ```bash
   chmod +x scripts/install-solarstorm.sh
   ./scripts/install-solarstorm.sh
   ```

4. **Follow prompts to:**
   - Set posting interval (default: 1.5 hours)
   - Choose deployment method: Python (venv or system) or Docker (GHCR or local build)
   - Optionally run a test post

> **Note:** The installer automatically handles Docker installation if you select Docker deployment. Docker must be installed on your system before running the installer.

### Option 2: Manual Docker Installation

For manual Docker deployment without the installer:

1. **Pull from GitHub Container Registry:**
   ```bash
   docker pull ghcr.io/chiefgyk3d/solarstorm_scout:latest
   ```

2. **Create configuration:**
   ```bash
   cp .env.example .env
   nano .env  # Edit with your credentials
   ```

3. **Run container:**
   ```bash
   docker run --rm --env-file=.env ghcr.io/chiefgyk3d/solarstorm_scout:latest
   ```

4. **Or build locally:**
   ```bash
   git clone https://github.com/ChiefGyk3D/solarstorm_scout.git
   cd solarstorm_scout
   docker build -t solarstorm_scout .
   docker run --rm --env-file=.env solarstorm_scout
   ```

5. **Schedule with cron:**
   ```bash
   crontab -e
   # Add: Run every 1.5 hours
   0 */1 * * * docker run --rm --env-file=/path/to/.env ghcr.io/chiefgyk3d/solarstorm_scout:latest
   30 */2 * * * docker run --rm --env-file=/path/to/.env ghcr.io/chiefgyk3d/solarstorm_scout:latest
   ```

### Option 3: Manual Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   `requirements.txt` is a generated lock with every dependency pinned to a
   version and its hashes; pip verifies each download against it. The direct
   dependencies live in `requirements.in`; see [Dependency lock](#dependency-lock).

2. **Configure:**
   ```bash
   cp .env.example .env
   nano .env
   ```

3. **Run manually:**
   ```bash
   python3 -m solarstorm_scout.main
   ```

## 🔧 Configuration

### Social Media Setup

#### Bluesky
1. Go to [Bluesky App Passwords](https://bsky.app/settings/app-passwords)
2. Create new app password: "SolarStorm Scout"
3. Copy password to `.env` file:
   ```env
   BLUESKY_ENABLE_POSTING=true
   BLUESKY_HANDLE=yourhandle.bsky.social
   BLUESKY_APP_PASSWORD=your-app-password
   ```
   (`BLUESKY_ENABLED=true`, the original name, still works.)

#### Mastodon
1. Log into your Mastodon instance
2. Go to Preferences → Development → New Application
3. Name: "SolarStorm Scout"
4. **Required Scopes**:
   - ✅ `read` - Verify account credentials
   - ✅ `write:statuses` - Post status updates and threads
   - ✅ `write:media` - Upload images to posts
5. Click "Submit" to create the application
6. Copy access token to `.env`:
   ```env
   MASTODON_ENABLE_POSTING=true
   MASTODON_API_BASE_URL=https://your-instance.social
   MASTODON_ACCESS_TOKEN=your-access-token
   ```
   (`MASTODON_ENABLED=true`, the original name, still works. The client id and secret are optional.)

### 🎙️ On-Air Briefing (LLM)

Off by default. Switch it on and point it at an Ollama server on your network, the same way the other daemons do:

```env
LLM_ENABLE=true
LLM_PROVIDER=ollama
LLM_OLLAMA_HOST=http://192.168.1.50   # your local LLM server
LLM_OLLAMA_PORT=11434
LLM_OLLAMA_MODEL=gemma3:4b
```

What happens each run:

1. The forecaster hands the run's numbers (SFI, K/A-index, foF2 and MUF, absorption, band-by-band conditions, aurora power, X-ray class, NOAA scales) to the model with a prompt that asks for a short spoken-style briefing and forbids anything not in the report.
2. The reply is cleaned (chatter, quotes, hashtags and URLs removed) and cut to a sentence end if it runs long.
3. It is checked against the data: a stated K-index, A-index or SFI must match; a flare class must match the current X-ray class (negated mentions like "no M-class flares" are fine); an R/S/G scale must match. hypeman's guardrails then reject invented events (CMEs, solar wind, sunspot numbers, clock times, weekdays, arrival forecasts), hype words, and stray hashtags or links.
4. One stricter retry if the first attempt failed. If that fails too, or the LLM is off or unreachable, **the thread is posted without the briefing** and looks exactly as it did before. The briefing can never block the data.

Optional settings, read by hypeman-social (full reference in its [configuration docs](https://github.com/ChiefGyk3D/hypeman/blob/main/docs/CONFIGURATION.md)):

| Variable | Meaning | Default |
|---|---|---|
| `LLM_TEMPERATURE` | Sampling temperature; low keeps a small model honest | `0.3` |
| `LLM_MAX_EMOJI_COUNT` | Reject replies with more emoji than this | `2` |
| `LLM_ENABLE_PROFANITY_FILTER` | Reject profanity | `false` |
| `LLM_FALLBACK_PROVIDER` | Opt-in failover, e.g. `gemini` (needs `pip install "hypeman-social[gemini]"` and `GEMINI_API_KEY`). Off means an Ollama outage costs the briefing, not your privacy | *(none)* |
| `LLM_ENABLE_THINKING_MODE` | Headroom for reasoning models (qwen3, gemma4) | `false` |

Preview what the model produces without posting anything:

```bash
python3 -m solarstorm_scout.demo   # includes the briefing when LLM_ENABLE=true
```

### Doppler Secrets Manager (Optional)

Instead of `.env` files, use Doppler:

1. Create [Doppler](https://doppler.com) account
2. Create project (e.g., "solarstorm-scout") and add secrets
3. Create config within the project (e.g., "dev", "prd")
4. Generate service token
5. Set in environment:
   ```env
   DOPPLER_TOKEN=your-service-token
   DOPPLER_PROJECT=solarstorm-scout
   DOPPLER_CONFIG=prd
   ```

> **Note:** Both `DOPPLER_PROJECT` and `DOPPLER_CONFIG` environment variables are required when using Doppler secrets management. The project is fetched once per run and shared between settings and credentials.

AWS Secrets Manager and HashiCorp Vault work too (`SECRETS_MANAGER=aws|vault`, install `hypeman-social[aws]` or `[vault]`); see the hypeman-social [configuration reference](https://github.com/ChiefGyk3D/hypeman/blob/main/docs/CONFIGURATION.md#secrets-managers).

## 🕐 Scheduling

### systemd Timer (Linux)

Automatically configured by `install-solarstorm.sh` script.

**View status:**
```bash
sudo systemctl status solarstorm-scout.timer
```

**View logs:**
```bash
sudo journalctl -u solarstorm-scout.service -f
```

**Manual run:**
```bash
sudo systemctl start solarstorm-scout.service
```

**Change interval:**
Edit `/etc/systemd/system/solarstorm-scout.timer` and change `OnUnitActiveSec=` value, then:
```bash
sudo systemctl daemon-reload
sudo systemctl restart solarstorm-scout.timer
```

### System Cron

For Docker or manual runs:

```bash
crontab -e
```

Add:
```cron
# Every 1.5 hours (at :00 and :30 past odd hours)
0 1-23/2 * * * cd /path/to/solarstorm-scout && python3 -m solarstorm_scout.main
30 0-22/2 * * * cd /path/to/solarstorm-scout && python3 -m solarstorm_scout.main

# Or with Docker
0 1-23/2 * * * docker run --rm --env-file=/path/to/.env ghcr.io/chiefgyk3d/solarstorm_scout:latest
30 0-22/2 * * * docker run --rm --env-file=/path/to/.env ghcr.io/chiefgyk3d/solarstorm_scout:latest
```

## 📊 Data Sources

All data fetched from [NOAA Space Weather Prediction Center](https://www.swpc.noaa.gov/):

- **Solar Flux Index**: 10.7cm radio emissions (F10.7)
- **Planetary K-index**: Geomagnetic activity
- **Aurora Power**: Hemispheric power index
- **GOES X-Ray Flux**: Real-time solar X-ray monitoring

Data updated every run (default: 1.5 hours).

## 🛠️ Development

### Project Structure

```
solarstorm_scout/
├── solarstorm_scout/
│   ├── __init__.py
│   ├── main.py          # Main bot orchestrator
│   ├── config.py        # Thin layer over hypeman-social's config/secrets
│   ├── spaceweather.py  # NOAA data fetcher
│   ├── formatter.py     # Message formatter (thread layout and numbering)
│   ├── forecaster.py    # On-air briefing via hypeman-social's LLM manager
│   ├── social.py        # Thread posting through hypeman-social's platforms
│   ├── chart_renderer.py # GOES X-ray chart generator
│   └── demo.py          # Preview tool
├── tests/               # pytest suite (formatter, forecaster, posting flow)
├── scripts/
│   ├── install-solarstorm.sh    # Automated installer (Python + Docker)
│   └── uninstall-solarstorm.sh  # Uninstaller
├── systemd/
│   ├── solarstorm-scout.service.template  # systemd service template
│   └── solarstorm-scout.timer.template    # systemd timer template
├── media/
│   ├── banner.png       # README banner
│   ├── logo.png         # Project logo
│   ├── aurora.png       # Example aurora post
│   ├── band_conditions.png  # Example band conditions post
│   ├── d-region.png     # Example D-region post
│   ├── solar_indices.png    # Example solar indices post
│   ├── x-ray.png        # Example X-ray post
│   └── streamelements.png   # Donation image
├── .github/
│   └── workflows/       # CI/CD pipelines
├── .env.example
├── requirements.in          # Direct dependencies
├── requirements.txt         # Generated lock: every dependency pinned with hashes
├── requirements-dev.in      # + pytest and ruff
├── requirements-dev.txt     # Generated lock for development and CI
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── docker-compose.oneshot.yml
├── LICENSE
└── README.md
```

### Dependency lock

`requirements.in` lists the direct dependencies; Bluesky and Mastodon posting,
the LLM layer and config/secrets come in through `hypeman-social` and its
extras. `requirements.txt` is
generated from it and pins every dependency, transitive ones included, to a
version and its SHA-256 hashes. pip enters hash-checking mode by itself when it
reads the file, so `pip install -r requirements.txt` verifies every download,
and CI and the Docker image install with `--require-hashes`: a package
re-uploaded under the same version fails to install instead of shipping. To
add or bump a dependency, edit `requirements.in` and regenerate the lock with
the command in its header; never edit `requirements.txt` by hand. Dependabot
regenerates it for version bumps.

### Running Tests

```bash
# Install the development lock (runtime deps + pytest + ruff)
pip install --require-hashes -r requirements-dev.txt

# Run tests (no network: platforms and the LLM are faked)
pytest

# Lint (CI runs the same)
ruff check solarstorm_scout/ tests/
```

## 🔍 Troubleshooting

### Bot not posting

1. **Check service status:**
   ```bash
   sudo systemctl status solarstorm-scout.timer
   sudo systemctl status solarstorm-scout.service
   ```

2. **View logs:**
   ```bash
   sudo journalctl -u solarstorm-scout.service -n 50
   ```

3. **Test manually:**
   ```bash
   cd /path/to/solarstorm-scout
   source venv/bin/activate  # if using venv
   python3 -m solarstorm_scout.main
   ```

### Authentication errors

- **Bluesky**: Verify app password (not account password)
- **Mastodon**: Check access token and API base URL
- **Permissions**: Ensure scopes include `read` and `write`

### NOAA data fetch errors

- Check internet connectivity
- NOAA APIs occasionally timeout - bot will retry on next run
- View detailed logs: `LOG_LEVEL=DEBUG` in `.env`

### Docker issues

```bash
# Pull latest image
docker pull ghcr.io/chiefgyk3d/solarstorm_scout:latest

# Test container manually
docker run --rm --env-file=.env ghcr.io/chiefgyk3d/solarstorm_scout:latest

# Build locally if needed
docker build --no-cache -t solarstorm_scout .
docker run --rm --env-file=.env solarstorm_scout
```

## 📝 License

Mozilla Public License 2.0 (MPL-2.0)

**Commercial Use Requirements:**
- ✅ You MAY use this software commercially
- ✅ You MAY modify this software for commercial purposes
- ⚠️ You MUST share any modifications to MPL-licensed files under the same MPL 2.0 license
- ⚠️ Modified versions must clearly indicate changes were made
- ✅ You can combine with proprietary software (file-level copyleft, not project-level)

**In Summary:** If you modify any of the Python files in `solarstorm_scout/`, you must contribute those changes back under MPL 2.0. Your larger project can remain proprietary, but the modified bot code must be open source.

See [LICENSE](LICENSE) file for complete details.

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📧 Support

- **Issues**: [GitHub Issues](https://github.com/ChiefGyk3D/solarstorm_scout/issues)
- **Discussions**: [GitHub Discussions](https://github.com/ChiefGyk3D/solarstorm_scout/discussions)

## 🙏 Acknowledgments

- **NOAA Space Weather Prediction Center** - For excellent public APIs
- **Amateur Radio Community** - For inspiration and support
- **Bluesky & Mastodon** - For open social media platforms

## 📖 Related Projects

- [hypeman-social](https://github.com/ChiefGyk3D/hypeman) - The shared posting, LLM and config core this bot is built on
- [Penguin Overlord](https://github.com/chiefgyk3d/penguin-overlord) - Discord bot with HAM radio features
- [NOAA Space Weather](https://www.swpc.noaa.gov/) - Official NOAA space weather site

---

## 💝 Support This Project

If you find SolarStorm Scout useful, consider supporting continued development.
Everything is also collected at **[support.chiefgyk3d.com](https://support.chiefgyk3d.com)**.

### Recurring Support

<div align="center">
<table>
  <tr>
    <td align="center" width="150">
      <a href="https://patreon.com/chiefgyk3d" title="Patreon">
        <img src="media/icons/patreon.svg" width="36" height="36" alt="Patreon"><br>
        <sub><b>Patreon</b></sub>
      </a>
    </td>
    <td align="center" width="150">
      <a href="https://streamelements.com/chiefgyk3d/tip" title="StreamElements">
        <img src="media/streamelements.png" width="36" height="36" alt="StreamElements"><br>
        <sub><b>StreamElements</b></sub>
      </a>
    </td>
    <td align="center" width="150">
      <a href="https://shop.chiefgyk3d.com/" title="Merch Store">
        <img src="media/icons/merch.svg" width="36" height="36" alt="Merch"><br>
        <sub><b>Merch Store</b></sub>
      </a>
    </td>
  </tr>
</table>
</div>

### Cryptocurrency Tips

<div align="center">
<table>
  <tr>
    <td align="center" width="60"><img src="media/icons/bitcoin.svg" width="28" height="28" alt="Bitcoin"></td>
    <td><b>Bitcoin</b><br><code>bc1qztdzcy2wyavj2tsuandu4p0tcklzttvdnzalla</code></td>
  </tr>
  <tr>
    <td align="center" width="60"><img src="media/icons/monero.svg" width="28" height="28" alt="Monero"></td>
    <td><b>Monero</b><br><code>84Y34QubRwQYK2HNviezeH9r6aRcPvgWmKtDkN3EwiuVbp6sNLhm9ffRgs6BA9X1n9jY7wEN16ZEpiEngZbecXseUrW8SeQ</code></td>
  </tr>
  <tr>
    <td align="center" width="60"><img src="media/icons/ethereum.svg" width="28" height="28" alt="Ethereum"></td>
    <td><b>Ethereum</b><br><code>0x554f18cfB684889c3A60219BDBE7b050C39335ED</code></td>
  </tr>
  <tr>
    <td align="center" width="60"><img src="media/icons/solana.svg" width="28" height="28" alt="Solana"></td>
    <td><b>Solana</b><br><code>5T8h3HbyvHgLxwXgchRYbHSqRjZyAr8J7uwjLN9Fh8Jh</code></td>
  </tr>
</table>
</div>

---

## 👤 Author & Socials

<div align="center">
<table>
  <tr>
    <td align="center" width="90"><a href="https://social.chiefgyk3d.com/@chiefgyk3d" title="Mastodon"><img src="media/icons/mastodon.svg" width="30" height="30" alt="Mastodon"><br><sub>Mastodon</sub></a></td>
    <td align="center" width="90"><a href="https://bsky.app/profile/chiefgyk3d.com" title="Bluesky"><img src="media/icons/bluesky.svg" width="30" height="30" alt="Bluesky"><br><sub>Bluesky</sub></a></td>
    <td align="center" width="90"><a href="https://twitch.tv/chiefgyk3d" title="Twitch"><img src="media/icons/twitch.svg" width="30" height="30" alt="Twitch"><br><sub>Twitch</sub></a></td>
    <td align="center" width="90"><a href="https://www.youtube.com/channel/UCvFY4KyqVBuYd7JAl3NRyiQ" title="YouTube"><img src="media/icons/youtube.svg" width="30" height="30" alt="YouTube"><br><sub>YouTube</sub></a></td>
    <td align="center" width="90"><a href="https://kick.com/chiefgyk3d" title="Kick"><img src="media/icons/kick.svg" width="30" height="30" alt="Kick"><br><sub>Kick</sub></a></td>
    <td align="center" width="90"><a href="https://www.tiktok.com/@chiefgyk3d" title="TikTok"><img src="media/icons/tiktok.svg" width="30" height="30" alt="TikTok"><br><sub>TikTok</sub></a></td>
    <td align="center" width="90"><a href="https://discord.chiefgyk3d.com" title="Discord"><img src="media/icons/discord.svg" width="30" height="30" alt="Discord"><br><sub>Discord</sub></a></td>
    <td align="center" width="90"><a href="https://matrix-invite.chiefgyk3d.com" title="Matrix"><img src="media/icons/matrix.svg" width="30" height="30" alt="Matrix"><br><sub>Matrix</sub></a></td>
  </tr>
</table>
</div>

<div align="center"><sub>Made with ❤️ by <a href="https://github.com/ChiefGyk3D">ChiefGyk3D</a></sub></div>
