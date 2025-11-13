# daily_trading.py
"""
Daily automated trading script with Telegram notifications.
Run this once per day (before market open or after close).
"""

import os
import sys
import pandas as pd
from datetime import datetime
from scripts.data_loader import load_data
from scripts.signal_generator_daily import generate_signal_daily
from scripts.signal_generator_v3 import get_enabled_indicators
from scripts.portfolio_manager import update_portfolio
from scripts.performance_tracker import update_results
from scripts.risk_manager import (
    calculate_position_metrics, check_circuit_breaker, analyze_drop_reason,
    format_circuit_breaker_message
)
from scripts.telegram_bot import (
    send_daily_report, send_trade_alert, send_stop_loss_alert,
    send_take_profit_alert, format_portfolio_summary,
    format_trades_today, format_signals, send_telegram_message
)
from scripts.rs_rating import RelativeStrengthAnalyzer

# Optional AI analyzer (if available)
try:
    from scripts.ai_analyzer import analyze_position_with_ai
    AI_ANALYSIS_AVAILABLE = True
except ImportError:
    AI_ANALYSIS_AVAILABLE = False
    def analyze_position_with_ai(*args, **kwargs):
        return None

# Configuration
ACCOUNT_SIZE = 500000
MAX_POSITIONS = 10
MAX_POSITION_PCT = 0.20
MIN_COMBINED_SCORE = 50
USE_ATR_SIZING = True
MIN_RS_RATING = 60  # NEW: Minimum Relative Strength rating for daily trading (1-99 scale)

print("=" * 70)
print("🤖 DAILY AUTOMATED TRADING")
print("=" * 70)
print(f"📅 {datetime.now().strftime('%d %b %Y, %H:%M:%S')}")
print("=" * 70)

# Check if trading is enabled
TRADING_ENABLED = os.getenv("TRADING_ENABLED", "true").lower() == "true"

if not TRADING_ENABLED:
    message = "⏸️ Trading is PAUSED\n\nTo resume, set TRADING_ENABLED=true in .env"
    print(message)
    send_telegram_message(message)
    sys.exit(0)

# Load stock data
print("\n📥 Loading stock data...")
stock_data = load_data(period="6mo", interval="1d")

if not stock_data:
    error_msg = "❌ No stock data loaded. Check watchlist."
    print(error_msg)
    send_telegram_message(error_msg)
    sys.exit(1)

print(f"✅ Loaded {len(stock_data)} stocks")

# Load portfolio
portfolio_path = "data/portfolio.csv"
if os.path.exists(portfolio_path):
    portfolio = pd.read_csv(portfolio_path)
    # Ensure EntryDate column exists
    if 'EntryDate' not in portfolio.columns:
        portfolio['EntryDate'] = datetime.now().strftime("%Y-%m-%d")
    print(f"✅ Portfolio loaded: {len(portfolio[portfolio['Status']=='HOLD'])} positions")
else:
    portfolio = pd.DataFrame(columns=["Ticker", "Status", "EntryPrice", "EntryDate", "Quantity", "StopLoss", "TakeProfit"])
    portfolio.to_csv(portfolio_path, index=False)
    print("⚠️ New portfolio created")

# Track today's activity
signals_generated = []
trades_today = []

print(f"\n🎯 Analyzing {len(stock_data)} stocks...")

# Show which indicators are enabled
enabled = get_enabled_indicators()
print(f"📊 Using indicators: {', '.join(enabled)}")
print()

# Initialize RS Analyzer
rs_analyzer = RelativeStrengthAnalyzer()
rs_filtered_count = 0

# Process each stock
for ticker, df in stock_data.items():
    if df.empty or len(df) < 60:
        continue

    try:
        # NEW: RS Rating Filter (Pre-filter before expensive indicator calculations)
        rs_rating = rs_analyzer.calculate_rs_rating(ticker)
        if rs_rating < MIN_RS_RATING:
            rs_filtered_count += 1
            continue  # Skip weak stocks

        # Generate signal using v3 (configurable) - only for stocks that passed RS filter
        signal, score, details = generate_signal_daily(df, min_score=MIN_COMBINED_SCORE)

        # Track signal
        if signal != "HOLD":
            signals_generated.append({
                'ticker': ticker,
                'action': signal,
                'score': score,
                'details': details,
                'rs_rating': rs_rating  # Store RS rating for reference
            })
            print(f"{ticker}: {signal} (Score: {score} | RS: {rs_rating})")

        # Track portfolio before update
        positions_before = len(portfolio[portfolio['Status'] == 'HOLD'])

        # Update portfolio
        portfolio = update_portfolio(
            portfolio, ticker, signal, df=df,
            account_size=ACCOUNT_SIZE,
            use_atr_sizing=USE_ATR_SIZING,
            max_positions=MAX_POSITIONS,
            max_position_pct=MAX_POSITION_PCT
        )

        # Track if trade happened
        positions_after = len(portfolio[portfolio['Status'] == 'HOLD'])

        if positions_before != positions_after or signal != "HOLD":
            # Check if it was a trade
            if os.path.exists("data/trades.csv"):
                trades_df = pd.read_csv("data/trades.csv")
                today = datetime.now().strftime("%Y-%m-%d")
                today_trades_df = trades_df[trades_df['Date'] == today]

                if not today_trades_df.empty:
                    latest_trade = today_trades_df.iloc[-1]

                    if latest_trade['Ticker'] == ticker:
                        # Send Telegram alert
                        price = float(latest_trade['Price'])
                        qty = int(latest_trade['Quantity'])
                        action = latest_trade['Signal']
                        notes = latest_trade.get('Notes', '')

                        # Determine alert type
                        if 'Stop-loss' in str(notes):
                            pnl = float(latest_trade.get('PnL', 0))
                            entry = float(portfolio[portfolio['Ticker']==ticker]['EntryPrice'].iloc[0]) if ticker in portfolio['Ticker'].values else 0
                            send_stop_loss_alert(ticker, entry, price, pnl, strategy="DAILY")
                        elif 'Take-profit' in str(notes):
                            pnl = float(latest_trade.get('PnL', 0))
                            entry = float(portfolio[portfolio['Ticker']==ticker]['EntryPrice'].iloc[0]) if ticker in portfolio['Ticker'].values else 0
                            send_take_profit_alert(ticker, entry, price, pnl, strategy="DAILY")
                        else:
                            details_str = f"{notes}" if notes else ""
                            send_trade_alert(ticker, action, price, qty, details_str, strategy="DAILY")

    except Exception as e:
        print(f"⚠️ Error processing {ticker}: {e}")
        continue

