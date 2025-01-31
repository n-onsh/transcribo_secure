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

# Modify the wait-for-it script to properly wait for PostgreSQL
COPY <<'EOF' /app/wait-for-it.sh
#!/bin/bash
set -e

host="$1"
shift
cmd="$@"

until PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\q'; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

>&2 echo "Postgres is up - executing command"
exec uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
EOF

RUN chmod +x /app/wait-for-it.sh

CMD ["/app/wait-for-it.sh", "postgres"]