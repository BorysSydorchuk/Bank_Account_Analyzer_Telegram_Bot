FROM python:3.12-slim

WORKDIR /app

# System deps needed to build cryptography/psycopg wheels on some platforms
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# python -m (rather than the bare uvicorn script) guarantees /app is on sys.path,
# so `app/` can import the sibling `kbc_analyzer/` package.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]