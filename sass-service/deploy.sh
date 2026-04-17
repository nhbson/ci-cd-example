#!/bin/bash

set -e

echo "🚀 Deploying Webhook System..."

docker build -t webhook-app .

docker stack deploy -c docker-compose.yml webhook

echo "✅ Deployment complete"