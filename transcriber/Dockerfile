FROM python:3.10-slim

RUN apt-get update -qq && \
    apt-get install -y -qq ffmpeg > /dev/null 2>&1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --quiet

COPY . .

ENV PYTHONPATH=/app
ENV HF_HUB_ENABLE_HF_TRANSFER=1

# Fail if HF_AUTH_TOKEN is not provided
ARG HF_AUTH_TOKEN
ENV HF_AUTH_TOKEN=${HF_AUTH_TOKEN}
RUN if [ -z "$HF_AUTH_TOKEN" ]; then echo "HF_AUTH_TOKEN must be provided" && exit 1; fi

CMD ["python3", "-m", "src.main"]
