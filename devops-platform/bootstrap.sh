#!/bin/bash

echo "====================================="
echo "DevOps Platform Auto Installer"
echo "====================================="

echo "Updating server..."
sudo apt update -y

echo "Installing Docker..."
sudo apt install -y docker.io

sudo systemctl start docker
sudo systemctl enable docker

echo "Installing Docker Compose..."
sudo apt install -y docker-compose

echo "Creating project folder..."
mkdir devops-platform
cd devops-platform

echo "Creating folders..."
mkdir jenkins
mkdir nginx
mkdir app
mkdir src

###################################
# docker-compose.yml
###################################

cat <<EOF > docker-compose.yml
version: "3.8"

services:

  jenkins:
    build: ./jenkins
    container_name: jenkins
    ports:
      - "8080:8080"
      - "50000:50000"
    volumes:
      - jenkins_home:/var/jenkins_home
      - /var/run/docker.sock:/var/run/docker.sock
    restart: always

  nginx:
    image: nginx:latest
    container_name: nginx
    ports:
      - "80:80"
    volumes:
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf
      - ./src:/var/www
    depends_on:
      - app

  app:
    build: ./app
    container_name: laravel_app
    volumes:
      - ./src:/var/www
    restart: always

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
  jenkins_home:
  mysql_data:
EOF

###################################
# Jenkins Dockerfile
###################################

cat <<EOF > jenkins/Dockerfile
FROM jenkins/jenkins:lts

USER root

RUN apt-get update && \
    apt-get install -y docker.io

RUN usermod -aG docker jenkins

USER jenkins
EOF

###################################
# Laravel Dockerfile
###################################

cat <<EOF > app/Dockerfile
FROM php:8.2-fpm

WORKDIR /var/www

RUN apt-get update && \
    apt-get install -y \
    git \
    curl \
    zip \
    unzip \
    libzip-dev

RUN docker-php-ext-install pdo pdo_mysql zip

COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

CMD ["php-fpm"]
EOF

###################################
# Nginx config
###################################

cat <<EOF > nginx/default.conf
server {

    listen 80;

    root /var/www/public;
    index index.php index.html;

    location / {
        try_files \$uri \$uri/ /index.php?\$query_string;
    }

    location ~ \.php$ {
        fastcgi_pass laravel_app:9000;
        fastcgi_index index.php;
        include fastcgi_params;
        fastcgi_param SCRIPT_FILENAME \$document_root\$fastcgi_script_name;
    }

}
EOF

echo "Starting containers..."

sudo docker compose up -d --build

echo ""
echo "====================================="
echo "INSTALLATION COMPLETE"
echo "====================================="
echo ""
echo "Open Jenkins:"
echo ""
echo "http://YOUR_SERVER_IP:8080"
echo ""

echo "Jenkins first password:"
sudo docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword