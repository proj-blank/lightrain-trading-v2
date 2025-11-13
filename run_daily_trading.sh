#!/bin/bash
# run_daily_trading.sh - PostgreSQL version
cd /home/ubuntu/trading

echo "=========================================="
echo "⚡ DAILY TRADING - PostgreSQL"
echo "Time: $(TZ='Asia/Kolkata' date)"
echo "=========================================="

# Load environment variables
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Export database credentials
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=lightrain
export DB_USER=lightrain_user
export DB_PASSWORD='LightRain2025@Secure'

python3 daily_trading_pg.py

STATUS=$?

if [ $STATUS -ne 0 ]; then
    echo "ERROR: Daily trading failed with status $STATUS"
    exit $STATUS
fi

echo ""
echo "✅ Daily Trading Complete"
exit 0
