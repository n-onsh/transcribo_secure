FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install PyTorch first
RUN pip3 install torch==2.1.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cu121

# Then install other requirements
COPY requirements.txt .
RUN sed -i '/torch==/d' requirements.txt && \
    sed -i '/torchaudio==/d' requirements.txt && \
    pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run the application
CMD ["python3", "-m", "src.main"]