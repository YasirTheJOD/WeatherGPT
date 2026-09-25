# WeatherGPT backend image (Phase 7 deployment).
#
# The app is config-driven (backend/app/core/config.py) and fails open on
# Postgres/Redis, so the same image runs locally, in docker compose, or on a
# plain box — only env vars change. See docs/DEPLOYMENT.md.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Project metadata + sources. `pip install .` needs the package present, so
# this is one layer (fine for a prototype image; rebuilds are quick).
COPY pyproject.toml ./
COPY app ./app
COPY data ./data
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# Run as a non-root user; 8000 is unprivileged so nothing else is needed.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Compose inherits this healthcheck (services depend on it via
# `condition: service_healthy`); it hits the readiness endpoint, which is
# exempt from rate limiting.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
