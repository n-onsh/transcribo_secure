# Use official PyTorch image with CUDA 11.8 (as required by the task list)
FROM pytorch/pytorch:2.1.2-cuda11.8-cudnn8-runtime

# Install system dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy .env file so that pydantic BaseSettings can load configuration
COPY .env .

# Install Python dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV HF_HUB_ENABLE_HF_TRANSFER=1

# Set entrypoint
CMD ["python3", "-m", "src.main"]
