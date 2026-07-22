# Container for the Cloud Run pipeline service (GCP mode).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CANONIFY_MODE=gcp

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY data ./data

# Install the package with GCP extras.
RUN pip install --upgrade pip && pip install ".[gcp]"

EXPOSE 8080

# Eventarc delivers CloudEvents over HTTP to this server.
CMD ["python", "-m", "canonify.server"]
