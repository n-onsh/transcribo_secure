FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ffmpeg \
    git \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*


# Install Python dependencies first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p /app/static /app/data /app/data/in /app/data/out /app/data/error /app/data/worker

# Copy application code
COPY . .

# Set permissions
RUN chmod -R 755 /app/static /app/data

# Environment variables
ENV PYTHONPATH=/app
ENV STATIC_PATH=/app/static
ENV STORAGE_SECRET=${STORAGE_SECRET}
ENV BACKEND_API_URL=${BACKEND_API_URL}
ENV REFRESH_INTERVAL=${REFRESH_INTERVAL}
ENV MAX_UPLOAD_SIZE=${MAX_UPLOAD_SIZE}
ENV ENVIRONMENT=production

# OpenTelemetry configuration
ENV OTEL_RESOURCE_ATTRIBUTES=service.name=transcribo-frontend
ENV OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
ENV OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
ENV OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/health || exit 1

# Expose port
EXPOSE 8501

# Set entrypoint with proper command for NiceGUI
ENTRYPOINT ["python", "src/main.py"]

