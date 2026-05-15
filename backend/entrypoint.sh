#!/bin/bash
set -e

DB_PATH="${DATABASE_URL#sqlite+aiosqlite:///}"
DB_PATH="${DB_PATH#./}"

if [ -f "$DB_PATH" ]; then
    BACKUP_PATH="${DB_PATH}.bak-$(date +%Y%m%d%H%M%S)"
    echo "Backing up database to $BACKUP_PATH..."
    cp "$DB_PATH" "$BACKUP_PATH" || echo "Warning: backup failed, continuing anyway"
fi

echo "Running migrations..."
if ! alembic upgrade head; then
    echo "ERROR: Migration failed. Manual intervention required."
    exit 1
fi

echo "Starting application..."
exec "$@"
