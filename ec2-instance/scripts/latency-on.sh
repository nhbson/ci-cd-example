#!/bin/bash

echo "🌐 Adding real network simulation..."

sudo tc qdisc add dev lo root netem delay 50ms 10ms loss 0.5%

echo "✅ Latency ON"