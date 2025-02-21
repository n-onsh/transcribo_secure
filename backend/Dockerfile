FROM python:3.10-slim

WORKDIR /app

# Install build tools and dependencies
RUN apt-get update -qq && apt-get install -y -qq \
    gcc \
    libmagic-dev \
    postgresql-client \
    curl \
    libffi-dev \
    > /dev/null 2>&1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -v

# Copy the entire backend directory
COPY . .

# Create logs directory and ensure proper permissions
RUN mkdir -p logs && chmod 777 logs

# Command to launch the API with debug flags
CMD ["python", "-X", "dev", "-X", "faulthandler", "-v", "-m", "src.main"]
