#!/bin/bash

set -e

PROJECT_NAME="sass-optimized-service"

echo "🚀 Initializing High-Performance Architecture: $PROJECT_NAME"

# Check if running on Windows partition (WSL2 specific optimization)
if [[ $(pwd) == /mnt/* ]]; then
    echo "⚠️  WARNING: You are running on a Windows partition (/mnt/c/)."
    echo "Filesystem performance will be 10x slower. For 10,000 RPS, move this folder to ~/ (Linux Home)."
fi

mkdir -p $PROJECT_NAME
cd $PROJECT_NAME

# 📁 Folder Structure
mkdir -p docker/nginx docker/php docker/supervisor src

# -----------------------------
# 🧠 1. Nginx Config (High Concurrency Tuning)
# -----------------------------
cat <<EOL > docker/nginx/nginx.conf
worker_processes auto;
worker_rlimit_nofile 200000;

events {
    worker_connections 10240;
    multi_accept on;
    use epoll;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    keepalive_requests 100000;
    reset_timedout_connection on;

    gzip on;
    gzip_comp_level 4;
    gzip_types text/plain text/css application/json application/javascript;

    # Protecs Swoole workers from slow clients/network
    proxy_buffering on;
    proxy_buffer_size 128k;
    proxy_buffers 4 256k;
    proxy_busy_buffers_size 256k;

    upstream octane_backend {
        least_conn;
        server app:8000;
        keepalive 128;
    }

    server {
        listen 80 reuseport backlog=65535;
        server_name _;
        root /var/www/public;

        location / {
            proxy_pass http://octane_backend;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            
            proxy_connect_timeout 5s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }
    }
}
EOL

# -----------------------------
# 🧠 2. Dockerfile (Fixed pgrep, Swoole, Igbinary, JIT)
# -----------------------------
cat <<EOL > docker/php/Dockerfile
FROM php:8.3-cli-bookworm

WORKDIR /var/www

# Install system dependencies + procps (for pgrep) + build tools
RUN apt-get update && apt-get install -y \\
    git curl zip unzip libzip-dev libonig-dev \\
    libpng-dev libxml2-dev libssl-dev supervisor \\
    libbrotli-dev libc-ares-dev libcurl4-openssl-dev \\
    procps \\
    && rm -rf /var/lib/apt/lists/*

# Install standard extensions
RUN docker-php-ext-install pdo_mysql mbstring zip pcntl bcmath gd

# High-Performance Serialization & Redis
RUN pecl install igbinary && docker-php-ext-enable igbinary
RUN pecl install --configureoptions 'enable-redis-igbinary="yes"' redis && docker-php-ext-enable redis

# Build Swoole with Brotli and OpenSSL support
RUN pecl install --configureoptions 'enable-sockets="no" enable-openssl="yes" enable-http2="yes" enable-mysqlnd="yes" enable-swoole-curl="yes" enable-cares="yes" enable-brotli="yes"' swoole-5.1.3 \\
    && docker-php-ext-enable swoole

# Enable JIT Compiler (Huge CPU reduction)
RUN echo "opcache.enable=1" >> /usr/local/etc/php/conf.d/opcache.ini \\
    && echo "opcache.enable_cli=1" >> /usr/local/etc/php/conf.d/opcache.ini \\
    && echo "opcache.memory_consumption=512" >> /usr/local/etc/php/conf.d/opcache.ini \\
    && echo "opcache.interned_strings_buffer=64" >> /usr/local/etc/php/conf.d/opcache.ini \\
    && echo "opcache.max_accelerated_files=32531" >> /usr/local/etc/php/conf.d/opcache.ini \\
    && echo "opcache.validate_timestamps=0" >> /usr/local/etc/php/conf.d/opcache.ini \\
    && echo "opcache.jit_buffer_size=100M" >> /usr/local/etc/php/conf.d/opcache.ini \\
    && echo "opcache.jit=1255" >> /usr/local/etc/php/conf.d/opcache.ini

COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

EXPOSE 8000
EOL

# -----------------------------
# 🧠 3. Supervisor (Fixed Section Error)
# -----------------------------
cat <<EOL > docker/supervisor/worker.conf
[supervisord]
logfile=/dev/null
logfile_maxbytes=0
pidfile=/var/run/supervisord.pid
nodaemon=true
user=root

[program:laravel-worker]
process_name=%(program_name)s_%(process_num)02d
command=php /var/www/artisan queue:work redis --sleep=1 --tries=3 --timeout=90
autostart=true
autorestart=true
numprocs=10
user=root
redirect_stderr=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
EOL

# -----------------------------
# 🧠 4. Docker Compose (Unified Scaling)
# -----------------------------
cat <<EOL > docker-compose.yml
services:
  nginx:
    image: nginx:latest
    ports: ["80:80"]
    volumes: ["./docker/nginx/nginx.conf:/etc/nginx/nginx.conf:ro"]
    depends_on: [app]
    networks: [sass-network]

  app:
    build: { context: ., dockerfile: docker/php/Dockerfile }
    volumes: ["./src:/var/www"]
    env_file: .env
    # Aggressive worker count for high RPS
    command: php artisan octane:start --server=swoole --host=0.0.0.0 --port=8000 --workers=64 --task-workers=16 --max-requests=10000
    deploy:
      resources:
        limits: { cpus: '6.0', memory: 8G }
    networks: [sass-network]

  worker:
    build: { context: ., dockerfile: docker/php/Dockerfile }
    volumes: ["./src:/var/www", "./docker/supervisor/worker.conf:/etc/supervisor/conf.d/worker.conf:ro"]
    env_file: .env
    command: /usr/bin/supervisord -n -c /etc/supervisor/conf.d/worker.conf
    networks: [sass-network]

  redis:
    image: redis:7-alpine
    command: redis-server --save "" --appendonly no
    networks: [sass-network]

  mysql:
    image: mysql:8.4
    environment: { MYSQL_ROOT_PASSWORD: root, MYSQL_DATABASE: app }
    command: >
      --innodb-buffer-pool-size=2G
      --innodb-flush-log-at-trx-commit=2
      --max-connections=1000
    volumes: ["mysql_data:/var/lib/mysql"]
    networks: [sass-network]

networks: { sass-network: { driver: bridge } }
volumes: { mysql_data: }
EOL

# -----------------------------
# 🧠 5. Helper Scripts
# -----------------------------
cat <<EOL > deploy.sh
#!/bin/bash
docker compose up -d --build
echo "⏳ Waiting for DB..."
sleep 10
docker compose exec app php artisan key:generate
docker compose exec app php artisan migrate:fresh --force
docker compose exec app php artisan optimize
docker compose restart app
echo "✅ Architecture is LIVE"
EOL

cat <<EOL > bench.sh
#!/bin/bash
# Runs benchmark from WITHIN the docker network to bypass Windows latency
docker run --rm --network ${PROJECT_NAME}_sass-network williamyeh/wrk -t16 -c400 -d30s http://nginx/api/ping
EOL

chmod +x deploy.sh bench.sh

# -----------------------------
# 🧠 6. Optimized .env
# -----------------------------
cat <<EOL > .env
APP_ENV=production
APP_DEBUG=false
OCTANE_SERVER=swoole
DB_HOST=mysql
DB_DATABASE=app
DB_USERNAME=root
DB_PASSWORD=root
REDIS_HOST=redis
REDIS_SERIALIZER=igbinary
SESSION_DRIVER=redis
CACHE_STORE=redis
QUEUE_CONNECTION=redis
EOL

echo "✅ Project '$PROJECT_NAME' created!"
echo "👉 1. Move this folder to ~/ if you are in WSL2. "
echo "👉 Ex: cp -r /mnt/c/Working/ci-cd-example/sass-service/sass-optimized-service ~/sass-optimized-service"
echo "👉 2. Add 'Route::get(\"/ping\", fn() => \"ok\");' to src/routes/api.php"
echo "👉 3. Run ./deploy.sh"