#!/bin/bash
# Start Telegram control bot in background
# This keeps the bot listening for commands 24/7

cd /Users/brosshack/project_blank/Microcap-India

# Check if already running
if pgrep -f "telegram_control.py" > /dev/null; then
    echo "⚠️  Bot already running (PID: $(pgrep -f telegram_control.py))"
    echo "To restart, first run: pkill -f telegram_control.py"
    exit 1
fi

# Ensure log directory exists
mkdir -p logs

# Start control bot in background with nohup (survives terminal closure)
nohup /Users/brosshack/project_blank/venv/bin/python3 -u telegram_control.py >> logs/control_bot.log 2>&1 &

PID=$!
echo "🤖 Control bot started (PID: $PID)"
echo "📝 Logs: logs/control_bot.log"
echo "🛑 To stop: pkill -f telegram_control.py"
echo ""
echo "Check status: ps -p $PID"
