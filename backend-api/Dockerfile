# backend-api/Dockerfile
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libmagic-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x wait-for-it.sh

CMD ["./wait-for-it.sh", "postgres", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]