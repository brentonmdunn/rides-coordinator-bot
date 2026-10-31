#!/bin/bash
set -euo pipefail

SERVICE="ride-bot"
IMAGE="brentonmdunn/ride-bot"
HEALTH_TIMEOUT=120
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OVERRIDE_FILE="${SCRIPT_DIR}/.rollback-override.yml"
cd "$SCRIPT_DIR"

# Keep updates and rollback on the same configuration and volume paths.
COMPOSE=(docker compose)
if [ -f .doppler-token ]; then
    if [ ! -s .doppler-token ]; then
        echo "ERROR: .doppler-token is empty; refusing to update."
        exit 1
    fi
    if [ ! -f docker-compose.doppler.yaml ]; then
        echo "ERROR: Copy docker-compose.doppler.yaml here before updating."
        exit 1
    fi
    COMPOSE+=(-f docker-compose.doppler.yaml)
    echo "Using Doppler secrets from .doppler-token."
else
    # Resolve the base file explicitly so rollback uses the same file.
    for candidate in compose.yaml compose.yml docker-compose.yaml docker-compose.yml; do
        if [ -f "$candidate" ]; then
            COMPOSE+=(-f "$candidate")
            break
        fi
    done
fi
"${COMPOSE[@]}" config --quiet

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
    "${COMPOSE[@]}" stop "$SERVICE"

    cat > "$OVERRIDE_FILE" << EOF
services:
  ${SERVICE}:
    image: ${IMAGE}:rollback
EOF
    "${COMPOSE[@]}" -f "$OVERRIDE_FILE" up -d --pull never "$SERVICE"

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
"${COMPOSE[@]}" pull "$SERVICE"

echo "🛑 Stopping old container..."
# Stop the old one to release the Discord Gateway connection and DB locks
"${COMPOSE[@]}" stop "$SERVICE"

echo "🏁 Starting new container..."
"${COMPOSE[@]}" up -d "$SERVICE"

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
