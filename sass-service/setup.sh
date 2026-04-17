#!/bin/bash

set -e

PROJECT_NAME="."

echo "🚀 Creating project structure: $PROJECT_NAME"

# Root
mkdir -p $PROJECT_NAME
cd $PROJECT_NAME

# -----------------------------
# 📁 Docker folders
# -----------------------------
mkdir -p docker/nginx
mkdir -p docker/php
mkdir -p docker/supervisor

# -----------------------------
# 📁 Laravel source
# -----------------------------
mkdir -p src

# -----------------------------
# 📄 Core files
# -----------------------------
touch docker/nginx/nginx.conf
touch docker/php/Dockerfile
touch docker/supervisor/worker.conf

touch docker-stack.yml
touch .env
touch deploy.sh
touch scale.sh
touch logs.sh

# -----------------------------
# 🧠 Default nginx.conf
# -----------------------------
cat <<EOL > docker/nginx/nginx.conf
worker_processes auto;

events {
    worker_connections 1024;
}

http {
    sendfile on;

    upstream php-upstream {
        server php:9000;
    }

    server {
        listen 80;

        root /var/www/public;
        index index.php index.html;

        location / {
            try_files \$uri \$uri/ /index.php?\$query_string;
        }

        location ~ \.php$ {
            include fastcgi_params;
            fastcgi_pass php-upstream;
            fastcgi_param SCRIPT_FILENAME \$document_root\$fastcgi_script_name;
        }
    }
}
EOL

# -----------------------------
# 🧠 Default PHP Dockerfile
# -----------------------------
cat <<EOL > docker/php/Dockerfile
FROM php:8.2-fpm

RUN apt-get update && apt-get install -y \
    git unzip curl libzip-dev \
    && docker-php-ext-install pdo pdo_mysql zip

WORKDIR /var/www

COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

CMD ["php-fpm"]
EOL

# -----------------------------
# 🧠 Supervisor config
# -----------------------------
cat <<EOL > docker/supervisor/worker.conf
[program:laravel-worker]
process_name=%(program_name)s_%(process_num)02d
command=php /var/www/artisan queue:work --sleep=3 --tries=3 --timeout=90
autostart=true
autorestart=true
numprocs=2
redirect_stderr=true
stdout_logfile=/var/www/storage/logs/worker.log
EOL

# -----------------------------
# 🧠 docker-stack.yml
# -----------------------------
cat <<EOL > docker-stack.yml
version: "3.8"

services:
  nginx:
    image: nginx:latest
    ports:
      - "80:80"
    volumes:
      - ./src:/var/www
      - ./docker/nginx/nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - php

  php:
    build:
      context: .
      dockerfile: docker/php/Dockerfile
    volumes:
      - ./src:/var/www
    working_dir: /var/www

  mysql:
    image: mysql:8
    environment:
      MYSQL_DATABASE: laravel
      MYSQL_ROOT_PASSWORD: root
    ports:
      - "3306:3306"
    volumes:
      - dbdata:/var/lib/mysql

  redis:
    image: redis:alpine

volumes:
  dbdata:
EOL

# -----------------------------
# 🧠 .env
# -----------------------------
cat <<EOL > .env
APP_ENV=local
APP_DEBUG=true

DB_HOST=mysql
DB_DATABASE=laravel
DB_USERNAME=root
DB_PASSWORD=root

REDIS_HOST=redis
EOL

# -----------------------------
# 🚀 deploy.sh
# -----------------------------
cat <<EOL > deploy.sh
#!/bin/bash
set -e

echo "🚀 Deploying stack..."

docker compose -f docker-stack.yml down
docker compose -f docker-stack.yml up -d --build

echo "✅ Deployment completed"
EOL

chmod +x deploy.sh

# -----------------------------
# 📈 scale.sh
# -----------------------------
cat <<EOL > scale.sh
#!/bin/bash

SERVICE=\$1
COUNT=\$2

if [ -z "\$SERVICE" ] || [ -z "\$COUNT" ]; then
  echo "Usage: ./scale.sh [service] [count]"
  exit 1
fi

docker compose -f docker-stack.yml up -d --scale \$SERVICE=\$COUNT

echo "📈 Scaled \$SERVICE to \$COUNT"
EOL

chmod +x scale.sh

# -----------------------------
# 📜 logs.sh
# -----------------------------
cat <<EOL > logs.sh
#!/bin/bash

SERVICE=\$1

if [ -z "\$SERVICE" ]; then
  docker compose -f docker-stack.yml logs -f
else
  docker compose -f docker-stack.yml logs -f \$SERVICE
fi
EOL

chmod +x logs.sh

# -----------------------------
# 🎉 Done
# -----------------------------
echo "✅ Project structure created successfully!"
echo ""
echo "Next steps:"
echo "1. cd $PROJECT_NAME"
echo "2. Put your Laravel app into ./src"
echo "3. Run ./deploy.sh"