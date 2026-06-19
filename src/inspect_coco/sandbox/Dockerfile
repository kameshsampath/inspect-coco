FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    bash \
    bc \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Python test dependencies
RUN pip install --no-cache-dir pytest pytest-json-ctrf pyyaml

# Cortex Code CLI
# CORTEX_CHANNEL can be: stable, beta, canary
ARG CORTEX_CHANNEL=beta
ENV CORTEX_CHANNEL=${CORTEX_CHANNEL}
RUN curl -LsS https://ai.snowflake.com/static/cc-scripts/install.sh -o /tmp/install.sh \
    && SKIP_PODMAN=1 NON_INTERACTIVE=1 CORTEX_CHANNEL=${CORTEX_CHANNEL} sh /tmp/install.sh \
    && rm /tmp/install.sh

# Ensure tools are on PATH
ENV PATH="/root/.local/bin:$PATH"

# Disable telemetry in evals
ENV COCO_TELEMETRY_DISABLED=true

WORKDIR /workspace
CMD ["tail", "-f", "/dev/null"]
