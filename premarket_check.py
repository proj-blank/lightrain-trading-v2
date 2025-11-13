#!/usr/bin/env python3
"""
Pre-Market Global Sentiment Check
Run at 8:45 AM IST before market opens at 9:15 AM

Captures overnight moves in US/Asia markets to predict India opening
"""
import sys
sys.path.insert(0, '/Users/brosshack/project_blank/LightRain')

from scripts.global_market_sentiment import get_global_sentiment, save_global_sentiment, should_adjust_strategy
from scripts.telegram_bot import send_telegram_message
from datetime import datetime

print("="*70)
print("🌍 PRE-MARKET GLOBAL SENTIMENT CHECK")
print("="*70)
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
print()

# Fetch global markets data
print("📊 Fetching global market data...")
sentiment_data = get_global_sentiment()

# Save to database
save_global_sentiment(sentiment_data)
print("✅ Sentiment data saved to database")
print()

# Display results
print("="*70)
print("OVERNIGHT MARKET MOVES")
print("="*70)
print(f"🇺🇸 US Markets:")
print(f"   S&P 500:  {sentiment_data['sp500_change_pct']:+.2f}%")
print(f"   Nasdaq:   {sentiment_data['nasdaq_change_pct']:+.2f}%")
print(f"   VIX:      {sentiment_data['vix_change_pct']:+.2f}%")
print()
print(f"🌏 Asian Markets:")
print(f"   Nikkei:     {sentiment_data['nikkei_change_pct']:+.2f}%")
print(f"   Hang Seng:  {sentiment_data['hang_seng_change_pct']:+.2f}%")
print()
print("="*70)
print("SENTIMENT ANALYSIS")
print("="*70)
print(f"Global Sentiment: {sentiment_data['global_sentiment']}")
print(f"Expected NIFTY Gap: {sentiment_data['overnight_gap_expected']:+.2f}%")
print(f"Risk Mode: {sentiment_data['risk_on_off']}")
if sentiment_data['us_asia_divergence']:
    print("⚠️  WARNING: US and Asia markets diverging!")
if sentiment_data['is_monday']:
    print("📅 Monday Effect: 36+ hour gap since Friday close")
print()

# Get strategy adjustment recommendation
adjustment = should_adjust_strategy()
print("="*70)
print("TRADING STRATEGY ADJUSTMENT")
print("="*70)
print(f"Action: {adjustment['action']}")
print(f"Reason: {adjustment['reason']}")
print(f"Position Size Multiplier: {adjustment['position_adjustment']:.2f}x")
print()

# Prepare Telegram message
if adjustment['action'] != 'NORMAL':
    emoji = "🚀" if adjustment['action'] == 'BOOST' else "⚠️"
    msg = f"{emoji} *PRE-MARKET ALERT*\n\n"
    msg += f"*Global Sentiment:* {sentiment_data['global_sentiment']}\n"
    msg += f"*Expected NIFTY Gap:* {sentiment_data['overnight_gap_expected']:+.2f}%\n\n"
    msg += f"*US Overnight:*\n"
    msg += f"S&P 500: {sentiment_data['sp500_change_pct']:+.2f}%\n"
    msg += f"Nasdaq: {sentiment_data['nasdaq_change_pct']:+.2f}%\n\n"
    msg += f"*Strategy Adjustment:*\n"
    msg += f"{adjustment['action']} - {adjustment['reason']}\n"
    msg += f"Position sizes: {adjustment['position_adjustment']:.0%}"

    send_telegram_message(msg)
    print("📱 Telegram alert sent")
else:
    print("ℹ️  No significant global moves - proceeding normally")

print()
print("="*70)
print("✅ Pre-market check complete")
print("="*70)
