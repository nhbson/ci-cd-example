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