# Save portfolio
portfolio.to_csv(portfolio_path, index=False)
print(f"\n✅ Portfolio saved")

# Update positions tracker (for dynamic watchlist)
from scripts.position_tracker import update_positions_file
num_positions = update_positions_file(portfolio)
print(f"✅ Position tracker updated: {num_positions} open positions")

# Update performance metrics
update_results(portfolio, stock_data)

# Circuit Breaker Monitoring (4% alert / 5% hard stop)
print("\n🛡️ Checking circuit breakers...")
on_hold_path = "data/positions_on_hold.csv"
positions_on_hold = []
if os.path.exists(on_hold_path):
    hold_df = pd.read_csv(on_hold_path)
    positions_on_hold = hold_df['Ticker'].tolist()

for _, row in portfolio[portfolio['Status'] == 'HOLD'].iterrows():
    ticker = row['Ticker']
    entry_price = float(row['EntryPrice'])
    entry_date = row.get('EntryDate', datetime.now().strftime("%Y-%m-%d"))
    qty = int(row['Quantity'])

    # Skip if on hold
    if ticker in positions_on_hold:
        print(f"  ⏸️ {ticker}: On hold (suppressed)")
        continue

    if ticker in stock_data and not stock_data[ticker].empty:
        current_price = float(stock_data[ticker]['Close'].iloc[-1])

        # Check circuit breaker (4% alert, 5% hard stop)
        action, loss, analysis = check_circuit_breaker(
            ticker, entry_price, current_price, entry_date,
            alert_threshold=0.04,  # 4% alert
            hard_stop=0.05  # 5% hard stop
        )

        if action == 'CIRCUIT_BREAKER':
            # Hard stop - immediate exit
            print(f"  🔴 CIRCUIT BREAKER: {ticker} | Loss: {analysis['loss_pct']:.2f}%")

            # Format and send message
            msg = format_circuit_breaker_message(ticker, analysis)
            send_telegram_message(msg)

            # Execute exit
            portfolio.loc[portfolio['Ticker'] == ticker, 'Status'] = 'SOLD'

            # Record trade
            # from scripts.trade_recorder import record_trade
            # record_trade(
            #     ticker=ticker,
            #     signal='SELL',
            #     price=current_price,
            #     quantity=qty,
            #     notes=f"Circuit breaker at {analysis['loss_pct']:.2f}%"
            # )

            print(f"  ✅ Position exited: {ticker}")

        elif action == 'ALERT':
            # 4% alert - investigate
            print(f"  ⚠️ ALERT: {ticker} | Loss: {analysis['loss_pct']:.2f}%")

            # Analyze drop reason
            drop_analysis = analyze_drop_reason(ticker)

            # Get AI analysis
            ai_analysis = None
            try:
                ai_analysis = analyze_position_with_ai(
                    ticker, entry_price, current_price, entry_date
                )
            except Exception as e:
                print(f"    ⚠️ AI analysis failed: {e}")

            # Format alert message
            from scripts.risk_manager import format_alert_message
            msg = format_alert_message(ticker, analysis, drop_analysis, ai_analysis)
            send_telegram_message(msg)

print("✅ Circuit breaker check complete\n")

# Calculate portfolio metrics
metrics = calculate_position_metrics(portfolio, stock_data)

# Get today's trades
trades_df = pd.read_csv("data/trades.csv") if os.path.exists("data/trades.csv") else pd.DataFrame()
today = datetime.now().strftime("%Y-%m-%d")
today_trades_df = trades_df[trades_df['Date'] == today] if not trades_df.empty else pd.DataFrame()

# Format and send daily report
portfolio_summary = format_portfolio_summary(metrics)
trades_summary = format_trades_today(today_trades_df)
signals_summary = format_signals(signals_generated)

send_daily_report(portfolio_summary, trades_summary, signals_summary, strategy="DAILY")

# Print summary
print(f"\n{'='*70}")
print("📊 DAILY SUMMARY")
print(f"{'='*70}")
print(f"Signals Generated: {len(signals_generated)}")
print(f"Stocks Filtered by RS < {MIN_RS_RATING}: {rs_filtered_count}")
print(f"Trades Executed: {len(today_trades_df)}")
print(f"Active Positions: {metrics['total_positions']}")
print(f"Portfolio P&L: ₹{metrics['total_unrealized_pnl']:,.2f}")
print(f"{'='*70}")
print("✅ Daily trading complete!")
print(f"{'='*70}\n")
