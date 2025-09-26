# Dockerfile for CitizenServe Scraper with Patchright
# Designed for production deployment on Oracle VPS

FROM python:3.11-slim

# Set environment variables for Docker
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies including Xvfb for headed mode
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    curl \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome (not Chromium) for better stealth
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Create downloads directory with proper permissions
RUN mkdir -p /app/downloads && chmod 755 /app/downloads

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Patchright chromium driver
RUN patchright install chromium

# Copy application code
COPY citizenserve_scraper.py .
COPY BypassV3/ ./BypassV3/

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.path.append('BypassV3'); from bypass import ReCaptchaV3Bypass; print('OK')" || exit 1

# Default command with Xvfb for headed mode
CMD ["xvfb-run", "-a", "--server-args=-screen 0 1920x1080x24", "python", "citizenserve_scraper.py"]

# Labels for maintainability
LABEL maintainer="Dominion Intelligence Platform"
LABEL description="CitizenServe permit scraper with Patchright stealth automation"
LABEL version="1.0.0"