#!/bin/bash

echo "📈 Scaling app instances..."

docker compose up -d --scale app1=3 --scale app2=3

echo "✅ Scaled to 6 instances"