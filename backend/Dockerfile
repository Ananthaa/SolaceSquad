# Dockerfile for Cloud Run
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

# Run application
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
