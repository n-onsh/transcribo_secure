FROM python:3.10-slim

WORKDIR /app

# Install build tools, dependencies, and netcat for wait-for-it.sh
RUN apt-get update && apt-get install -y \
    gcc \
    libmagic-dev \
    postgresql-client \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire backend directory (including wait-for-it.sh)
COPY . .

# Ensure the wait-for-it.sh script is executable
RUN chmod +x wait-for-it.sh

# Command: wait for the Postgres service then launch the API
CMD ["./wait-for-it.sh", "postgres:5432", "-t", "30", "--", "python", "-m", "src.main"]


