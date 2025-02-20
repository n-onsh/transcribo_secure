#!/bin/sh
# wait-for-it.sh: Wait until a TCP host and port become available

TIMEOUT=15
STRICT=0

# Parse command-line arguments
while :; do
  case "$1" in
    *:* )
      HOST=$(echo "$1" | cut -d: -f1)
      PORT=$(echo "$1" | cut -d: -f2)
      shift 1
      ;;
    -s)
      STRICT=1
      shift 1
      ;;
    -t)
      TIMEOUT="$2"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

# Wait for the host:port to become available
i=1
while [ $i -le $TIMEOUT ]; do
  if nc -z "$HOST" "$PORT"; then
    echo "$HOST:$PORT is available after $i seconds."
    if [ $# -gt 0 ]; then
      exec "$@"
    fi
    exit 0
  fi
  i=$((i + 1))
  sleep 1
done

echo "Timeout occurred after waiting $TIMEOUT seconds for $HOST:$PORT" >&2
exit 1
