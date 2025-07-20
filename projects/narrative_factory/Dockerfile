# Multi-stage Docker build for production optimization
# CodeFarm T04 Production Optimization Implementation

FROM python:3.12-slim as base

# Install system dependencies and security updates
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    ca-certificates \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash --uid 1000 app
WORKDIR /home/app

# Install UV for fast Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set environment variables for production
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    PATH="/home/app/.local/bin:$PATH"

# Development stage
FROM base as development
USER app

# Copy dependency files
COPY --chown=app:app pyproject.toml uv.lock ./

# Install all dependencies including dev dependencies
RUN uv sync --dev

# Copy application code
COPY --chown=app:app . .

# Development server with hot reload
CMD ["uv", "run", "uvicorn", "src.web.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production dependencies stage
FROM base as deps
USER app

# Copy dependency files
COPY --chown=app:app pyproject.toml uv.lock ./

# Install only production dependencies
RUN uv sync --frozen --no-dev

# Production stage
FROM python:3.12-slim as production
USER root

# Install only runtime dependencies and security updates
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && apt-get upgrade -y \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash --uid 1000 app
WORKDIR /home/app

# Copy UV binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy Python environment from deps stage
COPY --from=deps --chown=app:app /home/app/.local /home/app/.local

# Copy application code
COPY --chown=app:app src/ ./src/
COPY --chown=app:app scripts/ ./scripts/
COPY --chown=app:app pyproject.toml ./

# Set environment variables for production
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    PATH="/home/app/.local/bin:$PATH" \
    ENVIRONMENT=production \
    LOG_LEVEL=INFO

# Switch to non-root user
USER app

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Production startup with Gunicorn for better performance
CMD ["uv", "run", "gunicorn", "src.web.app:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "60", \
     "--keep-alive", "5", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]

# Multi-platform build targets
FROM production as production-arm64
# ARM64-specific optimizations can be added here if needed

FROM production as production-amd64
# AMD64-specific optimizations can be added here if needed