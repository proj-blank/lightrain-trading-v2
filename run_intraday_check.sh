#!/bin/bash
# Intraday Regime Check Runner - Runs at 10 AM and 11 AM IST

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

# Run intraday regime check
python3 intraday_regime_check.py >> logs/intraday_check.log 2>&1
