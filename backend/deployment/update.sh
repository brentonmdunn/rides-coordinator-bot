#!/bin/bash

echo "🚀 Pulling latest image..."
# Pulling first ensures the 'downtime' doesn't include download time
docker compose pull ride-bot

echo "🛑 Stopping old container..."
# Stop the old one to release the Discord Gateway connection and DB locks
docker compose stop ride-bot

echo "🏁 Starting new container..."
docker compose up -d ride-bot

echo "⏳ Waiting for health check..."
# This loops until the /health endpoint returns 200 OK
until [ "$(docker inspect -f '{{.State.Health.Status}}' ride-bot)" == "healthy" ]; do
    printf '.'
    sleep 1
done

echo -e "\n✅ Update complete! Bot is healthy."
