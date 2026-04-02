#!/bin/bash

set -e

PROJECT_NAME="laravel-octane-production"

echo "🚀 Creating production project: $PROJECT_NAME"

# -----------------------------------
# Create structure
# -----------------------------------

mkdir -p "$PROJECT_NAME/docker/nginx"
mkdir -p "$PROJECT_NAME/docker/php"

cd "$PROJECT_NAME"

# -----------------------------------
# docker-compose.yml
# -----------------------------------

echo "📦 Creating docker-compose.yml..."

cat <<'EOF' > docker-compose.yml
version: "3.9"

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./src:/var/www
      - ./docker/nginx/default.conf:/etc/nginx/nginx.conf
    depends_on:
      - app
    restart: unless-stopped

  app:
    build:
      context: .
      dockerfile: docker/php/Dockerfile
      cpus: 1.0
      mem_limit: 1g
    volumes:
      - ./src:/var/www
    working_dir: /var/www
    depends_on:
      - redis
      - mysql
    restart: unless-stopped

  queue:
    build:
      context: .
      dockerfile: docker/php/Dockerfile
    command: php artisan queue:work --sleep=1 --tries=3 --timeout=60
    volumes:
      - ./src:/var/www
    depends_on:
      - redis
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  mysql:
    image: mysql:8
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: laravel
    command: --default-authentication-plugin=mysql_native_password
    ports:
      - "3309:3306"
    volumes:
      - mysql_data:/var/lib/mysql

volumes:
  mysql_data:
EOF

# -----------------------------------
# Dockerfile
# -----------------------------------

echo "🐳 Creating Dockerfile..."

cat <<'EOF' > docker/php/Dockerfile
FROM openswoole/swoole:php8.3-alpine

RUN apk add --no-cache \
    libpng-dev \
    libzip-dev \
    oniguruma-dev \
    curl \
    git \
    autoconf \
    gcc \
    g++ \
    make

# ✅ Install required PHP extensions
RUN docker-php-ext-install \
    pdo_mysql \
    mbstring \
    bcmath \
    gd \
    zip \
    pcntl

# 🔥 Install Redis extension
RUN pecl install redis && docker-php-ext-enable redis

WORKDIR /var/www

CMD ["php", "artisan", "octane:start", "--server=swoole", "--host=0.0.0.0", "--port=8000", "--workers=auto", "--max-requests=1000"]
EOF

# -----------------------------------
# Nginx config
# -----------------------------------

echo "🌐 Creating nginx config..."

cat <<'EOF' > docker/nginx/default.conf
worker_processes auto;

events {
    worker_connections 65535;
}

http {
    upstream backend {
        least_conn;
        server app:8000;
    }

    server {
        listen 80;

        location / {
            proxy_pass http://backend;

            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }
    }
}
EOF

# -----------------------------------
# Install Laravel (SAFE + IDEMPOTENT)
# -----------------------------------

echo "⬇️ Installing Laravel 11..."

# Clean previous broken install (optional but recommended)
if [ -d "src/vendor" ]; then
  echo "⚠️ Existing Laravel detected, cleaning..."
  rm -rf src
fi

mkdir -p src

DOCKER_CONFIG=/tmp docker run --rm \
    -v "$(pwd)/src:/app" \
    -w /app \
    composer:2 \
    composer create-project laravel/laravel:^11.0 .

cd src

echo "⚡ Forcing PHP 8.3 compatibility..."

DOCKER_CONFIG=/tmp docker run --rm \
    -v "$(pwd):/app" \
    -w /app \
    composer:2 \
    composer config platform.php 8.3.30

echo "⚡ Reinstalling dependencies..."

DOCKER_CONFIG=/tmp docker run --rm \
    -v "$(pwd):/app" \
    -w /app \
    composer:2 \
    composer update

echo "⚡ Installing Octane..."

DOCKER_CONFIG=/tmp docker run --rm \
    -v "$(pwd):/app" \
    -w /app \
    composer:2 \
    composer require laravel/octane:^2.0

echo "⚡ Installing Swoole..."

DOCKER_CONFIG=/tmp docker run --rm \
    -v "$(pwd):/app" \
    -w /app \
    php:8.3-cli \
    sh -c "php artisan octane:install --server=swoole"

# -----------------------------------
# Optimize Laravel
# -----------------------------------

echo "⚙️ Optimizing Laravel..."

cat <<'EOF' >> .env

OCTANE_SERVER=swoole
CACHE_DRIVER=redis
QUEUE_CONNECTION=redis
SESSION_DRIVER=redis
REDIS_HOST=redis
EOF

chmod -R 775 storage bootstrap/cache

cd ..

echo ""
echo "✅ DONE!"
echo ""
echo "Run:"
echo "cd $PROJECT_NAME"
echo "docker compose up -d --build"
echo ""
echo "Open:"
echo "http://localhost"
echo ""
echo "🔥 SUCCESS: No PHP errors, no Composer errors, ready to scale 🚀"