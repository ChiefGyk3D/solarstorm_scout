# 🚀 SolarStorm Scout - Quick Start Guide

Get posting space weather updates in under 5 minutes!

## Prerequisites Checklist

- [ ] Python 3.8+ installed
- [ ] Bluesky account OR Mastodon account (or both!)
- [ ] Linux system (for systemd) OR Docker installed

## Installation in 4 Steps

### Step 1: Get Your Social Media Credentials

**For Bluesky:**
1. Go to https://bsky.app/settings/app-passwords
2. Click "Add App Password"
3. Name it: "SolarStorm Scout"
4. **Copy the password immediately** (you won't see it again!)
5. Your handle is your username + domain (e.g., `alice.bsky.social`)

**For Mastodon:**
1. Log into your Mastodon instance
2. Go to: Preferences → Development → New Application
3. Application name: "SolarStorm Scout"
4. Scopes: Check `read` and `write`
5. Click "Submit"
6. Copy the "Your access token" value

### Step 2: Clone and Configure

```bash
# Clone repository
git clone https://github.com/chiefgyk3d/solarstorm-scout.git
cd solarstorm-scout

# Copy example config
cp .env.example .env

# Edit with your credentials
nano .env
```

**Minimum .env configuration (Bluesky example):**
```env
LOG_LEVEL=INFO

BLUESKY_ENABLED=true
BLUESKY_HANDLE=yourhandle.bsky.social
BLUESKY_APP_PASSWORD=your-app-password-here

MASTODON_ENABLED=false
```

### Step 3: Choose Installation Method

#### Option A: Automated Installer (Recommended)

The installer script supports both Python and Docker deployments:

```bash
chmod +x scripts/install-solarstorm.sh
./scripts/install-solarstorm.sh
```

Follow the prompts:
- Set interval: Press Enter for 1.5 hours (default)
- Choose timer type: Fixed schedule or relative timing
- Deployment method: Choose Python (venv/system) or Docker (GHCR/local build)
- Test post: Choose Y to verify it works

> **Note:** If you choose Docker deployment, Docker must be installed on your system first.

Done! 🎉

#### Option B: Manual Docker Install

```bash
# Run with docker-compose scheduler
docker-compose up -d

# Check logs
docker logs -f solarstorm-scout
```

#### Option C: Manual Run

```bash
# Install dependencies
pip install -r requirements.txt

# Run once
python3 -m solarstorm_scout.main
```

### Step 4: Verify It's Working

**For systemd:**
```bash
# Check timer status
sudo systemctl status solarstorm-scout.timer

# View logs
sudo journalctl -u solarstorm-scout.service -f

# Run test post
sudo systemctl start solarstorm-scout.service
```

**For Docker:**
```bash
# View logs
docker logs solarstorm-scout

# Check scheduler
docker logs solarstorm-scheduler
```

**Check your social media** - you should see a 4-part thread with space weather data!

## Common Issues

### "Authentication failed"
- **Bluesky**: Use app password, NOT your account password
- **Mastodon**: Verify access token is correct and has `read` + `write` scopes

### "No platforms configured"
- Check `.env` file has `BLUESKY_ENABLED=true` or `MASTODON_ENABLED=true`
- Verify credentials are filled in (no empty values)

### Service won't start
```bash
# Check for errors
sudo journalctl -u solarstorm-scout.service -n 50

# Try manual run to see error details
cd /path/to/solarstorm-scout
source venv/bin/activate
python3 -m solarstorm_scout.main
```

## Customization

### Change Posting Interval

**systemd:**
```bash
sudo nano /etc/systemd/system/solarstorm-scout.timer
# Change OnUnitActiveSec=5400s (1.5 hours) to desired seconds
sudo systemctl daemon-reload
sudo systemctl restart solarstorm-scout.timer
```

**Docker:**
```bash
nano docker-compose.yml
# Change: ofelia.job-exec.solarstorm.schedule: "@every 2h"
docker-compose restart
```

### Enable Both Platforms

Edit `.env`:
```env
BLUESKY_ENABLED=true
BLUESKY_HANDLE=yourhandle.bsky.social
BLUESKY_APP_PASSWORD=your-password

MASTODON_ENABLED=true
MASTODON_API_BASE_URL=https://mastodon.social
MASTODON_ACCESS_TOKEN=your-token
```

Restart service:
```bash
sudo systemctl restart solarstorm-scout.timer
# or
docker-compose restart
```

## What Gets Posted?

Every 1.5 hours (or your chosen interval), a 4-part thread:

1. **HF Propagation**: Solar flux, K-index, overall conditions
2. **D-Region Absorption**: Current absorption levels, band recommendations  
3. **Aurora Forecast**: Aurora power, visibility, VHF conditions
4. **X-Ray Flux**: GOES solar X-ray classification, flare impacts

## Next Steps

- Monitor logs to ensure reliable posting
- Adjust interval based on your audience
- Check out the full README.md for advanced options
- Star the repo if you find it useful! ⭐

## Support

Having issues? 
- Read full docs: [README.md](README.md)
- Check troubleshooting section
- Open an issue: https://github.com/chiefgyk3d/solarstorm-scout/issues

---

**Happy space weather posting! 73!** 📡🌞
