#!/bin/bash

echo "🚀 Pulling latest images..."
docker compose pull

echo "🛑 Stopping old containers..."
docker compose down

echo "🏁 Starting all containers..."
docker compose up -d

echo "⏳ Waiting for health check..."
until [ "$(docker inspect -f '{{.State.Health.Status}}' ride-bot)" == "healthy" ]; do
    printf '.'
    sleep 1
done

echo -e "\n✅ Update complete! All services are healthy."
