#!/bin/bash

echo "🔥 Simulating 500 concurrent users..."

wrk -t8 -c500 -d60s http://localhost:8000

echo "✅ Test complete"