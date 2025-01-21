FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

# Install base utilities
RUN apt-get update && apt-get install -y \
    ffmpeg \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run the application
CMD ["python3", "-m", "src.main"]