#!/usr/bin/env python3
"""Monitor and exit positions when TP/SL hit - Daily strategy"""
import pandas as pd
import yfinance as yf
import json
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
PORTFOLIO_FILE = os.path.join(BASE_DIR, "data/portfolio.csv")
TRADES_FILE = os.path.join(BASE_DIR, "data/trades.csv")
CAPITAL_FILE = os.path.join(BASE_DIR, "data/capital_tracker.json")

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

portfolio = pd.read_csv(PORTFOLIO_FILE)
active = portfolio[portfolio['Status'] == 'HOLD']
exits_made = False

for _, row in active.iterrows():
    ticker = row['Ticker']
    entry = float(row['EntryPrice'])
    sl = float(row['StopLoss'])
    tp = float(row['TakeProfit'])
    qty = int(row['Quantity'])
    entry_date = row.get('EntryDate', datetime.now().strftime("%Y-%m-%d"))

    df = yf.download(ticker, period='1d', progress=False)
    if df.empty:
        continue

    current = float(df['Close'].iloc[-1])

    # 1. Circuit Breaker Check (4% alert, 5% hard stop) - runs BEFORE TP/SL
    if check_if_position_on_hold(ticker):
        print(f"⏸️ {ticker}: On hold (skipping circuit breaker)")
        action = 'HOLD'
    else:
        action, loss, analysis = check_circuit_breaker(
            ticker, entry, current, entry_date,
            alert_threshold=0.04,  # 4% alert
            hard_stop=0.05         # 5% hard stop
        )

    if action == 'CIRCUIT_BREAKER':
        # 5% hard stop - immediate exit
        pnl = round((current - entry) * qty, 2)
        portfolio = portfolio[portfolio['Ticker'] != ticker]
        log_trade(ticker, "SELL", current, qty, f"DAILY CIRCUIT-BREAKER at {analysis['loss_pct']:.2f}%", pnl)
        update_capital(pnl)
        exits_made = True

        msg = format_circuit_breaker_message(ticker, analysis)
        send_telegram_message(msg)
        print(f"🔴 {ticker} Circuit Breaker triggered: ₹{pnl}")
        continue

    elif action == 'ALERT':
        # 4% alert - investigate
        print(f"⚠️ {ticker} at {analysis['loss_pct']:.2f}% loss - sending alert")

        drop_analysis = analyze_drop_reason(ticker)

        try:
            from scripts.ai_news_analyzer import get_ai_recommendation
            ai_analysis = get_ai_recommendation(
                ticker, drop_analysis,
                entry, current, analysis['loss_pct']
            )
            print(f"🤖 AI: {ai_analysis.get('ai_recommendation', 'N/A')} ({ai_analysis.get('ai_confidence', 'N/A')})")
        except Exception as e:
            print(f"⚠️ AI analysis failed: {e}")
            ai_analysis = None

        msg = format_alert_message(ticker, analysis, drop_analysis, ai_analysis)
        send_telegram_message(msg)

    # 2. Regular TP/SL Check (after circuit breaker)
    if current <= sl:
        pnl = round((current - entry) * qty, 2)
        portfolio = portfolio[portfolio['Ticker'] != ticker]
        log_trade(ticker, "SELL", current, qty, f"SL hit at {sl:.2f}", pnl)
        update_capital(pnl)
        exits_made = True

        msg = f"🛑 *STOP LOSS HIT*\n{ticker}\nExit: ₹{current:.2f}\nP&L: ₹{pnl:+,.2f}"
        send_telegram_message(msg)
        print(f"🛑 {ticker} SL hit: ₹{pnl}")
    elif current >= tp:
        pnl = round((current - entry) * qty, 2)
        portfolio = portfolio[portfolio['Ticker'] != ticker]
        log_trade(ticker, "SELL", current, qty, f"TP hit at {tp:.2f}", pnl)
        update_capital(pnl)
        exits_made = True

        pnl_pct = ((current - entry) / entry) * 100
        msg = f"🎯 *TAKE PROFIT HIT*\n{ticker}\nExit: ₹{current:.2f} (+{pnl_pct:.2f}%)\nP&L: ₹{pnl:+,.2f}"
        send_telegram_message(msg)
        print(f"🎯 {ticker} TP hit: ₹{pnl}")

portfolio.to_csv(PORTFOLIO_FILE, index=False)

if exits_made:
    import subprocess
    subprocess.run(['/Users/brosshack/project_blank/venv/bin/python3', os.path.join(BASE_DIR, 'scripts/portfolio_manager.py')], cwd=BASE_DIR)
