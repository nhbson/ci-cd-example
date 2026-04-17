#!/bin/bash

SERVICE=$1

if [ -z "$SERVICE" ]; then
  docker compose -f docker-stack.yml logs -f
else
  docker compose -f docker-stack.yml logs -f $SERVICE
fi
