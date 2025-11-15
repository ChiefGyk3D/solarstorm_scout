FROM python:3.14-slim

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

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

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
