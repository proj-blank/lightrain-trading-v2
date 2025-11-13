#!/bin/bash
# Morning Global Market Check
# Run at 8:30 AM IST (before market open)

cd /home/ubuntu/trading

echo "🌍 Running morning global market check..."
python3 global_market_filter.py

echo "✅ Market check complete"
