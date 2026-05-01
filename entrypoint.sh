#!/bin/sh
set -e

echo "Running database migrations..."
flask db upgrade

echo "Starting Gunicorn..."
exec gunicorn \
  --bind 0.0.0.0:5000 \
  --workers "${GUNICORN_WORKERS:-1}" \
  --timeout 120 \
  --access-logfile - \
  run:app
