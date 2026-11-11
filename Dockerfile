# Dockerfile for CodeDNA backend

FROM python:3.14-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for layer caching
COPY pyproject.toml ./

# Copy application source
COPY src/ ./src/

# Install Python dependencies and the application package
RUN pip install --no-cache-dir .

# Expose API port
EXPOSE 8000

# Run the API server
CMD ["sh", "-c", "uvicorn codna.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
