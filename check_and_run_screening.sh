#!/bin/bash
# check_and_run_screening.sh - Run daily screening at 8:30 AM IST

cd /Users/brosshack/project_blank/Microcap-India

# Get current hour and minute in IST
IST_HOUR=$(TZ='Asia/Kolkata' date +%H)
IST_MINUTE=$(TZ='Asia/Kolkata' date +%M)

# Check if it's 8:30 AM IST (allow 8:30-8:59)
if [ "$IST_HOUR" = "08" ] && [ "$IST_MINUTE" -ge 30 ]; then
    # Check if already ran today
    TODAY=$(TZ='Asia/Kolkata' date +%Y-%m-%d)
    MARKER="/tmp/microcap_screening_$TODAY"

    if [ ! -f "$MARKER" ]; then
        echo "$(date): Running daily screening at IST ${IST_HOUR}:${IST_MINUTE}" >> logs/cron.log

        # Run the screening script
        /Users/brosshack/project_blank/venv/bin/python3 daily_screening.py >> logs/screening.log 2>&1

        # Mark as done for today
        touch "$MARKER"
    fi
fi
