#!/bin/bash
# EOD Summary Runner - Runs at 3:30 PM IST daily

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

# Run EOD summary
python3 eod_summary.py >> logs/eod_summary.log 2>&1
