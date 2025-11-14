#!/bin/bash
# Mid-day Adaptive Trading Runner
# Triggered at 10:30 AM if intraday reversal confirmed

cd /home/ubuntu/trading

# Set environment
export PYTHONPATH=/home/ubuntu/trading
export TZ='Asia/Kolkata'

# Database credentials
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=lightrain
export DB_USER=lightrain_user
export DB_PASSWORD='LightRain2025@Secure'

# Flag for 50% position sizing (mid-day entry)
export MIDDAY_ENTRY=true
export POSITION_SIZE_MULTIPLIER=0.5

echo "======================================================================="
echo "🕥 MID-DAY ADAPTIVE ENTRY - 10:30 AM"
echo "======================================================================="
echo "📅 $(date '+%d %b %Y, %H:%M:%S IST')"
echo "🔄 Running with 50% position sizing (adaptive reversal entry)"
echo "======================================================================="

# Run DAILY strategy with reduced sizing
python3 daily_trading_pg.py >> logs/midday_trading.log 2>&1

echo "✅ Mid-day trading complete!"
