# syntax=docker/dockerfile:1.6
# ----------------------------------------------------------------------------
# EduBot backend image
# ----------------------------------------------------------------------------
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# System libs needed for: psycopg2 (libpq), pymssql/pyodbc (unixodbc),
# sentence-transformers compile fallbacks, ssl, and healthchecks.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        ca-certificates \
        libpq-dev \
        unixodbc-dev \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for layer caching
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

# Copy source
COPY backend/ /app/

# Create writable data dir (for SQLite demo, Chroma persistence)
RUN mkdir -p /app/app/data /app/app/chroma_db

EXPOSE 8000

# Healthcheck — backend must answer /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# uvicorn workers tuned for low-resource self-hosted school servers; bump in prod
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
