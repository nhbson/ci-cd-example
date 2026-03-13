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
