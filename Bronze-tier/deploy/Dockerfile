# Platinum Tier - Cloud Agent Docker Image
# AI Employee Hackathon - Cloud VM Deployment
#
# This image runs:
# - cloud_agent.py (24/7 task processing)
# - sync_vault.py (Git-based vault sync)
# - Watchdog (health monitoring)

FROM python:3.11-slim

# Labels
LABEL maintainer="AI Employee Hackathon"
LABEL version="1.0.0"
LABEL description="Platinum Tier Cloud Agent"

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV TZ=UTC
ENV VAULT_AGENT_ID=cloud
ENV VAULT_SYNC_BRANCH=main
ENV SYNC_INTERVAL=60
ENV AGENT_INTERVAL=30

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    openssh-client \
    curl \
    vim \
    tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN useradd -m -s /bin/bash aiemployee \
    && mkdir -p /app /data /logs /ssh \
    && chown -R aiemployee:aiemployee /app /data /logs /ssh

# Set working directory
WORKDIR /app

# Copy requirements first (for caching)
COPY deploy/requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY scripts/ /app/scripts/
COPY utils/ /app/utils/
COPY config/ /app/config/
COPY deploy/entrypoint.sh /app/entrypoint.sh
COPY deploy/healthcheck.py /app/healthcheck.py

# Make scripts executable
RUN chmod +x /app/entrypoint.sh \
    && chmod +x /app/scripts/*.py \
    && chown -R aiemployee:aiemployee /app

# Create mount points
VOLUME ["/data/AI_Employee_Vault", "/ssh", "/logs"]

# Switch to non-root user
USER aiemployee

# Health check
HEALTHCHECK --interval=60s --timeout=30s --start-period=30s --retries=3 \
    CMD python /app/healthcheck.py || exit 1

# Default command
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["all"]
