#!/bin/bash
# Configure Telegram Bot Credentials for LightRain
# Run this on AWS VM: ./configure_telegram.sh

cd ~/trading

echo "========================================================================"
echo "🤖 Configuring LightRain Telegram Bot"
echo "========================================================================"
echo ""

# Add Telegram credentials to .env
cat >> .env << 'EOF'

# Telegram Bot for LightRain
TELEGRAM_BOT_TOKEN=8440439995:AAEGlIB_KMlA88EEZJelaL97FJ1DfGGE3X8
TELEGRAM_CHAT_ID=940492565
EOF

echo "✅ Telegram credentials added to .env"
echo ""

# Test the bot
echo "📱 Testing Telegram bot..."
source venv/bin/activate
python3 << 'PYTEST'
import os
import requests

TOKEN = "8440439995:AAEGlIB_KMlA88EEZJelaL97FJ1DfGGE3X8"
CHAT_ID = "940492565"

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
data = {
    "chat_id": CHAT_ID,
    "text": "🌧️ LightRain Bot is online!\n\nAWS VM configured successfully.\nReady to start trading.",
    "parse_mode": "Markdown"
}

response = requests.post(url, json=data)
if response.status_code == 200:
    print("✅ Test message sent successfully!")
    print("Check your Telegram for confirmation.")
else:
    print(f"❌ Failed: {response.text}")
PYTEST

echo ""
echo "========================================================================"
echo "✅ Configuration Complete!"
echo "========================================================================"
echo ""
echo "📋 Next steps:"
echo "   1. Setup cron jobs: ./deploy/setup_cron.sh"
echo "   2. Test pre-market: python3 premarket_check.py"
echo ""
