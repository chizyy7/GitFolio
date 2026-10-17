# ---------------------------------------------------------------------------
# GitFolio backend — FastAPI + pygit2 + the local AI client libraries.
#
# Build:  docker build -t gitfolio-backend ./backend
# Run:    docker run -p 8000:8000 --env-file .env gitfolio-backend
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# libffi/libgcc are needed by the compiled wheels; git is handy for debugging.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libffi8 libgcc-s1 curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ------------------------------------------------------------------ deps
# Copy only the requirements first so the (slow) dependency layer is cached
# independently of the source code.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# ------------------------------------------------------------------ source
COPY . .

# Where bare Git object databases live; mounted as a volume in compose.
ENV STORAGE_PATH=/data/repos
RUN mkdir -p /data/repos

EXPOSE 8000

# Readiness probe hits the DB and reports the optional AI dependencies.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

# Production server: gunicorn supervising uvicorn workers. The long timeout
# accommodates first-token latency from a cold Llama 3.2 model.
CMD ["gunicorn", "app.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "4", \
     "-b", "0.0.0.0:8000", \
     "--timeout", "300", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
