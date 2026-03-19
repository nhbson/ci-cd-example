#!/bin/bash

echo "🛑 Stopping..."

docker compose down
sudo tc qdisc del dev lo root 2>/dev/null

echo "✅ Cleaned"