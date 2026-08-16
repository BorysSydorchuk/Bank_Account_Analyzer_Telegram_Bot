FROM python:3.12-slim

WORKDIR /app

# System deps needed to build cryptography/psycopg wheels on some platforms
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# S4-09 Item 1: don't run the app as root. Shared by both containers built
# from this Dockerfile (backend and celery_worker, per docker-compose.yml)
# — the celery_worker in particular handles the Enable Banking OAuth
# callback and writes/reads eb_session.json, so this user needs real
# access to that file, not just to run the server process.
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser
USER appuser

EXPOSE 8000

# python -m (rather than the bare uvicorn script) guarantees /app is on sys.path,
# so `app/` can import the sibling `kbc_analyzer/` package.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]