# scripts/telegram_bot.py
"""
Telegram bot for trading notifications and control.
Send daily reports, alerts, and allow remote control.
"""

import os
import pandas as pd
from datetime import datetime
import pytz
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram_message(message, parse_mode="Markdown"):
    """Send a message via Telegram bot."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": parse_mode
    }

    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("✅ Telegram message sent")
            return True
        else:
            print(f"❌ Telegram error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Failed to send Telegram: {e}")
        return False


def send_daily_report(portfolio_summary, trades_today, signals, strategy="DAILY"):
    """Send formatted daily trading report."""

    date_str = datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%d %b %Y, %H:%M")

    strategy_emoji = "⚡" if strategy == "DAILY" else "📈" if strategy == "SWING" else "🤖"
    strategy_name = f"{strategy} TRADING" if strategy in ["DAILY", "SWING"] else "MICROCAP INDIA"

    message = f"""
{strategy_emoji} *{strategy_name} - REPORT*
📅 {date_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💼 *PORTFOLIO SUMMARY*
{portfolio_summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 *TODAY'S TRADES*
{trades_today if trades_today else 'No trades today'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 *SIGNALS GENERATED*
{signals if signals else 'No signals today'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    send_telegram_message(message)


def send_trade_alert(ticker, action, price, quantity, details="", strategy="DAILY"):
    """Send real-time trade alert."""

    emoji = "🟢" if action == "BUY" else "🔴" if action == "SELL" else "⚪"
    strategy_tag = f"[{strategy}]" if strategy in ["DAILY", "SWING"] else ""

    message = f"""
{emoji} *{action} ALERT* {strategy_tag}

📊 *{ticker}*
💰 Price: ₹{price:.2f}
📦 Qty: {quantity}
{details}

⏰ {datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")}
"""

    send_telegram_message(message)


def send_stop_loss_alert(ticker, entry, exit_price, pnl, strategy="DAILY"):
    """Send stop-loss hit alert."""

    strategy_tag = f"[{strategy}]" if strategy in ["DAILY", "SWING"] else ""

    message = f"""
🛑 *STOP-LOSS HIT* {strategy_tag}

📊 *{ticker}*
📥 Entry: ₹{entry:.2f}
📤 Exit: ₹{exit_price:.2f}
💸 P&L: ₹{pnl:.2f}

⏰ {datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")}
"""

    send_telegram_message(message)


def send_take_profit_alert(ticker, entry, exit_price, pnl, strategy="DAILY"):
    """Send take-profit hit alert."""

    strategy_tag = f"[{strategy}]" if strategy in ["DAILY", "SWING"] else ""

    message = f"""
🎯 *TAKE-PROFIT HIT* {strategy_tag}

📊 *{ticker}*
📥 Entry: ₹{entry:.2f}
📤 Exit: ₹{exit_price:.2f}
💰 P&L: ₹{pnl:.2f}

⏰ {datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")}
"""

    send_telegram_message(message)


def send_error_alert(error_message):
    """Send error notification."""

    message = f"""
⚠️ *ERROR ALERT*

{error_message}

⏰ {datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")}
"""

    send_telegram_message(message)


def format_portfolio_summary(metrics):
    """Format portfolio metrics for Telegram."""

    if metrics['total_positions'] == 0:
        return "No active positions"

    summary = f"""*Open Positions ({metrics['total_positions']}):*
"""

    # Show detailed P&L for each position
    for pos in metrics['positions']:
        emoji = "🟢" if pos['pnl'] > 0 else "🔴" if pos['pnl'] < 0 else "⚪"
        category = pos.get('category', 'Unknown')
        summary += f"📌 {pos['ticker']}: {category}\n"
        summary += f"   Entry: ₹{pos['entry']:.2f} | Now: ₹{pos['current']:.2f} | {emoji} ₹{pos['pnl']:,.0f} ({pos['pnl_pct']:+.2f}%)\n"

    # Add portfolio totals
    summary += f"""
*Portfolio:*
💰 Exposure: ₹{metrics['total_exposure']:,.0f}
"""

    # Show total unrealized P&L
    if metrics['total_unrealized_pnl'] != 0:
        unrealized_pct = (metrics['total_unrealized_pnl'] / metrics['total_exposure'] * 100) if metrics['total_exposure'] > 0 else 0
        pnl_emoji = "🟢" if metrics['total_unrealized_pnl'] >= 0 else "🔴"
        summary += f"{pnl_emoji} Unrealized P&L: ₹{metrics['total_unrealized_pnl']:,.2f} ({unrealized_pct:+.2f}%)\n"

    return summary


def format_trades_today(trades_df):
    """Format today's trades for Telegram."""

    if trades_df.empty:
        return None

    trades_text = ""
    for _, trade in trades_df.iterrows():
        emoji = "🟢" if trade['Signal'] == 'BUY' else "🔴"
        pnl_str = f" | P&L: ₹{trade['PnL']:,.0f}" if pd.notna(trade['PnL']) else ""
        trades_text += f"\n{emoji} {trade['Signal']} {trade['Ticker']} @ ₹{trade['Price']:.2f}{pnl_str}"

    return trades_text


def format_signals(signals_list):
    """Format signals for Telegram."""

    if not signals_list:
        return None

    signals_text = ""
    for signal in signals_list[:10]:  # Max 10 signals
        emoji = "🟢" if signal['action'] == 'BUY' else "🔴" if signal['action'] == 'SELL' else "⚪"
        signals_text += f"\n{emoji} {signal['ticker']}: {signal['action']} (Score: {signal['score']})"

    return signals_text


def send_eod_position_report(portfolio, stock_data, strategy="DAILY"):
    """
    Send end-of-day position report showing:
    - Why positions weren't closed (distance from SL/TP)
    - Current P&L
    - Risk status
    """
    import yfinance as yf

    if portfolio.empty:
        return

    positions = portfolio[portfolio['Status'] == 'HOLD']

    strategy_emoji = "⚡" if strategy == "DAILY" else "📈" if strategy == "SWING" else "🔚"
    strategy_tag = f"[{strategy}]" if strategy in ["DAILY", "SWING"] else ""

    if positions.empty:
        message = f"""
{strategy_emoji} *END OF DAY REPORT* {strategy_tag}

✅ No open positions
💵 Fully in cash

⏰ Market closed - See you tomorrow!
"""
        send_telegram_message(message)
        return

    # Build report
    ist_time = datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%I:%M %p IST")
    message = f"""
{strategy_emoji} *END OF DAY REPORT* {strategy_tag}
⏰ Market Close - {ist_time}

📊 *Open Positions: {len(positions)}*

"""

    total_pnl = 0

    for _, row in positions.iterrows():
        ticker = row['Ticker']
        entry = float(row['EntryPrice'])
        qty = int(row['Quantity'])
        sl = float(row['StopLoss'])
        tp = float(row['TakeProfit'])
        category = row['Category']

        # Get current price
        try:
            if ticker in stock_data and not stock_data[ticker].empty:
                current = float(stock_data[ticker]['Close'].iloc[-1])
            else:
                stock = yf.Ticker(ticker)
                current = float(stock.history(period='1d')['Close'].iloc[-1])
        except:
            current = entry

        # Calculate metrics
        pnl = (current - entry) * qty
        pnl_pct = ((current - entry) / entry) * 100
        total_pnl += pnl

        # Distance from SL/TP
        dist_to_sl = ((current - sl) / current) * 100
        dist_to_tp = ((tp - current) / current) * 100

        # Status emoji
        if pnl >= 0:
            pnl_emoji = "🟢"
        else:
            pnl_emoji = "🔴"

        # Risk level based on distance to SL
        if dist_to_sl < 2:
            risk = "🔴 HIGH RISK"
        elif dist_to_sl < 5:
            risk = "🟡 MODERATE"
        else:
            risk = "🟢 SAFE"

        message += f"""
*{ticker}* ({category})
{pnl_emoji} P&L: ₹{pnl:,.0f} ({pnl_pct:+.1f}%)
📍 Current: ₹{current:.2f}
🛑 Stop-Loss: ₹{sl:.2f} ({dist_to_sl:.1f}% away)
🎯 Take-Profit: ₹{tp:.2f} ({dist_to_tp:.1f}% away)
{risk}

"""

    # Summary
    message += f"""
━━━━━━━━━━━━━━━━
💰 *Total Unrealized P&L: ₹{total_pnl:,.2f}*

❓ *Why Didn't We Close?*
Positions remain open because:
• No stop-loss hit (monitored every 60s)
• No take-profit hit (monitored every 60s)
• No SELL signals generated

🔄 Monitor continues tomorrow at 9:15 AM IST
"""

    send_telegram_message(message)


def get_telegram_updates(offset=None):
    """Get pending updates/messages from Telegram"""
    if not TELEGRAM_BOT_TOKEN:
        return []

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"timeout": 10}
    if offset:
        params["offset"] = offset

    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            return response.json().get("result", [])
        return []
    except Exception as e:
        print(f"❌ Failed to get updates: {e}")
        return []


def process_telegram_command(update):
    """
    Process incoming Telegram commands

    Supported commands:
    - /hold TICKER - Continue holding position despite alert (wait for 5% hard stop)
    - /exit TICKER - Exit position immediately at current price (~3%)
    - /smart-stop TICKER - Let smart stops (ATR/Chandelier) decide when to exit
    - /status - Show current positions
    """
    import json

    try:
        message = update.get("message", {})
        text = message.get("text", "")

        if not text.startswith("/"):
            return None

        parts = text.strip().split()
        command = parts[0].lower()

        if command == "/hold" and len(parts) == 2:
            ticker = parts[1].upper()
            return {"action": "hold", "ticker": ticker}

        elif command == "/exit" and len(parts) == 2:
            ticker = parts[1].upper()
            return {"action": "exit", "ticker": ticker}

        elif command == "/smart-stop" and len(parts) == 2:
            ticker = parts[1].upper()
            return {"action": "smart-stop", "ticker": ticker}

        elif command == "/status":
            return {"action": "status"}

        return None

    except Exception as e:
        print(f"❌ Error processing command: {e}")
        return None


def force_exit_position(ticker):
    """
    Force exit a position immediately (called via /exit command)

    Returns:
        success: Boolean
        message: Result message
    """
    import json
    import os
    import pandas as pd
    from datetime import datetime

    portfolio_file = 'data/swing_portfolio.json'

    if not os.path.exists(portfolio_file):
        return False, f"Portfolio file not found"

    try:
        with open(portfolio_file, 'r') as f:
            portfolio_data = json.load(f)

        portfolio = pd.DataFrame(portfolio_data)

        # Find position
        position = portfolio[portfolio['Ticker'] == ticker]

        if position.empty:
            return False, f"Position {ticker} not found in portfolio"

        pos = position.iloc[0]
        entry_price = float(pos['EntryPrice'])
        qty = int(pos['Quantity'])

        # Get current price
        import yfinance as yf
        df = yf.download(ticker, period='1d', progress=False)

        if df.empty:
            return False, f"Could not fetch current price for {ticker}"

        current_price = float(df['Close'].iloc[-1])

        # Calculate P&L
        pnl = (current_price - entry_price) * qty
        pnl_pct = ((current_price - entry_price) / entry_price) * 100

        # Log the trade
        trade_data = {
            'Date': datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d'),
            'Ticker': ticker,
            'Action': 'SELL',
            'Price': current_price,
            'Qty': qty,
            'EntryPrice': entry_price,
            'PnL': pnl,
            'PnL%': pnl_pct,
            'DaysHeld': (datetime.now(pytz.timezone('Asia/Kolkata')).date() - pd.to_datetime(pos['EntryDate']).date()).days,
            'Reason': 'MANUAL-EXIT',
            'Category': pos.get('Category', 'Unknown')
        }

        # Save trade
        trades_file = 'data/swing_trades.csv'
        trade_df = pd.DataFrame([trade_data])

        if os.path.exists(trades_file):
            trade_df.to_csv(trades_file, mode='a', header=False, index=False)
        else:
            trade_df.to_csv(trades_file, index=False)

        # Remove from portfolio
        portfolio = portfolio[portfolio['Ticker'] != ticker]

        # Save updated portfolio
        with open(portfolio_file, 'w') as f:
            json.dump(portfolio.to_dict('records'), f, indent=2)

        msg = f"""
✅ *MANUAL EXIT EXECUTED*

📊 Ticker: {ticker}
📥 Entry: ₹{entry_price:.2f}
📤 Exit: ₹{current_price:.2f}
💰 P&L: ₹{pnl:,.0f} ({pnl_pct:+.2f}%)
📦 Qty: {qty}

Position closed per your command.
"""

        return True, msg

    except Exception as e:
        return False, f"Error exiting position: {str(e)}"


def mark_position_hold(ticker):
    """
    Mark position to hold (ignore 4% alert for this position today)

    This adds a flag to prevent re-alerting on the same position
    """
    import json
    import os
    from datetime import datetime

    alert_file = 'data/alert_holds.json'

    try:
        # Load existing holds
        if os.path.exists(alert_file):
            with open(alert_file, 'r') as f:
                holds = json.load(f)
        else:
            holds = {}

        # Add hold with timestamp
        holds[ticker] = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S')

        # Save
        os.makedirs('data', exist_ok=True)
        with open(alert_file, 'w') as f:
            json.dump(holds, f, indent=2)

        msg = f"""
✅ *HOLD COMMAND RECEIVED*

📊 Ticker: {ticker}

Position will continue holding.
Alert suppressed for today.
Circuit breaker (5%) still active.
"""

        return True, msg

    except Exception as e:
        return False, f"Error marking hold: {str(e)}"


def check_if_position_on_hold(ticker):
    """Check if position has been marked to hold today"""
    import json
    import os
    from datetime import datetime

    alert_file = 'data/alert_holds.json'

    if not os.path.exists(alert_file):
        return False

    try:
        with open(alert_file, 'r') as f:
            holds = json.load(f)

        if ticker not in holds:
            return False

        # Check if hold is from today
        hold_date = holds[ticker].split()[0]
        today = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d')

        return hold_date == today

    except:
        return False


def mark_position_smart_stop(ticker):
    """
    Mark position to use smart-stop mode (let smart stops handle exits)

    This tells the system to skip circuit breaker and let ATR/Chandelier/Support stops decide
    """
    import json
    import os
    from datetime import datetime

    smart_stop_file = 'data/smart_stop_mode.json'

    try:
        # Load existing smart-stop positions
        if os.path.exists(smart_stop_file):
            with open(smart_stop_file, 'r') as f:
                smart_stops = json.load(f)
        else:
            smart_stops = {}

        # Add smart-stop mode with timestamp
        smart_stops[ticker] = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S')

        # Save
        with open(smart_stop_file, 'w') as f:
            json.dump(smart_stops, f, indent=2)

        return True, f"✅ Smart-stop mode enabled for {ticker}\nSystem will use ATR/Chandelier/Support stops instead of circuit breaker"

    except Exception as e:
        return False, f"Error: {str(e)}"


def check_if_smart_stop_mode(ticker):
    """Check if position is in smart-stop mode"""
    import json
    import os

    smart_stop_file = 'data/smart_stop_mode.json'

    if not os.path.exists(smart_stop_file):
        return False

    try:
        with open(smart_stop_file, 'r') as f:
            smart_stops = json.load(f)

        return ticker in smart_stops

    except:
        return False


def get_portfolio_status():
    """Get current portfolio status for /status command"""
    import json
    import os
    import pandas as pd
    import yfinance as yf

    portfolio_file = 'data/swing_portfolio.json'

    if not os.path.exists(portfolio_file):
        return "📊 *PORTFOLIO STATUS*\n\nNo active positions"

    try:
        with open(portfolio_file, 'r') as f:
            portfolio_data = json.load(f)

        if not portfolio_data:
            return "📊 *PORTFOLIO STATUS*\n\nNo active positions"

        portfolio = pd.DataFrame(portfolio_data)

        msg = f"📊 *PORTFOLIO STATUS*\n\n"
        msg += f"Active Positions: {len(portfolio)}\n\n"

        total_pnl = 0

        for _, pos in portfolio.iterrows():
            ticker = pos['Ticker']
            entry = float(pos['EntryPrice'])
            qty = int(pos['Quantity'])

            # Get current price
            try:
                df = yf.download(ticker, period='1d', progress=False)
                current = float(df['Close'].iloc[-1])
            except:
                current = entry

            pnl = (current - entry) * qty
            pnl_pct = ((current - entry) / entry) * 100
            total_pnl += pnl

            emoji = "🟢" if pnl >= 0 else "🔴"

            msg += f"{emoji} *{ticker}*\n"
            msg += f"   Entry: ₹{entry:.2f} | Now: ₹{current:.2f}\n"
            msg += f"   P&L: ₹{pnl:,.0f} ({pnl_pct:+.2f}%)\n\n"

        msg += f"━━━━━━━━━━━━━━━━\n"
        msg += f"💰 Total P&L: ₹{total_pnl:,.0f}"

        return msg

    except Exception as e:
        return f"❌ Error getting status: {str(e)}"
