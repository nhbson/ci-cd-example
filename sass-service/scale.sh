#!/bin/bash

SERVICE=$1
COUNT=$2

if [ -z "$SERVICE" ] || [ -z "$COUNT" ]; then
  echo "Usage: ./scale.sh [service] [count]"
  exit 1
fi

docker compose -f docker-stack.yml up -d --scale $SERVICE=$COUNT

echo "📈 Scaled $SERVICE to $COUNT"