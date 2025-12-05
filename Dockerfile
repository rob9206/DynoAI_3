# DynoAI Backend Dockerfile
# Multi-stage build for optimized production image

# =============================================================================
# Stage 1: Build stage
# =============================================================================
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
COPY api/requirements.txt ./api-requirements.txt

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r api-requirements.txt

# =============================================================================
# Stage 2: Production stage
# =============================================================================
FROM python:3.11-slim as production

# Labels for container metadata
LABEL org.opencontainers.image.title="DynoAI API Server"
LABEL org.opencontainers.image.description="AI-powered dyno tuning toolkit for Harley-Davidson ECM optimization"
LABEL org.opencontainers.image.version="1.2.0"
LABEL org.opencontainers.image.vendor="DynoAI"

# Create non-root user for security
RUN groupadd --gid 1000 dynoai && \
    useradd --uid 1000 --gid dynoai --shell /bin/bash --create-home dynoai

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy application code
COPY --chown=dynoai:dynoai api/ ./api/
COPY --chown=dynoai:dynoai dynoai/ ./dynoai/
COPY --chown=dynoai:dynoai io_contracts.py .
COPY --chown=dynoai:dynoai ai_tuner_toolkit_dyno_v1_2.py .
COPY --chown=dynoai:dynoai tables/ ./tables/
COPY --chown=dynoai:dynoai templates/ ./templates/

# Create necessary directories with proper permissions
RUN mkdir -p uploads outputs runs && \
    chown -R dynoai:dynoai uploads outputs runs

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DYNOAI_HOST=0.0.0.0 \
    DYNOAI_PORT=5001 \
    DYNOAI_DEBUG=false \
    DYNOAI_UPLOAD_DIR=/app/uploads \
    DYNOAI_OUTPUT_DIR=/app/outputs \
    DYNOAI_RUNS_DIR=/app/runs

# Expose the API port
EXPOSE 5001

# Health check - uses readiness probe for accurate container status
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5001/api/health/ready || exit 1

# Switch to non-root user
USER dynoai

# Run the application
CMD ["python", "-m", "api.app"]

# =============================================================================
# Stage 3: Development stage (optional, for local development)
# =============================================================================
FROM production as development

USER root

# Install development dependencies
RUN pip install --no-cache-dir \
    pytest \
    pytest-cov \
    black \
    ruff \
    mypy

# Switch back to non-root user
USER dynoai

# Enable debug mode for development
ENV DYNOAI_DEBUG=true

# Override command for development with hot reload
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=5001", "--reload"]

