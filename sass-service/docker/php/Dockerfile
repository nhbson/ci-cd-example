FROM php:8.3-cli

WORKDIR /var/www

RUN apt-get update && apt-get install -y \
    git curl zip unzip \
    libzip-dev libonig-dev \
    libpng-dev libxml2-dev \
    libssl-dev zlib1g-dev \
    libcurl4-openssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN docker-php-ext-install pdo_mysql mbstring zip pcntl

RUN pecl install redis && docker-php-ext-enable redis
RUN pecl install swoole-5.1.3 && docker-php-ext-enable swoole

COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

COPY src /var/www

RUN composer install --no-dev --optimize-autoloader

RUN chown -R www-data:www-data /var/www \
 && chmod -R 775 storage bootstrap/cache

USER www-data

EXPOSE 8000

CMD ["php", "artisan", "octane:start", "--server=swoole", "--host=0.0.0.0", "--port=8000"]