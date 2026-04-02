#!/bin/bash

SERVICE_NAME="laravel_app"
MIN=2
MAX=5

# Get CPU usage
CPU=$(docker stats --no-stream --format "{{.CPUPerc}}" | sed 's/%//g' | awk '{sum+=$1} END {print sum/NR}')

# Get current replicas
CURRENT=$(docker service ls --format "{{.Name}} {{.Replicas}}" | grep $SERVICE_NAME | awk '{print $2}' | cut -d'/' -f1)

echo "CPU: $CPU | Replicas: $CURRENT"

if (( $(echo "$CPU > 70" | bc -l) )); then
  if [ "$CURRENT" -lt "$MAX" ]; then
    NEW=$((CURRENT + 1))
    echo "Scaling UP → $NEW"
    docker service scale $SERVICE_NAME=$NEW
  fi
fi

if (( $(echo "$CPU < 30" | bc -l) )); then
  if [ "$CURRENT" -gt "$MIN" ]; then
    NEW=$((CURRENT - 1))
    echo "Scaling DOWN → $NEW"
    docker service scale $SERVICE_NAME=$NEW
  fi
fi