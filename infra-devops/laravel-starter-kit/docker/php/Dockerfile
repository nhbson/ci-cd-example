FROM php:8.3-cli

RUN apt-get update && apt-get install -y     git curl zip unzip libpq-dev     && docker-php-ext-install pdo pdo_pgsql

COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

RUN pecl install swoole && docker-php-ext-enable swoole

WORKDIR /var/www/html
