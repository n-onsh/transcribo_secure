#!/bin/sh

# Original version: https://github.com/vishnubob/wait-for-it/blob/master/wait-for-it.sh
# Usage: ./wait-for-it.sh host:port [-s] [-t timeout] [-- command args]

TIMEOUT=15
STRICT=0
while :; do
  case "$1" in
    *:* )
    HOST=$(printf "%s\n" "$1"| cut -d : -f 1)
    PORT=$(printf "%s\n" "$1"| cut -d : -f 2)
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

for i in `seq $TIMEOUT` ; do
  nc -z "$HOST" "$PORT" > /dev/null 2>&1
  result=$?
  if [ $result -eq 0 ] ; then
    if [ $# -gt 0 ] ; then
      exec "$@"
    fi
    exit 0
  fi
  sleep 1
done

echo "Timeout occurred after waiting $TIMEOUT seconds for $HOST:$PORT" >&2
exit 1