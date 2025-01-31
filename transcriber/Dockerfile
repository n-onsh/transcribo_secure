FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    python3 \
    python3-pip \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Set environment variables for Hugging Face
ENV HF_HOME=/root/.cache/huggingface
ENV TRANSFORMERS_CACHE=/root/.cache/huggingface/transformers

# Install PyTorch with CUDA support
RUN pip3 install --no-cache-dir torch==2.1.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cu121

# Install whisperx from GitHub to get the latest fixes
RUN pip3 install --no-cache-dir git+https://github.com/m-bain/whisperx.git

# Install other requirements
COPY requirements.txt .
RUN sed -i '/torch==/d' requirements.txt && \
    sed -i '/torchaudio==/d' requirements.txt && \
    sed -i '/whisperx==/d' requirements.txt && \
    pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories and set permissions
RUN mkdir -p /root/.cache/huggingface && \
    mkdir -p /root/.cache/torch/hub/checkpoints && \
    chmod -R 777 /root/.cache

# Preload VAD model for WhisperX
RUN python3 -c 'import whisperx; whisperx.load_model("large-v3", "cpu", compute_type="int8", download_root="/root/.cache/huggingface")'

CMD ["python3", "-m", "src.main"]