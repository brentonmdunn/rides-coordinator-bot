#!/bin/bash
set -euo pipefail

SERVICE="ride-bot"
IMAGE="brentonmdunn/ride-bot"
HEALTH_TIMEOUT=30
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OVERRIDE_FILE="${SCRIPT_DIR}/.rollback-override.yml"

cleanup() {
    rm -f "$OVERRIDE_FILE"
}
trap cleanup EXIT

rollback() {
    echo ""
    echo "❌ Health check did not pass within ${HEALTH_TIMEOUT}s."

    if [ -z "${ROLLBACK_IMAGE:-}" ]; then
        echo "   No rollback snapshot available — leaving new container running."
        exit 1
    fi

    echo "⏪ Rolling back to previous image..."
    docker compose stop "$SERVICE"

    cat > "$OVERRIDE_FILE" << EOF
services:
  ${SERVICE}:
    image: ${IMAGE}:rollback
EOF
    docker compose -f docker-compose.yml -f "$OVERRIDE_FILE" up -d "$SERVICE"

    echo "✅ Rollback complete. Verify the container is healthy."
    exit 1
}

echo "💾 Snapshotting current image for rollback..."
# Pulling first ensures the 'downtime' doesn't include download time
ROLLBACK_IMAGE=$(docker inspect "$SERVICE" --format '{{.Image}}' 2>/dev/null || echo "")
if [ -n "$ROLLBACK_IMAGE" ]; then
    docker tag "$ROLLBACK_IMAGE" "${IMAGE}:rollback"
    echo "   Saved as ${IMAGE}:rollback"
else
    echo "   No running container found — skipping rollback snapshot."
fi

echo "🚀 Pulling latest image..."
docker compose pull "$SERVICE"

echo "🛑 Stopping old container..."
# Stop the old one to release the Discord Gateway connection and DB locks
docker compose stop "$SERVICE"

echo "🏁 Starting new container..."
docker compose up -d "$SERVICE"

echo "⏳ Waiting up to ${HEALTH_TIMEOUT}s for health check..."
ELAPSED=0
until [ "$(docker inspect -f '{{.State.Health.Status}}' "$SERVICE" 2>/dev/null)" == "healthy" ]; do
    if [ "$ELAPSED" -ge "$HEALTH_TIMEOUT" ]; then
        rollback
    fi
    printf '.'
    sleep 1
    ELAPSED=$((ELAPSED + 1))
done

echo -e "\n✅ Update complete! Bot is healthy."
