#!/bin/bash

echo "Creating Grab-like platform..."

PROJECT=grab-platform
mkdir -p $PROJECT
cd $PROJECT

mkdir gateway services infrastructure

services=(
auth-service
order-service
driver-service
dispatch-service
notification-service
)

for service in "${services[@]}"
do
 echo "Creating $service"
 mkdir -p services/$service

 docker run --rm \
  -v $(pwd)/services/$service:/app \
  composer create-project laravel/laravel .

 cd services/$service

 docker run --rm -v $(pwd):/app composer require laravel/octane predis/predis

 cd ../../
done

echo "Creating API Gateway"

mkdir -p gateway/api-gateway

cat > gateway/api-gateway/server.js <<EOF
const express = require('express')
const proxy = require('http-proxy-middleware')

const app = express()

app.use('/auth', proxy.createProxyMiddleware({target:'http://auth-service:8000'}))
app.use('/order', proxy.createProxyMiddleware({target:'http://order-service:8000'}))
app.use('/driver', proxy.createProxyMiddleware({target:'http://driver-service:8000'}))

app.listen(4000)
EOF

echo "Creating docker-compose"

cat > docker-compose.yml <<EOF
version: '3'

services:

 api-gateway:
  image: node:18
  working_dir: /app
  volumes:
   - ./gateway/api-gateway:/app
  command: node server.js
  ports:
   - "4000:4000"

 auth-service:
  build: ./services/auth-service
  command: php artisan octane:start --server=swoole --host=0.0.0.0 --port=8000

 order-service:
  build: ./services/order-service
  command: php artisan octane:start --server=swoole --host=0.0.0.0 --port=8000

 driver-service:
  build: ./services/driver-service
  command: php artisan octane:start --server=swoole --host=0.0.0.0 --port=8000

 dispatch-service:
  build: ./services/dispatch-service
  command: php artisan octane:start --server=swoole --host=0.0.0.0 --port=8000

 redis:
  image: redis:7

 mysql:
  image: mysql:8
  environment:
   MYSQL_ROOT_PASSWORD: root

 kafka:
  image: bitnami/kafka
EOF

echo "Platform created"