#!/bin/bash
# Wrapper script to check timing and run daily trading
# Called by cron every hour at minute 0

cd /Users/brosshack/project_blank/Microcap-India

# Get current time in IST
current_hour=$(TZ='Asia/Kolkata' date +%H)
current_minute=$(TZ='Asia/Kolkata' date +%M)

# Run daily trading at 09:00 IST (after market open)
if [ "$current_hour" -eq 9 ] && [ "$current_minute" -eq 0 ]; then
    echo "$(date): Running daily trading workflow..." >> logs/daily.log
    ./run_daily_trading.sh >> logs/daily.log 2>&1
    echo "$(date): Daily trading complete" >> logs/daily.log
else
    # Not time to run
    exit 0
fi
