#!/bin/bash
# Stop and remove containers
docker-compose down

# Remove the old image to force rebuild
docker rmi teams-notion-api-dev-app 2>/dev/null || true
docker rmi $(docker images -q teams-notion-api-dev-app) 2>/dev/null || true

# Rebuild without cache
docker-compose build --no-cache

# Start the container
docker-compose up -d

# Show logs
docker-compose logs -f
