#!/bin/bash

set -e

PROJECT_NAME="laravel-starter-kit"

# -----------------------------
# 🧠 Detect & fix WSL path
# -----------------------------
WORKDIR=$(pwd)

if [[ "$WORKDIR" == /mnt/* ]]; then
  echo "⚠️ Running inside /mnt (Windows FS)... applying compatibility fix"

  # Convert to proper mount path
  WORKDIR=$(wslpath -u "$(wslpath -w "$PWD")")
fi

# -----------------------------
# 🧹 Clean old project
# -----------------------------
if [ -d "$PROJECT_NAME" ]; then
  echo "⚠️ Existing project found. Removing..."
  rm -rf $PROJECT_NAME
fi

echo "🚀 Creating project structure..."

mkdir -p $PROJECT_NAME/docker/nginx
mkdir -p $PROJECT_NAME/docker/php
mkdir -p $PROJECT_NAME/src

cd $PROJECT_NAME

# -----------------------------
# 🐳 docker-compose.yml
# -----------------------------
cat <<EOL > docker-compose.yml
version: "3.9"

services:

  nginx:
    image: nginx:latest
    ports:
      - "80:80"
    volumes:
      - ./src:/var/www/html
      - ./docker/nginx/default.conf:/etc/nginx/conf.d/default.conf
    depends_on:
      - app

  app:
    build:
      context: .
      dockerfile: docker/php/Dockerfile
    volumes:
      - ./src:/var/www/html
    working_dir: /var/www/html
    command: php artisan octane:start --server=swoole --host=0.0.0.0 --port=8000
    depends_on:
      - redis

  redis:
    image: redis:7-alpine

  worker:
    build:
      context: .
      dockerfile: docker/php/Dockerfile
    volumes:
      - ./src:/var/www/html
    working_dir: /var/www/html
    command: php artisan queue:work
    depends_on:
      - redis
EOL

# -----------------------------
# 🐘 PHP Dockerfile
# -----------------------------
cat <<EOL > docker/php/Dockerfile
FROM php:8.3-cli

RUN apt-get update && apt-get install -y \
    git curl zip unzip libpq-dev \
    && docker-php-ext-install pdo pdo_pgsql

COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

RUN pecl install swoole && docker-php-ext-enable swoole

WORKDIR /var/www/html
EOL

# -----------------------------
# 🌐 Nginx config
# -----------------------------
cat <<EOL > docker/nginx/default.conf
server {
    listen 80;

    location / {
        proxy_pass http://app:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOL

# -----------------------------
# 📦 Laravel install
# -----------------------------
echo "📦 Installing Laravel..."

cd src

docker run --rm \
  -v "$WORKDIR/$PROJECT_NAME/src":/app \
  -w /app \
  composer create-project laravel/laravel .

echo "⚡ Installing packages..."

docker run --rm \
  -v "$WORKDIR/$PROJECT_NAME/src":/app \
  -w /app \
  composer require laravel/octane predis/predis -W

echo "⚙️ Installing Octane..."

docker run --rm \
  -v "$WORKDIR/$PROJECT_NAME/src":/app \
  -w /app \
  php:8.3-cli bash -c "
apt-get update && apt-get install -y git unzip libpq-dev && \
docker-php-ext-install pdo pdo_pgsql && \
curl -sS https://getcomposer.org/installer | php && \
php composer.phar install && \
php artisan octane:install --server=swoole
"

# -----------------------------
# 🔐 .env
# -----------------------------
cat <<EOL > .env
APP_NAME=CRM
APP_ENV=local
APP_KEY=
APP_DEBUG=true
APP_URL=http://localhost

DB_CONNECTION=pgsql
DB_HOST=aws-1-ap-northeast-1.pooler.supabase.com
DB_PORT=6543
DB_DATABASE=postgres
DB_USERNAME=postgres.hobhaeieerlfgtugylcv
DB_PASSWORD=Kn3in1@5675
DB_SSLMODE=require

CACHE_DRIVER=redis
QUEUE_CONNECTION=redis
REDIS_HOST=redis
REDIS_PORT=6379
EOL

cd ..

# -----------------------------
# 🐳 Run Docker
# -----------------------------
echo "🐳 Starting containers..."

docker compose up -d --build

sleep 10

APP_CONTAINER=$(docker ps --format '{{.Names}}' | grep app | head -n 1)

echo "🔑 Finalizing Laravel..."

docker exec $APP_CONTAINER php artisan key:generate
docker exec $APP_CONTAINER php artisan migrate

echo ""
echo "✅ DONE!"
echo "🌍 http://localhost"
echo ""
docker ps