#!/bin/bash
# Runs benchmark from WITHIN the docker network to bypass Windows latency
docker run --rm --network sass-optimized-service_sass-network williamyeh/wrk -t16 -c400 -d30s http://nginx/ping
