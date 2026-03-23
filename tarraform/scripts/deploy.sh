#!/bin/bash

echo "🚀 Pulling latest code..."
git pull origin main

echo "🐳 Building new container (green)..."
docker-compose build app_green

echo "▶ Starting green container..."
docker-compose up -d app_green

echo "🔄 Switching traffic to green..."
sed -i 's/app_blue/app_green/g' nginx.conf

docker exec nginx nginx -s reload

echo "🧹 Stopping blue container..."
docker stop app_blue

echo "🎉 Deploy complete (zero downtime)"