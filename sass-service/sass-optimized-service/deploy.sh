#!/bin/bash
docker compose up -d --build
echo "⏳ Waiting for DB..."
sleep 10
docker compose exec app php artisan key:generate
docker compose exec app php artisan migrate:fresh --force
docker compose exec app php artisan optimize
docker compose restart app
echo "✅ Architecture is LIVE"
