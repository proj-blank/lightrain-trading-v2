#!/usr/bin/env python3
"""Monitor and exit positions when TP/SL hit - Swing strategy"""
import json
import yfinance as yf
import os
import sys
from datetime import datetime

# Add scripts to path for circuit breaker integration
sys.path.append('/Users/brosshack/project_blank/Microcap-India')
from scripts.risk_manager import (
    check_circuit_breaker,
    analyze_drop_reason,
    format_alert_message,
    format_circuit_breaker_message
)
from scripts.telegram_bot import send_telegram_message, check_if_position_on_hold

BASE_DIR = "/Users/brosshack/project_blank/Microcap-India"
PORTFOLIO_FILE = os.path.join(BASE_DIR, "data/swing_portfolio.json")
TRADES_FILE = os.path.join(BASE_DIR, "data/trades.csv")
CAPITAL_FILE = os.path.join(BASE_DIR, "data/swing_capital_tracker.json")

def update_capital(pnl):
    with open(CAPITAL_FILE) as f:
        cap = json.load(f)

    if pnl > 0:
        # Lock profits - DO NOT reinvest (safety mechanism)
        cap['total_profits_locked'] += pnl
    else:
        # Subtract losses from trading capital
        cap['current_trading_capital'] += pnl  # pnl is negative
        # Track losses for reporting
        cap['total_losses'] += abs(pnl)

    cap['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M')

    with open(CAPITAL_FILE, 'w') as f:
        json.dump(cap, f, indent=2)

def log_trade(ticker, signal, price, qty, notes="", pnl=None):
    import pandas as pd
    trade = pd.DataFrame([{
        "Date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Ticker": ticker,
        "Signal": signal,
        "Price": price,
        "Quantity": qty,
        "PnL": pnl if pnl is not None else "",
        "Notes": notes
    }])
    trade.to_csv(TRADES_FILE, mode="a", header=False, index=False)

with open(PORTFOLIO_FILE) as f:
    portfolio = json.load(f)

positions_to_remove = []
exits_made = False

