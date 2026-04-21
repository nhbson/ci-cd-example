FROM php:8.3-cli-bookworm

WORKDIR /var/www

# Install system dependencies + procps (for pgrep) + build tools
RUN apt-get update && apt-get install -y \
    git curl zip unzip libzip-dev libonig-dev \
    libpng-dev libxml2-dev libssl-dev supervisor \
    libbrotli-dev libc-ares-dev libcurl4-openssl-dev \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install standard extensions
RUN docker-php-ext-install pdo_mysql mbstring zip pcntl bcmath gd

# High-Performance Serialization & Redis
RUN pecl install igbinary && docker-php-ext-enable igbinary
RUN pecl install --configureoptions 'enable-redis-igbinary="yes"' redis && docker-php-ext-enable redis

# Build Swoole with Brotli and OpenSSL support
RUN pecl install --configureoptions 'enable-sockets="no" enable-openssl="yes" enable-http2="yes" enable-mysqlnd="yes" enable-swoole-curl="yes" enable-cares="yes" enable-brotli="yes"' swoole-5.1.3 \
    && docker-php-ext-enable swoole

# Enable JIT Compiler (Huge CPU reduction)
RUN echo "opcache.enable=1" >> /usr/local/etc/php/conf.d/opcache.ini \
    && echo "opcache.enable_cli=1" >> /usr/local/etc/php/conf.d/opcache.ini \
    && echo "opcache.memory_consumption=512" >> /usr/local/etc/php/conf.d/opcache.ini \
    && echo "opcache.interned_strings_buffer=64" >> /usr/local/etc/php/conf.d/opcache.ini \
    && echo "opcache.max_accelerated_files=32531" >> /usr/local/etc/php/conf.d/opcache.ini \
    && echo "opcache.validate_timestamps=0" >> /usr/local/etc/php/conf.d/opcache.ini \
    && echo "opcache.jit_buffer_size=100M" >> /usr/local/etc/php/conf.d/opcache.ini \
    && echo "opcache.jit=1255" >> /usr/local/etc/php/conf.d/opcache.ini

COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

EXPOSE 8000
