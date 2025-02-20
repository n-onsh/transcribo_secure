FROM python:3.10-slim

WORKDIR /app

# Install build tools, dependencies, and netcat for wait-for-it.sh
RUN apt-get update -qq && apt-get install -y -qq \
    gcc \
    libmagic-dev \
    postgresql-client \
    netcat-openbsd \
    > /dev/null 2>&1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --quiet

# Copy the entire backend directory (including wait-for-it.sh)
COPY . .

# Ensure the wait-for-it.sh script is executable
RUN chmod +x wait-for-it.sh

# Command: wait for the Postgres service then launch the API
CMD ["./wait-for-it.sh", "-t", "30", "postgres:5432", "--", "python", "-m", "src.main"]
