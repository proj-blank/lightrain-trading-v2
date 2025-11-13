#!/bin/bash
# check_and_run_swing_execute.sh - Execute swing trades at 9:15 AM IST
# Executes trades from signals generated at 4 PM previous day

cd /Users/brosshack/project_blank/Microcap-India

# Get current hour and minute in IST
IST_HOUR=$(TZ='Asia/Kolkata' date +%H)
IST_MINUTE=$(TZ='Asia/Kolkata' date +%M)

# Check if it's 9:15 AM IST (allow 9:15-9:59)
if [ "$IST_HOUR" = "09" ] && [ "$IST_MINUTE" -ge 15 ]; then
    # Check if already ran today
    TODAY=$(TZ='Asia/Kolkata' date +%Y-%m-%d)
    MARKER="/tmp/microcap_swing_execute_$TODAY"

    if [ ! -f "$MARKER" ]; then
        echo "$(date): Executing swing trades at IST ${IST_HOUR}:${IST_MINUTE}" >> logs/cron.log

        # Run swing trading in execute mode
        /Users/brosshack/project_blank/venv/bin/python3 swing_trading.py >> logs/swing_execute.log 2>&1

        # Mark as done for today
        touch "$MARKER"
    fi
fi
