#!/bin/bash
# run_swing_trading.sh - PostgreSQL version
cd /home/ubuntu/trading

echo "=========================================="
echo "⚡ SWING TRADING - PostgreSQL"
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

python3 swing_trading_pg.py

STATUS=$?

if [ $STATUS -ne 0 ]; then
    echo "ERROR: Swing trading failed with status $STATUS"
    exit $STATUS
fi

echo ""
echo "✅ Swing Trading Complete"
exit 0
