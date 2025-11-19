#!/usr/bin/env python3
"""
3:00 PM MAX-HOLD Warning System
Alerts user about positions reaching hold limits (Day 2 for DAILY, Day 9 for SWING)
Runs 30 minutes before market close to allow manual exit decisions
"""
import os
import sys
sys.path.insert(0, '/home/ubuntu/trading')

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz
from scripts.db_connection import get_db_cursor
from scripts.telegram_bot import send_telegram_message

# Configuration
MAX_HOLD_DAILY = 3  # Calendar days
MAX_HOLD_SWING = 10  # Calendar days

# AI Analysis
try:
    from scripts.ai_news_analyzer import get_ai_recommendation
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    print("⚠️ AI analysis not available")

def get_positions_at_warning_threshold():
    """Get positions that are one day away from MAX_HOLD exit"""
    positions = []

    try:
        with get_db_cursor() as cur:
            # DAILY: Day 2 positions (will exit day 3)
            cur.execute("""
                SELECT
                    ticker,
                    strategy,
                    entry_price,
                    quantity,
                    entry_date,
                    CURRENT_DATE - entry_date::date AS days_held
                FROM positions
                WHERE status = 'ACTIVE'
                  AND strategy = 'DAILY'
                  AND (CURRENT_DATE - entry_date::date) = %s
            """, (MAX_HOLD_DAILY - 1,))

            daily_positions = cur.fetchall()
            positions.extend(daily_positions)

            # SWING: Day 9 positions (will exit day 10)
            cur.execute("""
                SELECT
                    ticker,
                    strategy,
                    entry_price,
                    quantity,
                    entry_date,
                    CURRENT_DATE - entry_date::date AS days_held
                FROM positions
                WHERE status = 'ACTIVE'
                  AND strategy = 'SWING'
                  AND (CURRENT_DATE - entry_date::date) = %s
            """, (MAX_HOLD_SWING - 1,))

            swing_positions = cur.fetchall()
            positions.extend(swing_positions)

        return positions
    except Exception as e:
        print(f"❌ Error fetching positions: {e}")
        return []

def get_technical_analysis(ticker, entry_price, current_price):
    """Get basic technical indicators for AI analysis"""
    try:
        stock = yf.Ticker(f"{ticker}.NS")
        hist = stock.history(period='1mo')

        if hist.empty:
            return "No technical data available"

        # Basic indicators
        current = hist['Close'].iloc[-1]
        sma_20 = hist['Close'].rolling(20).mean().iloc[-1]
        rsi = calculate_rsi(hist['Close'], 14)

        pnl_pct = ((current_price - entry_price) / entry_price) * 100

        analysis = f"Current: ₹{current:.2f} | SMA(20): ₹{sma_20:.2f} | RSI: {rsi:.1f} | P&L: {pnl_pct:+.2f}%"
        return analysis
    except:
        return "Technical analysis unavailable"

def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    try:
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
    except:
        return 50.0

def main():
    """3:00 PM MAX-HOLD warning check"""
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)

    print("=" * 70)
    print("🔔 3:00 PM MAX-HOLD WARNING CHECK")
    print(f"⏰ Time: {now.strftime('%H:%M:%S IST')}")
    print("=" * 70)

    # Get positions at warning threshold
    positions = get_positions_at_warning_threshold()

    if not positions:
        print("✅ No positions at MAX-HOLD warning threshold")
        print("=" * 70)
        return

    print(f"⚠️ Found {len(positions)} position(s) approaching MAX-HOLD limit\n")

    # Process each position
    for pos in positions:
        ticker = pos['ticker']
        strategy = pos['strategy']
        entry_price = float(pos['entry_price'])
        qty = int(pos['quantity'])
        days_held = int(pos['days_held'])
        max_days = MAX_HOLD_DAILY if strategy == 'DAILY' else MAX_HOLD_SWING

        print(f"\n📊 Processing {ticker} ({strategy})...")
        print(f"   Entry: ₹{entry_price:.2f} | Qty: {qty} | Days held: {days_held}/{max_days}")

        # Get current price
        try:
            stock = yf.Ticker(f"{ticker}.NS")
            hist = stock.history(period='1d')

            if hist.empty:
                print(f"   ⚠️ No price data available for {ticker}")
                continue

            current_price = float(hist['Close'].iloc[-1])
            pnl = (current_price - entry_price) * qty
            pnl_pct = ((current_price - entry_price) / entry_price) * 100

            print(f"   Current: ₹{current_price:.2f} | P&L: ₹{pnl:,.0f} ({pnl_pct:+.2f}%)")

            # Get technical analysis
            technical = get_technical_analysis(ticker, entry_price, current_price)

            # Get AI recommendation with news
            ai_analysis = None
            if AI_AVAILABLE:
                print(f"   🤖 Getting AI analysis with news...")
                ai_analysis = get_ai_recommendation(
                    ticker=ticker,
                    technical_analysis=technical,
                    entry_price=entry_price,
                    current_price=current_price,
                    loss_pct=pnl_pct
                )

            # Format telegram message
            pnl_emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"

            message = f"""🔔 <b>MAX-HOLD WARNING + AI ANALYSIS</b>

📊 <b>Ticker:</b> {ticker} ({strategy})
📅 <b>Held:</b> {days_held} days (max: {max_days})
💰 <b>Current P&L:</b> {pnl_emoji} ₹{pnl:,.0f} ({pnl_pct:+.2f}%)

<b>Entry:</b> ₹{entry_price:.2f} | <b>Current:</b> ₹{current_price:.2f}
<b>Quantity:</b> {qty}

<b>━━━ TECHNICAL ━━━</b>
{technical}
"""

            # Add AI analysis if available
            if ai_analysis:
                ai_rec = ai_analysis.get('ai_recommendation', 'N/A')
                ai_conf = ai_analysis.get('ai_confidence', 'N/A')
                ai_reason = ai_analysis.get('ai_reasoning', 'N/A')
                news_count = ai_analysis.get('news_count', 0)
                headlines = ai_analysis.get('headlines', [])

                message += f"""
<b>━━━ AI ANALYSIS ━━━</b>
<b>Recommendation:</b> {ai_rec}
<b>Confidence:</b> {ai_conf}
<b>Reasoning:</b> {ai_reason}
"""

                if news_count > 0:
                    message += f"\n<b>📰 Recent News ({news_count} articles):</b>\n"
                    for i, headline in enumerate(headlines[:3], 1):
                        message += f"  {i}. {headline}\n"

            # Add action guidance
            message += f"""
<b>━━━━━━━━━━━━━━━━━━━</b>

<b>⏰ Will auto-exit tomorrow at 9:00 AM</b>

<b>Options:</b>
• Exit manually today before 3:30 PM close
• Let auto-exit handle tomorrow morning
• Type /exitall to exit all positions now

<i>You have 30 minutes to decide before market close</i>
"""

            # Send telegram alert
            send_telegram_message(message)
            print(f"   ✅ Alert sent to Telegram")

        except Exception as e:
            print(f"   ❌ Error processing {ticker}: {e}")
            continue

    print("\n" + "=" * 70)
    print(f"✅ Processed {len(positions)} position(s)")
    print("=" * 70)

if __name__ == "__main__":
    main()
