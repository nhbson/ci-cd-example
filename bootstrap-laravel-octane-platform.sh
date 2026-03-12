#!/bin/bash

PROJECT_NAME="laravel-octane-platform"

echo "Creating project structure..."

mkdir -p $PROJECT_NAME/docker/nginx
mkdir -p $PROJECT_NAME/docker/php
mkdir -p $PROJECT_NAME/src

cd $PROJECT_NAME

echo "Creating docker-compose.yml..."

cat <<EOF > docker-compose.yml
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
volumes:
- ./src:/var/www
depends_on:
- redis
- mysql
command: php artisan octane:start --server=swoole --host=0.0.0.0 --port=8000

queue:
build:
context: ./docker/php
container_name: laravel-queue
volumes:
- ./src:/var/www
command: php artisan queue:work --tries=3
depends_on:
- redis

redis:
image: redis:7
container_name: redis
ports:
- "6379:6379"

mysql:
image: mysql:8
container_name: mysql
environment:
MYSQL_ROOT_PASSWORD: root
MYSQL_DATABASE: laravel
ports:
- "3306:3306"
volumes:
- mysql_data:/var/lib/mysql

volumes:
mysql_data:
EOF

echo "Creating PHP Dockerfile..."

cat <<EOF > docker/php/Dockerfile
FROM php:8.2-cli

RUN apt-get update && apt-get install -y 
git 
curl 
unzip 
libzip-dev 
libpng-dev 
libonig-dev 
&& docker-php-ext-install pdo_mysql mbstring bcmath pcntl gd zip

RUN pecl install redis 
&& docker-php-ext-enable redis

RUN pecl install swoole 
&& docker-php-ext-enable swoole

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

WORKDIR /var/www
EOF

echo "Creating nginx config..."

cat <<EOF > docker/nginx/default.conf
server {
listen 80;
server_name localhost;

```
root /var/www/public;
index index.php index.html;

location / {
    try_files \$uri \$uri/ @octane;
}

location @octane {
    proxy_pass http://app:8000;
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header Scheme \$scheme;
}

location ~* \.(jpg|jpeg|png|gif|css|js|ico|svg)\$ {
    expires max;
    log_not_found off;
}
```

}
EOF

echo "Installing Laravel..."

docker run --rm -v $(pwd)/src:/app composer create-project laravel/laravel .

cd src

echo "Installing Laravel Octane..."

docker run --rm -v $(pwd):/app -w /app composer require laravel/octane

docker run --rm -v $(pwd):/app -w /app php:8.2-cli php artisan octane:install --server=swoole

echo "Project ready!"

echo ""
echo "Run the system:"
echo "cd $PROJECT_NAME"
echo "docker compose up -d --build"
echo ""
echo "Open browser:"
echo "http://localhost"
