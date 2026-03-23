#!/bin/bash

echo "⚠️ Rolling back..."

sed -i 's/app_green/app_blue/g' nginx.conf
docker exec nginx nginx -s reload

docker stop app_green

echo "✅ Rollback done"