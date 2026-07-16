# Stage 1: Build Go gateway
FROM golang:1.25-alpine AS go-builder
WORKDIR /build/gateway
COPY gateway/ .
RUN go build -o /whaagent-gateway .

# Stage 2: Python API base
FROM python:3.12-slim AS python-base

# Set working directory
WORKDIR /app

# Install uv for Python package management
# Copy from the official installer: https://github.com/astral-sh/uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install Search Tools and Network Diagnostics
# ripgrep: ultra-fast text searching
# fd-find: user-friendly alternative to 'find'
# fzf: general-purpose command-line fuzzy finder
# libmagic: Required by neonize/python-magic for file type detection
# curl: For testing HTTP/HTTPS connections
# dnsutils: For DNS resolution troubleshooting
# ffmpeg: Required by pydub for audio conversion (WhatsApp voice messages are OGG format)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ripgrep \
    fd-find \
    fzf \
    libmagic1 \
    curl \
    dnsutils \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Note: In Debian/Ubuntu, the 'fd' executable is renamed to 'fdfind'.
# We create a symbolic link so the agent can just call 'fd'.
RUN ln -s $(which fdfind) /usr/local/bin/fd

# Python Environment Setup

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

# Copy project files needed for dependency installation
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY config ./config

# Install dependencies using uv
# This installs the package in editable mode with all dependencies
RUN uv sync --frozen --no-dev

# Install Playwright Chromium browser + system dependencies for Crawl4AI
RUN uv run playwright install --with-deps chromium

# Copy Go binary from go-builder stage
COPY --from=go-builder /whaagent-gateway /usr/local/bin/

# Create logs directory
RUN mkdir -p /app/logs

# Stage 3: Runtime
FROM python-base

# Health check for the application
HEALTHCHECK --interval=30s --timeout=5s CMD curl -f http://localhost:8000/health || exit 1

# Set the default command to run both services
CMD ["sh", "-c", "whaagent-gateway & whaagent serve"]