for i, pos in enumerate(portfolio):
    ticker = pos['Ticker']
    entry = float(pos['EntryPrice'])
    sl = float(pos['StopLoss'])
    tp = float(pos['TakeProfit'])
    qty = int(pos['Quantity'])
    entry_date = pos.get('EntryDate', datetime.now().strftime('%Y-%m-%d'))
    highest_price = float(pos.get('HighestPrice', entry))
    days_held = int(pos.get('DaysHeld', 0))

    # Download data with enough history for smart stops
    df = yf.download(ticker, period='1mo', progress=False)
    if df.empty:
        continue

    current = float(df['Close'].iloc[-1])

    # Update highest price
    if current > highest_price:
        highest_price = current
        portfolio[i]['HighestPrice'] = highest_price

    # Recalculate smart stops dynamically (includes Chandelier trailing)
    from scripts.risk_manager import calculate_atr, calculate_smart_stops_swing

    atr = calculate_atr(df, period=14)
    recent_low = float(df['Low'].tail(5).min()) if len(df) >= 5 else None

    # Recalculate smart stops
    smart_stops = calculate_smart_stops_swing(
        entry_price=entry,
        current_price=current,
        highest_price=highest_price,
        atr=atr,
        days_held=days_held,
        recent_low=recent_low
    )

    # Update stop loss (only tighten, never widen)
    new_stop = smart_stops['stop_loss']
    sl = max(sl, new_stop)
    portfolio[i]['StopLoss'] = sl

    print(f"  📊 {ticker}: Smart Stop=₹{sl:.2f} (method: {smart_stops['method']}) | Current: ₹{current:.2f}")

    # 🛡️ CIRCUIT BREAKER CHECK - Priority #1 (before TP/SL checks)
    # Check if user has enabled smart-stop mode for this position
    from scripts.telegram_bot import check_if_smart_stop_mode

    if check_if_smart_stop_mode(ticker):
        # User chose smart-stop mode - skip circuit breaker, let smart stops decide
        print(f"🤖 {ticker}: Smart-stop mode active | Skipping circuit breaker")
        action = 'HOLD'  # Skip circuit breaker logic
    else:
        # Normal circuit breaker check
        action, loss, analysis = check_circuit_breaker(
            ticker, entry, current, entry_date,
            alert_threshold=0.03,  # 3% alert - triggers AI analysis
            hard_stop=0.05         # 5% hard stop
        )

    if action == 'CIRCUIT_BREAKER':
        # Hard stop - immediate exit
        pnl = round((current - entry) * qty, 2)
        positions_to_remove.append(i)
        log_trade(ticker, "SELL", current, qty, f"SWING CIRCUIT-BREAKER at {analysis['loss_pct']:.2f}%", pnl)
        update_capital(pnl)
        exits_made = True

        # Send circuit breaker notification
        msg = format_circuit_breaker_message(ticker, analysis)
        send_telegram_message(msg)
        print(f"🔴 {ticker} Circuit Breaker triggered: ₹{pnl}")
        continue

    elif action == 'ALERT':
        # 3% loss - check if user already said to hold
        if check_if_position_on_hold(ticker):
            print(f"🚨 {ticker} at {analysis['loss_pct']:.2f}% loss | Skipping alert (user marked HOLD)")
        else:
            # Analyze why it's dropping - technical analysis
            drop_analysis = analyze_drop_reason(ticker)

            # Get AI analysis (news + technical)
            ai_analysis = None
            try:
                from scripts.ai_news_analyzer import get_ai_recommendation
                ai_analysis = get_ai_recommendation(
                    ticker, drop_analysis,
                    entry, current, analysis['loss_pct']
                )
                print(f"🤖 AI Recommendation: {ai_analysis.get('ai_recommendation', 'N/A')} (Confidence: {ai_analysis.get('ai_confidence', 'N/A')})")
            except Exception as e:
                print(f"⚠️ AI analysis failed: {e}")

            # Send Telegram alert with both technical and AI analysis
            msg = format_alert_message(ticker, analysis, drop_analysis, ai_analysis)
            send_telegram_message(msg)
            print(f"🚨 {ticker} 3% alert sent with AI analysis | Loss: {analysis['loss_pct']:.2f}%")
        # Don't exit - wait for user decision or 5% hard stop
        # Skip TP/SL checks to avoid premature exit
        continue

    # Regular TP/SL checks (only if circuit breaker not triggered)
    if current <= sl:
        pnl = round((current - entry) * qty, 2)
        positions_to_remove.append(i)
        log_trade(ticker, "SELL", current, qty, f"SWING SL hit at {sl:.2f}", pnl)
        update_capital(pnl)
        exits_made = True

        msg = f"🛑 *SWING SL HIT*\n{ticker}\nExit: ₹{current:.2f}\nP&L: ₹{pnl:+,.2f}"
        send_telegram_message(msg)
        print(f"🛑 {ticker} SL hit: ₹{pnl}")
    elif current >= tp:
        pnl = round((current - entry) * qty, 2)
        positions_to_remove.append(i)
        log_trade(ticker, "SELL", current, qty, f"SWING TP hit at {tp:.2f}", pnl)
        update_capital(pnl)
        exits_made = True

        pnl_pct = ((current - entry) / entry) * 100
        msg = f"🎯 *SWING TP HIT*\n{ticker}\nExit: ₹{current:.2f} (+{pnl_pct:.2f}%)\nP&L: ₹{pnl:+,.2f}"
        send_telegram_message(msg)
        print(f"🎯 {ticker} TP hit: ₹{pnl}")

for idx in reversed(positions_to_remove):
    portfolio.pop(idx)

with open(PORTFOLIO_FILE, 'w') as f:
    json.dump(portfolio, f, indent=2)

if exits_made:
    import subprocess
    subprocess.run(['/Users/brosshack/project_blank/venv/bin/python3', os.path.join(BASE_DIR, 'swing_trading.py')], cwd=BASE_DIR)
