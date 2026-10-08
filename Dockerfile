# The base image is pinned by digest so a rebuild is reproducible and a
# retagged upstream image cannot slip in; Dependabot moves the digest.
FROM python:3.14-slim@sha256:caaf356f40667c496d405780745b9ac25771c189a51dfcc42430d531ea09f8a2

LABEL maintainer="SolarStorm Scout Team"
LABEL description="Space Weather Social Media Bot - Posts HF propagation updates"

# Set working directory
WORKDIR /app

# Install system dependencies and upgrade
# Apt versions are left unpinned on purpose: the base image is pinned by digest,
# and Debian removes superseded package versions, so exact apt pins would break
# the build at every security update.
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies, then remove pip from the runtime image. The
# bot never runs pip, and pip's own vendored libraries (listed in
# pip/_vendor/bom.cdx.json: msgpack 1.1.2, setuptools 70.3.0) are what Trivy
# reports as Python-level findings; no requirement installs either package,
# and pip is already the latest release, so upgrading cannot clear them.
# Dropping pip removes that code, and the findings, from the shipped image.
RUN pip install --no-cache-dir --require-hashes -r requirements.txt && \
    pip uninstall -y pip

# Copy application code
COPY solarstorm_scout/ ./solarstorm_scout/

# Create logs directory
RUN mkdir -p /app/logs

# Dedicated non-root user. UID/GID 1000 matches the owner of the host's
# existing ./logs bind mount, so no chown is needed. /app/logs holds the
# run-tracking files the bot writes.
RUN groupadd --gid 1000 solarstorm && \
    useradd --uid 1000 --gid 1000 --create-home --shell /usr/sbin/nologin solarstorm && \
    chown -R solarstorm:solarstorm /app

USER 1000:1000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Run the bot
CMD ["python3", "-m", "solarstorm_scout.main"]
