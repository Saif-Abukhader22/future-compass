# identity-service (FastAPI) - DigitalOcean App Platform ready
FROM python:3.11-slim-bullseye

# Safer runtime defaults + app paths
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/app \
    PORT=8080 \
    WEB_CONCURRENCY=2

WORKDIR $APP_HOME

# ---- System deps (build & runtime) ----
# libpq-dev + build-essential only needed if you compile psycopg from source.
# file is for python-magic; remove if unused.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpq-dev build-essential file ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ---- Python deps first (better layer caching) ----
COPY identity_service/requirements.txt ./identity_service/requirements.txt
COPY shared/requirements.txt          ./shared/requirements.txt

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r identity_service/requirements.txt \
 && pip install --no-cache-dir -r shared/requirements.txt

# ---- App source ----
COPY identity_service/ ./identity_service
COPY shared/            ./shared

# ---- Shrink: drop build tools after wheels are installed ----
RUN apt-get purge -y build-essential libpq-dev && apt-get autoremove -y && apt-get clean

# ---- Non-root user ----
RUN useradd -m appuser && chown -R appuser:appuser $APP_HOME
USER appuser

# App Platform routes to $PORT (default 8080)
EXPOSE 8080

# Use $PORT and tunable worker count
CMD sh -c 'uvicorn identity_service.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers ${WEB_CONCURRENCY:-2}'
