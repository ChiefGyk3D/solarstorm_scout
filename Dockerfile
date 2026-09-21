# The base image is pinned by digest so a rebuild is reproducible and a
# retagged upstream image cannot slip in; Dependabot moves the digest.
FROM python:3.14-slim@sha256:caaf356f40667c496d405780745b9ac25771c189a51dfcc42430d531ea09f8a2

LABEL maintainer="SolarStorm Scout Team"
LABEL description="Space Weather Social Media Bot - Posts HF propagation updates"

# Set working directory
WORKDIR /app

# Install system dependencies and upgrade
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
RUN pip install --no-cache-dir -r requirements.txt && \
    pip uninstall -y pip

# Copy application code
COPY solarstorm_scout/ ./solarstorm_scout/

# Create logs directory
RUN mkdir -p /app/logs

# Create non-root user
RUN useradd -m -u 1000 solarstorm && \
    chown -R solarstorm:solarstorm /app

USER solarstorm

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Run the bot
CMD ["python3", "-m", "solarstorm_scout.main"]
