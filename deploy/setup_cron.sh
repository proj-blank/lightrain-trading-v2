#!/bin/bash
# Setup Cron Jobs for Automated Trading - Run on AWS VM

echo "======================================================================"
echo "⏰ Setting up Cron Jobs for LightRain"
echo "======================================================================"

# Set timezone to IST
echo "🌍 Setting timezone to Asia/Kolkata..."
sudo timedatectl set-timezone Asia/Kolkata

# Paths
PROJECT_DIR="$HOME/trading"
PYTHON="$PROJECT_DIR/venv/bin/python3"
LOG_DIR="$PROJECT_DIR/logs"

# Create log directory
mkdir -p "$LOG_DIR"

# Create cron jobs file
cat > /tmp/lightrain_cron <<EOF
# LightRain Trading System - Automated Schedules
# Timezone: Asia/Kolkata (IST)

# Pre-Market Global Sentiment Check - 8:45 AM IST (30 min before market)
45 8 * * 1-5 cd $PROJECT_DIR && $PYTHON premarket_check.py >> $LOG_DIR/premarket.log 2>&1

# Daily Trading - Runs at 9:20 AM IST (after market opens at 9:15)
20 9 * * 1-5 cd $PROJECT_DIR && TRADING_ENABLED=true LIVE_ORDERS_ENABLED=false $PYTHON daily_trading_pg.py >> $LOG_DIR/daily.log 2>&1

# Daily Monitor - Every 5 minutes during market hours (9:15 AM - 3:30 PM)
*/5 9-15 * * 1-5 cd $PROJECT_DIR && $PYTHON monitor_positions.py >> $LOG_DIR/monitor.log 2>&1

# Swing Trading - Runs at 9:25 AM IST
25 9 * * 1-5 cd $PROJECT_DIR && TRADING_ENABLED=true LIVE_ORDERS_ENABLED=false $PYTHON swing_trading_pg.py >> $LOG_DIR/swing.log 2>&1

# Swing Monitor - Once per day at 3:00 PM (before market close)
0 15 * * 1-5 cd $PROJECT_DIR && $PYTHON monitor_swing.py >> $LOG_DIR/monitor_swing.log 2>&1

# Daily Log Rotation - 11:59 PM every day
59 23 * * * find $LOG_DIR -name "*.log" -mtime +7 -delete

# Health Check - Send heartbeat every day at 9:00 AM
0 9 * * 1-5 cd $PROJECT_DIR && echo "LightRain running on \$(date)" >> $LOG_DIR/heartbeat.log

EOF

# Install cron jobs
crontab /tmp/lightrain_cron
rm /tmp/lightrain_cron

echo ""
echo "✅ Cron jobs installed!"
echo ""
echo "📋 Schedule:"
echo "   Pre-Market Check: 8:45 AM IST (Global sentiment)"
echo "   Daily Trading:    9:20 AM IST"
echo "   Daily Monitor:    Every 5 min (9:15 AM - 3:30 PM)"
echo "   Swing Trading:    9:25 AM IST"
echo "   Swing Monitor:    3:00 PM IST"
echo ""
echo "📝 View cron jobs: crontab -l"
echo "📊 View logs: tail -f $LOG_DIR/daily.log"
echo ""
echo "======================================================================"
