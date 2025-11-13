#!/bin/bash
# check_and_run_swing.sh - Timezone-aware swing trading launcher
# This checks if it's 4:00 PM IST and runs swing trading if yes
# Run this every hour via cron: 0 * * * *

cd /Users/brosshack/project_blank/Microcap-India

# Get current hour in IST
IST_HOUR=$(TZ='Asia/Kolkata' date +%H)
IST_MINUTE=$(TZ='Asia/Kolkata' date +%M)

# Check if it's 4:00 PM IST (16:00, allow 16:00-16:59)
if [ "$IST_HOUR" = "16" ]; then
    # Check if already ran today
    TODAY=$(TZ='Asia/Kolkata' date +%Y-%m-%d)
    MARKER="/tmp/microcap_swing_$TODAY"

    if [ ! -f "$MARKER" ]; then
        echo "$(date): Running swing trading at IST 16:${IST_MINUTE} (4 PM)" >> logs/cron.log

        # Run the swing trading script
        ./run_swing_trading.sh >> logs/swing_cron.log 2>&1

        # Mark as done for today
        touch "$MARKER"
    fi
fi
