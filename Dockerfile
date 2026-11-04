# Dockerfile for CodeDNA backend

FROM python:3.14-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for layer caching
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir -e ".[dev]"

# Copy application source
COPY src/ ./src/

# Expose API port
EXPOSE 8000

# Run the API server
CMD ["uvicorn", "codna.api:app", "--host", "0.0.0.0", "--port", "8000"]
