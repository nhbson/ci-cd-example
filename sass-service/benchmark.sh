#!/bin/bash

URL=${1:-http://localhost/ping}
THREADS=16
CONNECTIONS=400
DURATION=30s
MIN_RPS=10000

echo "🚀 Running benchmark..."
echo "URL: $URL"

OUTPUT=$(wrk -t$THREADS -c$CONNECTIONS -d$DURATION $URL)

echo "$OUTPUT"

# Extract Requests/sec
RPS=$(echo "$OUTPUT" | grep "Requests/sec" | awk '{print $2}')

echo "👉 RPS: $RPS"

# Compare
RPS_INT=${RPS%.*}

if [ "$RPS_INT" -lt "$MIN_RPS" ]; then
    echo "❌ FAIL: RPS ($RPS) is below $MIN_RPS"
    exit 1
else
    echo "✅ PASS: RPS ($RPS) >= $MIN_RPS"
fi