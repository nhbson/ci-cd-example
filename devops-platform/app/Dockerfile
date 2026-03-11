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