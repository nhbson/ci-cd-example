#!/usr/bin/env bash
set -e

PROJECT=platform

echo "Creating $PROJECT..."
mkdir -p $PROJECT
cd $PROJECT

# ---- base folders ----
mkdir -p docker/nginx
mkdir -p docker/php
mkdir -p docker/supervisor
mkdir -p .github/workflows

echo "Creating Laravel project..."
docker run --rm -u $(id -u):$(id -g) \
 -v $(pwd):/app -w /app \
 composer create-project laravel/laravel app

cd app

echo "Installing Octane + Horizon..."
docker run --rm -u $(id -u):$(id -g) \
 -v $(pwd):/app -w /app \
 composer require laravel/octane laravel/horizon predis/predis

docker run --rm -u $(id -u):$(id -g) \
 -v $(pwd):/app -w /app \
 php:8.2-cli php artisan octane:install --server=swoole

cd ..

# ---- Dockerfile ----
cat > docker/php/Dockerfile <<'EOF'
FROM php:8.2-cli

RUN apt-get update && apt-get install -y \
    git curl zip unzip libpng-dev libzip-dev \
    && docker-php-ext-install pdo_mysql bcmath pcntl

RUN pecl install redis swoole \
    && docker-php-ext-enable redis swoole

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

WORKDIR /var/www
EOF

# ---- Nginx config ----
cat > docker/nginx/default.conf <<'EOF'
server {
    listen 80;

    root /var/www/public;
    index index.php;

    location / {
        proxy_pass http://app:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

# ---- docker-compose ----
cat > docker-compose.yml <<'EOF'
version: "3.9"

services:

  nginx:
    image: nginx:latest
    ports:
      - "8080:80"
    volumes:
      - ./app:/var/www
      - ./docker/nginx/default.conf:/etc/nginx/conf.d/default.conf
    depends_on:
      - app

  app:
    build: ./docker/php
    working_dir: /var/www
    volumes:
      - ./app:/var/www
    command: php artisan octane:start --server=swoole --host=0.0.0.0 --port=8000
    depends_on:
      - mysql
      - redis

  queue:
    build: ./docker/php
    working_dir: /var/www
    volumes:
      - ./app:/var/www
    command: php artisan horizon
    depends_on:
      - redis

  scheduler:
    build: ./docker/php
    working_dir: /var/www
    volumes:
      - ./app:/var/www
    command: sh -c "while true; do php artisan schedule:run; sleep 60; done"

  redis:
    image: redis:7

  mysql:
    image: mysql:8
    environment:
      MYSQL_DATABASE: laravel
      MYSQL_ROOT_PASSWORD: root
    ports:
      - "3306:3306"
    volumes:
      - dbdata:/var/lib/mysql

volumes:
  dbdata:
EOF

# ---- Makefile ----
cat > Makefile <<'EOF'
start:
	docker compose up -d --build

stop:
	docker compose down

logs:
	docker compose logs -f

shell:
	docker compose exec app bash

migrate:
	docker compose exec app php artisan migrate
EOF

# ---- CI pipeline example ----
cat > .github/workflows/ci.yml <<'EOF'
name: CI

on:
 push:
   branches: [main]

jobs:
 build:
   runs-on: ubuntu-latest

   steps:
    - uses: actions/checkout@v3

    - name: Install PHP
      uses: shivammathur/setup-php@v2
      with:
        php-version: 8.2

    - name: Install dependencies
      run: composer install

    - name: Run tests
      run: php artisan test
EOF

echo "Platform ready!"
echo "Run:"
echo "cd $PROJECT"
echo "make start"