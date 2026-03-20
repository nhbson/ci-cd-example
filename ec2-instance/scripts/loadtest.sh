#!/bin/bash

echo "🔥 Simulating 5000 concurrent users..."

wrk -t8 -c5000 -d60s http://localhost:8000

echo "✅ Test complete"