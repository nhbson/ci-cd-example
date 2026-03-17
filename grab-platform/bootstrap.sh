#!/bin/bash

set -e

PROJECT_NAME="laravel-octane-platform"

echo "Creating project structure..."

mkdir -p $PROJECT_NAME/docker/nginx
mkdir -p $PROJECT_NAME/docker/php
mkdir -p $PROJECT_NAME/src

cd $PROJECT_NAME

echo "Creating docker-compose.yml..."

cat <<'EOF' > docker-compose.yml
version: "3.9"

services:

  nginx:
    image: nginx:alpine
    container_name: nginx
    ports:
      - "80:80"
    volumes:
      - ./src:/var/www
      - ./docker/nginx/default.conf:/etc/nginx/conf.d/default.conf
    depends_on:
      - app

  app:
    build:
      context: ./docker/php
    container_name: laravel-app
    ports:
      - "8000:8000"
    volumes:
      - ./src:/var/www
    working_dir: /var/www
    entrypoint: /usr/local/bin/entrypoint.sh
    depends_on:
      - redis
      - mysql
    restart: unless-stopped

  queue:
    build:
      context: ./docker/php
    container_name: laravel-queue
    volumes:
      - ./src:/var/www
    working_dir: /var/www
    command: php artisan queue:work --tries=3
    depends_on:
      - redis
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: redis
    ports:
      - "6379:6379"

  mysql:
    image: mysql:8
    container_name: mysql
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

echo "Creating PHP Dockerfile..."

cat <<'EOF' > docker/php/Dockerfile
FROM php:8.4-cli-alpine

RUN apk add --no-cache \
    git \
    curl \
    unzip \
    pkgconfig \
    libzip-dev \
    libpng-dev \
    oniguruma-dev \
    brotli-dev \
    openssl-dev \
    linux-headers \
    autoconf \
    g++ \
    make

RUN docker-php-ext-install \
    pdo_mysql \
    mbstring \
    bcmath \
    pcntl \
    gd \
    zip

RUN pecl install redis && docker-php-ext-enable redis
RUN printf "\n" | pecl install swoole && docker-php-ext-enable swoole

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /var/www
EOF

echo "Creating entrypoint..."

cat <<'EOF' > docker/php/entrypoint.sh
#!/bin/sh

set -e

cd /var/www

php artisan config:clear || true
php artisan route:clear || true
php artisan cache:clear || true

exec php artisan octane:start \
  --server=swoole \
  --host=0.0.0.0 \
  --port=8000 \
  --workers=4 \
  --task-workers=2
EOF

chmod +x docker/php/entrypoint.sh

echo "Creating nginx config..."

cat <<'EOF' > docker/nginx/default.conf
server {
    listen 80;
    server_name localhost;

    root /var/www/public;
    index index.php index.html;

    location / {
        try_files $uri $uri/ @octane;
    }

    location @octane {

        proxy_pass http://app:8000;

        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header Scheme $scheme;
        proxy_set_header SERVER_PORT $server_port;
        proxy_set_header REMOTE_ADDR $remote_addr;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location ~* \.(jpg|jpeg|png|gif|css|js|ico|svg)$ {
        expires max;
        log_not_found off;
    }
}
EOF

echo "Preparing src..."

rm -rf src
mkdir src

echo "Installing Laravel..."

docker run --rm -v $(pwd)/src:/app -w /app composer:2 composer create-project laravel/laravel .

cd src

echo "Installing Laravel Octane..."

docker run --rm -v $(pwd):/app -w /app composer:2 composer require laravel/octane

echo "Installing Octane Swoole..."

docker run --rm -v $(pwd):/app -w /app php:8.4-cli sh -c "cd /app && php artisan octane:install --server=swoole"

echo "Fixing permissions..."

chmod -R 775 storage bootstrap/cache

echo ""
echo "Project ready!"
echo ""
echo "Run:"
echo "cd $PROJECT_NAME"
echo "docker compose up -d --build"
echo ""
echo "Open:"
echo "http://localhost"
echo "or"
echo "http://localhost:8000"