FROM php:8.3-cli

WORKDIR /var/www

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git curl zip unzip \
    libssl-dev \
    zlib1g-dev \
    libcurl4-openssl-dev \
    pkg-config \
    build-essential \
    autoconf \
    && docker-php-ext-install pdo pdo_mysql pcntl

# Install Swoole
RUN pecl install swoole \
    && docker-php-ext-enable swoole

# Install Redis extension
RUN pecl install redis \
    && docker-php-ext-enable redis

# Copy Laravel project
COPY ./www .

CMD ["php", "-v"]