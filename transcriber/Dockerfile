FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg git build-essential python3-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install whisperx from git with its dependencies
RUN git clone https://github.com/m-bain/whisperx.git /tmp/whisperx && \
    cd /tmp/whisperx && \
    pip install .

# Install monitoring requirements
COPY requirements.txt .
RUN pip install -r requirements.txt

# Set environment variables
ENV PYTHONPATH=/app \
    HF_HUB_ENABLE_HF_TRANSFER=1

# Fail if HF_AUTH_TOKEN is not provided
ARG HF_AUTH_TOKEN
ENV HF_AUTH_TOKEN=${HF_AUTH_TOKEN}
RUN if [ -z "$HF_AUTH_TOKEN" ]; then echo "HF_AUTH_TOKEN must be provided" && exit 1; fi

# Copy application code
COPY . .

CMD ["python3", "-m", "src.main"]
