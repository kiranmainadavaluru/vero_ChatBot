FROM python:3.11-slim

WORKDIR /app

# System deps some Python packages need to build (psycopg2, sentence-transformers deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

EXPOSE 8000

# gunicorn instead of the Flask dev server for anything beyond localhost.
# Single worker keeps memory down (sentence-transformers/torch is heavy) --
# raise workers only if your host has the RAM for multiple model copies.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "120", "app:app"]