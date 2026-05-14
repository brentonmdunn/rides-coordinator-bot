#!/bin/bash
set -e

echo "Running migrations..."
if ! alembic upgrade head; then
    echo "ERROR: Migration failed. Manual intervention required."
    exit 1
fi

echo "Starting application..."
exec "$@"
