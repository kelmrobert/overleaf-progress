#!/bin/bash

# Zero-downtime deployment script for Zinnbot
set -e

echo "🚀 Starting production deployment..."

# Pull latest changes
git pull origin main

echo "📦 Building new production images..."
# Build with --no-cache to ensure latest code
docker compose -f docker-compose.yml build --no-cache

echo "🔄 Rolling update..."
# Use --force-recreate to ensure containers use new images
# --no-deps prevents recreating dependencies
docker compose -f docker-compose.yml up --force-recreate --no-deps -d

echo "🧹 Cleaning up old images..."
docker image prune -f

echo "✅ Production deployment complete!"

# Show running containers
docker compose -f docker-compose.yml ps