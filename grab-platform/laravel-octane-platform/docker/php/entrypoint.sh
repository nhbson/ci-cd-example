#!/bin/sh

set -e

cd /var/www

php artisan config:clear || true
php artisan route:clear || true
php artisan cache:clear || true

exec php artisan octane:start \
  --server=swoole \
  --host=0.0.0.0 \
  --port=8000 \
  --workers=4 \
  --task-workers=2
