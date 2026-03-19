#!/bin/bash

set -e

echo "🚀 Starting full setup..."

# 1. Create Laravel if not exists
if [ ! -f "www/artisan" ]; then
  echo "📦 Creating Laravel project..."
  mkdir -p www
  composer create-project laravel/laravel www
fi

cd www

# 2. Install dependencies
echo "📦 Installing dependencies..."
composer install

# 3. Install Octane
if ! php artisan | grep -q octane; then
  echo "⚡ Installing Octane..."
  composer require laravel/octane
  php artisan octane:install --server=swoole
fi

# 4. Install WebSocket (Pusher)
if ! grep -q pusher composer.json; then
  echo "📡 Installing WebSocket..."
  composer require pusher/pusher-php-server
fi

# 5. Setup .env
if [ ! -f ".env" ]; then
  cp .env.example .env
fi

php artisan key:generate

# 6. Set env for WebSocket + Redis
sed -i 's/BROADCAST_DRIVER=.*/BROADCAST_DRIVER=pusher/' .env || true
echo "PUSHER_APP_ID=app-id" >> .env
echo "PUSHER_APP_KEY=app-key" >> .env
echo "PUSHER_APP_SECRET=app-secret" >> .env
echo "PUSHER_HOST=soketi" >> .env
echo "PUSHER_PORT=6001" >> .env
echo "PUSHER_SCHEME=http" >> .env

cd ..

# 7. Build & run Docker
echo "🐳 Building Docker..."
docker compose down -v
docker compose up -d --build

echo "✅ DONE!"
echo "👉 Open: http://localhost:8000"