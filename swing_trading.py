#!/usr/bin/env python3
"""
swing_trading.py - Daily swing trading system

Runs once per day at market close (4 PM IST)
- Scans watchlist for swing trade setups (2-7 day holds)
- Uses daily candles (not intraday)
- Manages existing positions (check TP/SL/trailing)
- Sends Telegram updates

Strategy:
- Target: 4% profit
- Stop: 2% loss
- Trailing: 1% once in profit
- Max hold: 10 days
- Max positions: 7

Separate from daily_trading.py (which trades intraday)
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(__file__))

from scripts.data_loader import load_data
from scripts.signal_generator_swing import generate_signal_swing
from scripts.portfolio_manager import get_stock_category
from scripts.pre_execution_checks import should_execute_trade, save_check_results
from scripts.risk_manager import check_circuit_breaker, analyze_drop_reason, format_alert_message, format_circuit_breaker_message
from scripts.telegram_bot import check_if_position_on_hold
from scripts.rs_rating import RelativeStrengthAnalyzer
import yfinance as yf

# Configuration
ACCOUNT_SIZE = 1000000  # ₹10 Lakh (separate from daily trading)
MAX_POSITIONS = 7
MAX_POSITION_PCT = 0.14  # 14% per position
MIN_SIGNAL_SCORE = 65  # Raised from 60 to be more selective
MIN_RS_RATING = 65  # NEW: Minimum Relative Strength rating (1-99 scale)
TARGET_PROFIT_PCT = 0.04  # 4%
STOP_LOSS_PCT = 0.02  # 2%
TRAILING_STOP_PCT = 0.01  # 1%
MAX_HOLD_DAYS = 10

# Files (separate from daily_trading)
SWING_PORTFOLIO_FILE = 'data/swing_portfolio.json'
SWING_TRADES_FILE = 'data/swing_trades.csv'
SWING_LOG_FILE = 'logs/swing_trading.log'

# Stock universe (liquid stocks - NSE + BSE)
STOCK_UNIVERSE = {
    'large_caps': [
        'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
        'BHARTIARTL.NS', 'SBIN.NS', 'BAJFINANCE.NS', 'HINDUNILVR.NS', 'KOTAKBANK.NS',
        'LT.NS', 'ITC.NS', 'ASIANPAINT.NS', 'AXISBANK.NS', 'MARUTI.NS',
        'SUNPHARMA.NS', 'TITAN.NS', 'ULTRACEMCO.NS', 'TATAMOTORS.NS',
        'WIPRO.NS', 'HCLTECH.NS', 'TECHM.NS', 'POWERGRID.NS', 'NTPC.NS',
        'COALINDIA.NS', 'TATASTEEL.NS', 'ONGC.NS', 'HINDALCO.NS',
        'JSWSTEEL.NS', 'BAJAJFINSV.NS', 'HEROMOTOCO.NS', 'INDUSINDBK.NS', 'BRITANNIA.NS',
        'APOLLOHOSP.NS', 'DIVISLAB.NS', 'DRREDDY.NS', 'CIPLA.NS',
        'TATACONSUM.NS', 'GRASIM.NS', 'SBILIFE.NS', 'HDFCLIFE.NS', 'BAJAJ-AUTO.NS',
        'ADANIPORTS.NS', 'BPCL.NS', 'M&M.NS', 'SHRIRAMFIN.NS', 'LTIM.NS'
    ],
    'mid_caps': [
        'PERSISTENT.NS', 'COFORGE.NS', 'MPHASIS.NS', 'LTTS.NS', 'CYIENT.NS',
        'ZYDUSLIFE.NS', 'TORNTPHARM.NS', 'AUROPHARMA.NS', 'LUPIN.NS',
        'LALPATHLAB.NS', 'METROPOLIS.NS', 'CROMPTON.NS', 'HAVELLS.NS', 'VGUARD.NS',
        'RELAXO.NS', 'BATAINDIA.NS', 'TRENT.NS', 'PIDILITIND.NS',
        'APLAPOLLO.NS', 'CENTURYPLY.NS', 'BLUEDART.NS',
        'KAJARIACER.NS', 'JKCEMENT.NS', 'RAMCOCEM.NS', 'ORIENTCEM.NS',
        'CHAMBLFERT.NS', 'DEEPAKNTR.NS', 'NAVINFLUOR.NS', 'SRF.NS',
        'TATAELXSI.BO', 'IPCALAB.BO', 'HONAUT.BO', 'ABBOTINDIA.BO'
    ],
    'micro_caps': [
        'FLUOROCHEM.NS', 'FINEORG.NS', 'GALAXYSURF.NS', 'ROSSARI.NS', 'ALKYLAMINE.NS',
        'SHARDACROP.NS', 'DCMSHRIRAM.NS',
        'TANLA.NS', 'KELLTONTEC.NS', 'MASTEK.NS',
        'ASTRAMICRO.NS', 'ELECON.NS', 'GREAVESCOT.NS', 'WHEELS.NS', 'RATNAMANI.NS',
        'GOCOLORS.NS', 'SMSLIFE.NS',
        'SUVEN.NS', 'AARTIDRUGS.NS', 'THYROCARE.NS',
        'DIGISPICE.NS', 'RPPINFRA.NS', 'RAJRATAN.NS', 'APLLTD.NS', 'GRINDWELL.NS',
        'SYMPHONY.BO', 'SONATSOFTW.BO'
    ]
}

def log(msg):
    """Log to console and file"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)

    os.makedirs('logs', exist_ok=True)
    with open(SWING_LOG_FILE, 'a') as f:
        f.write(log_msg + '\n')

def load_portfolio():
    """Load swing portfolio from file"""
    if not os.path.exists(SWING_PORTFOLIO_FILE):
        return pd.DataFrame(columns=[
            'Ticker', 'EntryDate', 'EntryPrice', 'Quantity',
            'StopLoss', 'TakeProfit', 'HighestPrice', 'DaysHeld', 'Category'
        ])

    try:
        with open(SWING_PORTFOLIO_FILE, 'r') as f:
            data = json.load(f)
        return pd.DataFrame(data)
    except:
        return pd.DataFrame(columns=[
            'Ticker', 'EntryDate', 'EntryPrice', 'Quantity',
            'StopLoss', 'TakeProfit', 'HighestPrice', 'DaysHeld', 'Category'
        ])

def save_portfolio(portfolio):
    """Save swing portfolio to file"""
    os.makedirs('data', exist_ok=True)
    portfolio_dict = portfolio.to_dict('records')
    with open(SWING_PORTFOLIO_FILE, 'w') as f:
        json.dump(portfolio_dict, f, indent=2)

def log_trade(trade_data):
    """Append trade to CSV"""
    os.makedirs('data', exist_ok=True)

    df = pd.DataFrame([trade_data])

    if os.path.exists(SWING_TRADES_FILE):
        df.to_csv(SWING_TRADES_FILE, mode='a', header=False, index=False)
    else:
        df.to_csv(SWING_TRADES_FILE, index=False)

def get_trading_capital():
    """Get current trading capital (profit-protected)"""
    try:
        with open('data/swing_capital_tracker.json') as f:
            cap = json.load(f)
        return cap['current_trading_capital']
    except:
        return ACCOUNT_SIZE

def get_cash():
    """Calculate available cash (current_capital - invested)"""
    portfolio = load_portfolio()
    account_size = get_trading_capital()

    if portfolio.empty:
        return account_size

    invested = 0
    for _, row in portfolio.iterrows():
        invested += float(row['EntryPrice']) * int(row['Quantity'])

    return account_size - invested

def check_exits(portfolio, stock_data, current_date):
    """Check and execute exits for all positions (with circuit breaker)"""
    from scripts.telegram_bot import send_telegram_message

    exits = []

    for idx, row in portfolio.iterrows():
        ticker = row['Ticker']
        entry_price = float(row['EntryPrice'])
        entry_date = pd.to_datetime(row['EntryDate'])
        qty = int(row['Quantity'])
        stop_loss = float(row['StopLoss'])
        take_profit = float(row['TakeProfit'])
        highest_price = float(row.get('HighestPrice', entry_price))
        days_held = int(row.get('DaysHeld', 0))

        # Update days held
        days_held = (current_date - entry_date).days
        portfolio.at[idx, 'DaysHeld'] = days_held

        # CHECK MAX HOLD FIRST (doesn't need price data)
        if days_held >= MAX_HOLD_DAYS:
            # Force exit due to max hold period - use last known price
            if ticker in stock_data and len(stock_data[ticker]) > 0:
                current_price = float(stock_data[ticker]['Close'].iloc[-1])
            else:
                log(f"⚠️ {ticker}: MAX-HOLD reached but no price data - skipping exit check")
                continue

            pnl = (current_price - entry_price) * qty
            pnl_pct = ((current_price - entry_price) / entry_price) * 100

            exits.append({
                'Date': current_date.strftime('%Y-%m-%d'),
                'Ticker': ticker,
                'Action': 'SELL',
                'Price': current_price,
                'Qty': qty,
                'EntryPrice': entry_price,
                'PnL': pnl,
                'PnL%': pnl_pct,
                'DaysHeld': days_held,
                'Reason': 'MAX-HOLD',
                'Category': row.get('Category', 'Unknown')
            })

            log(f"⏰ MAX-HOLD: {ticker} @ ₹{current_price:.2f} | P&L: ₹{pnl:,.0f} ({pnl_pct:+.2f}%) | {days_held}d")
            log_trade(exits[-1])
            portfolio = portfolio[portfolio['Ticker'] != ticker]
            continue

        # Get current price
        if ticker not in stock_data or current_date not in stock_data[ticker].index:
            continue

        current_price = float(stock_data[ticker].loc[current_date, 'Close'])

        # Update highest price
        if current_price > highest_price:
            highest_price = current_price
            portfolio.at[idx, 'HighestPrice'] = highest_price

        # Calculate P&L
        pnl = (current_price - entry_price) * qty
        pnl_pct = ((current_price - entry_price) / entry_price) * 100

        # 🛡️ CIRCUIT BREAKER CHECK - Priority #1
        # Check if user has enabled smart-stop mode for this position
        from scripts.telegram_bot import check_if_smart_stop_mode

        if check_if_smart_stop_mode(ticker):
            # User chose smart-stop mode - skip circuit breaker, let smart stops decide
            log(f"🤖 {ticker}: Smart-stop mode active | Skipping circuit breaker")
            action = 'HOLD'  # Skip circuit breaker logic
        else:
            # Normal circuit breaker check
            action, loss, analysis = check_circuit_breaker(
                ticker, entry_price, current_price, entry_date,
                alert_threshold=0.03,  # 3% alert with AI analysis
                hard_stop=0.05  # 5% hard stop
            )

        if action == 'CIRCUIT_BREAKER':
            # Hard stop triggered - immediate exit
            log(f"🔴 CIRCUIT BREAKER: {ticker} | Loss: {pnl_pct:.2f}%")

            # Send Telegram alert
            try:
                msg = format_circuit_breaker_message(ticker, analysis)
                send_telegram_message(msg)
            except Exception as e:
                log(f"⚠️ Could not send circuit breaker alert: {e}")

            # Execute exit
            exits.append({
                'Date': current_date.strftime('%Y-%m-%d'),
                'Ticker': ticker,
                'Action': 'SELL',
                'Price': current_price,
                'Qty': qty,
                'EntryPrice': entry_price,
                'PnL': pnl,
                'PnL%': pnl_pct,
                'DaysHeld': days_held,
                'Reason': 'CIRCUIT-BREAKER',
                'Category': row.get('Category', 'Unknown')
            })

            log_trade(exits[-1])
            portfolio = portfolio[portfolio['Ticker'] != ticker]
            continue

        elif action == 'ALERT':
            # 3% loss - check if user already said to hold
            if check_if_position_on_hold(ticker):
                log(f"🚨 ALERT: {ticker} | Loss: {pnl_pct:.2f}% | Skipping (user marked HOLD)")
            else:
                # Send alert with analysis
                log(f"🚨 ALERT: {ticker} | Loss: {pnl_pct:.2f}% | Analyzing...")

                # Analyze why it's dropping (technical)
                drop_analysis = analyze_drop_reason(ticker)

                # Get AI analysis (news + technical)
                try:
                    from scripts.ai_news_analyzer import get_ai_recommendation
                    ai_analysis = get_ai_recommendation(
                        ticker, drop_analysis,
                        entry_price, current_price, pnl_pct
                    )
                except Exception as e:
                    log(f"⚠️ AI analysis failed: {e}")
                    ai_analysis = None

                # Send Telegram alert with AI
                try:
                    msg = format_alert_message(ticker, analysis, drop_analysis, ai_analysis)
                    send_telegram_message(msg)
                    log(f"📱 Alert sent | AI: {ai_analysis.get('ai_recommendation', 'N/A') if ai_analysis else 'N/A'}")
                except Exception as e:
                    log(f"⚠️ Could not send alert: {e}")

        # Recalculate smart stops dynamically (includes Chandelier trailing)
        from scripts.risk_manager import calculate_atr, calculate_smart_stops_swing

        # Get current data for ATR calculation
        if ticker in stock_data:
            df = stock_data[ticker]
            atr = calculate_atr(df, period=14)
            recent_low = float(df['Low'].tail(5).min()) if len(df) >= 5 else None

            # Recalculate smart stops with updated data
            smart_stops = calculate_smart_stops_swing(
                entry_price=entry_price,
                current_price=current_price,
                highest_price=highest_price,
                atr=atr,
                days_held=days_held,
                recent_low=recent_low
            )

            # Update stop loss to the new smart stop (which includes Chandelier trailing)
            new_stop = smart_stops['stop_loss']
            stop_loss = max(stop_loss, new_stop)  # Only tighten, never widen

            # Update in portfolio
            portfolio.at[idx, 'StopLoss'] = stop_loss

            log(f"  📊 {ticker}: Smart Stop=₹{stop_loss:.2f} (method: {smart_stops['method']}) | Current: ₹{current_price:.2f}")

        # Check normal exit conditions
        exit_reason = None

        if current_price <= stop_loss:
            exit_reason = f"SMART-SL-{smart_stops['method'].upper()}" if 'smart_stops' in locals() else "STOP-LOSS"
        elif current_price >= take_profit:
            exit_reason = "TAKE-PROFIT"
        elif 'smart_stops' in locals() and smart_stops.get('time_based_exit', False):
            exit_reason = "TIME-BASED"
        # NOTE: MAX-HOLD check moved to line 181 (before price data check)

        if exit_reason:
            # Execute exit
            exits.append({
                'Date': current_date.strftime('%Y-%m-%d'),
                'Ticker': ticker,
                'Action': 'SELL',
                'Price': current_price,
                'Qty': qty,
                'EntryPrice': entry_price,
                'PnL': pnl,
                'PnL%': pnl_pct,
                'DaysHeld': days_held,
                'Reason': exit_reason,
                'Category': row.get('Category', 'Unknown')
            })

            emoji = "🎯" if exit_reason == "TAKE-PROFIT" else "🛑" if "SL" in exit_reason else "⏰"
            log(f"{emoji} {exit_reason}: {ticker} @ ₹{current_price:.2f} | P&L: ₹{pnl:,.0f} ({pnl_pct:+.2f}%) | {days_held}d")

            # Log trade
            log_trade(exits[-1])

            # Remove from portfolio
            portfolio = portfolio[portfolio['Ticker'] != ticker]

    return portfolio, exits

def smart_scan_with_allocation(portfolio, current_date, cash):
    """Smart screening with 60/20/20 allocation across Large/Mid/Micro caps"""
    entries = []
    active_positions = len(portfolio)

    if active_positions >= MAX_POSITIONS:
        log(f"📊 Max positions reached ({MAX_POSITIONS}), skipping entry scan")
        return portfolio, entries

    if cash < (ACCOUNT_SIZE * MAX_POSITION_PCT):
        log(f"💰 Insufficient cash (₹{cash:,.0f}), skipping entry scan")
        return portfolio, entries

    # Phase 1: Screen all stocks for BUY signals
    log(f"🔍 Phase 1: Screening {sum(len(v) for v in STOCK_UNIVERSE.values())} stocks...")

    # Initialize RS Analyzer
    rs_analyzer = RelativeStrengthAnalyzer()

    candidates = {'large_caps': [], 'mid_caps': [], 'micro_caps': []}
    rs_filtered_count = 0

    for category, tickers in STOCK_UNIVERSE.items():
        for ticker in tickers:
            # Skip if already holding
            if not portfolio.empty and ticker in portfolio['Ticker'].values:
                continue

            try:
                # Download data
                df = yf.download(ticker, period='3mo', interval='1d', progress=False)

                if df.empty or len(df) < 50:
                    continue

                # NEW: RS Rating Filter (Pre-filter before expensive indicator calculations)
                rs_rating = rs_analyzer.calculate_rs_rating(ticker)
                if rs_rating < MIN_RS_RATING:
                    rs_filtered_count += 1
                    continue  # Skip weak stocks

                # Generate signal (only for stocks that passed RS filter)
                signal, score, details = generate_signal_swing(df, min_score=MIN_SIGNAL_SCORE)

                if signal == "BUY" and score >= MIN_SIGNAL_SCORE:
                    current_price = float(df['Close'].iloc[-1])

                    candidates[category].append({
                        'ticker': ticker,
                        'score': score,
                        'price': current_price,
                        'category': category,
                        'rs_rating': rs_rating  # Store RS rating for reference
                    })

                    log(f"  ✅ {ticker}: Score {score:.0f} | RS {rs_rating} | ₹{current_price:.2f}")

            except Exception as e:
                continue

    # Count candidates
    total_candidates = sum(len(v) for v in candidates.values())
    log(f"\n📊 Found {total_candidates} BUY signals:")
    log(f"  Large-caps: {len(candidates['large_caps'])}")
    log(f"  Mid-caps: {len(candidates['mid_caps'])}")
    log(f"  Stocks filtered by RS < {MIN_RS_RATING}: {rs_filtered_count}")
    log(f"  Micro-caps: {len(candidates['micro_caps'])}")

    if total_candidates == 0:
        log("❌ No BUY signals found")
        return portfolio, entries

    # Phase 2: Apply smart 60/20/20 allocation
    log(f"\n🔍 Phase 2: Smart allocation (60/20/20)...")

    # Calculate target positions (60% large, 20% mid, 20% micro)
    slots_available = MAX_POSITIONS - active_positions
    target_large = int(slots_available * 0.60)
    target_mid = int(slots_available * 0.20)
    target_micro = int(slots_available * 0.20)

    # Adjust for rounding
    if target_large + target_mid + target_micro < slots_available:
        target_large += (slots_available - target_large - target_mid - target_micro)

    # Apply fallback logic
    actual_large = min(target_large, len(candidates['large_caps']))
    actual_mid = min(target_mid, len(candidates['mid_caps']))
    actual_micro = min(target_micro, len(candidates['micro_caps']))

    shortfall = (target_large - actual_large) + (target_mid - actual_mid) + (target_micro - actual_micro)

    if shortfall > 0:
        log(f"⚠️  Shortfall: {shortfall} positions, redistributing...")
        # Redistribute to mid first, then large
        if actual_mid < len(candidates['mid_caps']):
            can_add = min(len(candidates['mid_caps']) - actual_mid, shortfall)
            actual_mid += can_add
            shortfall -= can_add
            log(f"  +{can_add} to mid-caps")

        if shortfall > 0 and actual_large < len(candidates['large_caps']):
            can_add = min(len(candidates['large_caps']) - actual_large, shortfall)
            actual_large += can_add
            shortfall -= can_add
            log(f"  +{can_add} to large-caps")

    log(f"Final allocation: {actual_large} large / {actual_mid} mid / {actual_micro} micro")

    # Calculate capital per position using AVAILABLE CASH (not total capital)
    # Bug fix: Was using get_trading_capital() which caused over-allocation
    account_size = get_cash()  # Available cash = capital - invested
    capital_large = (account_size * 0.60) / actual_large if actual_large > 0 else 0
    capital_mid = (account_size * 0.20) / actual_mid if actual_mid > 0 else 0
    capital_micro = (account_size * 0.20) / actual_micro if actual_micro > 0 else 0

    # Phase 3: Select positions and run pre-execution checks
    log(f"\n🔍 Phase 3: Selecting positions with intelligence checks...")

    allocation_map = {
        'large_caps': (actual_large, capital_large),
        'mid_caps': (actual_mid, capital_mid),
        'micro_caps': (actual_micro, capital_micro)
    }

    for category, (num_positions, capital_per_pos) in allocation_map.items():
        if num_positions == 0:
            continue

        # Sort by score and take top N
        sorted_candidates = sorted(candidates[category], key=lambda x: x['score'], reverse=True)

        for candidate in sorted_candidates[:num_positions]:
            ticker = candidate['ticker']
            price = candidate['price']
            score = candidate['score']

            # Pre-execution checks
            log(f"\n  🔍 Checking {ticker}...")
            should_proceed, check_results = should_execute_trade(ticker, "BUY")
            save_check_results(ticker, check_results, should_proceed)

            if not should_proceed:
                log(f"  🚫 BLOCKED: {ticker} due to risk factors")
                continue

            log(f"  ✅ Approved: {ticker}")

            # Calculate position size
            qty = int(capital_per_pos // price)

            if qty == 0:
                continue

            actual_investment = qty * price

            # Calculate smart hybrid stops (ATR + Fixed + Chandelier)
            from scripts.risk_manager import calculate_atr, calculate_smart_stops_swing

            # Get ATR for this stock
            atr = calculate_atr(df, period=14)

            # Calculate recent 5-day low for support stop
            recent_low = float(df['Low'].tail(5).min()) if len(df) >= 5 else None

            # Get smart stops
            smart_stops = calculate_smart_stops_swing(
                entry_price=price,
                current_price=price,
                highest_price=price,
                atr=atr,
                days_held=0,
                recent_low=recent_low
            )

            take_profit = smart_stops['take_profit']
            stop_loss = smart_stops['stop_loss']

            log(f"  📊 Smart Stops: SL=₹{stop_loss:.2f} (method: {smart_stops['method']}) | TP=₹{take_profit:.2f}")
            log(f"     All stops: {smart_stops['all_stops']}")

            # Determine category label
            cat_label = category.replace('_caps', '').capitalize() + '-cap'

            # Add to portfolio
            new_position = {
                'Ticker': ticker,
                'EntryDate': current_date.strftime('%Y-%m-%d'),
                'EntryPrice': price,
                'Quantity': qty,
                'StopLoss': stop_loss,
                'TakeProfit': take_profit,
                'HighestPrice': price,
                'DaysHeld': 0,
                'Category': cat_label
            }

            portfolio = pd.concat([portfolio, pd.DataFrame([new_position])], ignore_index=True)
            cash -= actual_investment

            # Log entry
            entries.append({
                'Date': current_date.strftime('%Y-%m-%d'),
                'Ticker': ticker,
                'Action': 'BUY',
                'Price': price,
                'Qty': qty,
                'EntryPrice': price,
                'PnL': 0,
                'PnL%': 0,
                'DaysHeld': 0,
                'Reason': f'Score {score:.0f}',
                'Category': cat_label
            })

            log(f"  ✅ ENTERED: {ticker} @ ₹{price:.2f} | Qty: {qty} | {cat_label}")
            log_trade(entries[-1])

    return portfolio, entries

def send_telegram_summary(portfolio, exits, entries, total_pnl):
    """Send Telegram notification with swing trading summary"""
    try:
        from scripts.telegram_bot import send_telegram_message

        msg = "📈 *SWING TRADING - Daily Update*\n\n"
        msg += f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"

        # Exits
        if exits:
            msg += f"*Exits Today ({len(exits)}):*\n"
            for exit in exits:
                emoji = "🎯" if exit['Reason'] == "TAKE-PROFIT" else "🛑"
                msg += f"{emoji} {exit['Ticker']}: ₹{exit['PnL']:,.0f} ({exit['PnL%']:+.2f}%) | {exit['DaysHeld']}d\n"
            msg += "\n"

        # Entries
        if entries:
            msg += f"*New Positions ({len(entries)}):*\n"
            for entry in entries:
                msg += f"✅ {entry['Ticker']}: ₹{entry['Price']:.2f} × {entry['Qty']} | {entry['Category']}\n"
            msg += "\n"

        # Current portfolio with unrealized P&L
        total_unrealized_pnl = 0
        if not portfolio.empty:
            msg += f"*Open Positions ({len(portfolio)}):*\n"
            for _, row in portfolio.iterrows():
                ticker = row['Ticker']
                days = int(row['DaysHeld'])
                entry_price = float(row['EntryPrice'])
                qty = int(row['Quantity'])

                # Fetch current price
                try:
                    df = yf.download(ticker, period='1d', interval='1d', progress=False)
                    if not df.empty:
                        current_price = float(df['Close'].iloc[-1])

                        # Calculate unrealized P&L
                        unrealized_pnl = (current_price - entry_price) * qty
                        unrealized_pnl_pct = ((current_price - entry_price) / entry_price) * 100
                        total_unrealized_pnl += unrealized_pnl

                        # Format with emoji based on profit/loss
                        pnl_emoji = "🟢" if unrealized_pnl >= 0 else "🔴"
                        msg += f"📌 {ticker}: {days}d | {row['Category']}\n"
                        msg += f"   Entry: ₹{entry_price:.2f} | Now: ₹{current_price:.2f} | {pnl_emoji} ₹{unrealized_pnl:,.0f} ({unrealized_pnl_pct:+.2f}%)\n"
                    else:
                        msg += f"📌 {ticker}: {days}d | {row['Category']} | Price N/A\n"
                except Exception as e:
                    log(f"⚠️ Could not fetch price for {ticker}: {e}")
                    msg += f"📌 {ticker}: {days}d | {row['Category']} | Price N/A\n"

            msg += "\n"

        # Summary
        cash = get_cash()
        account_size = get_trading_capital()
        invested = account_size - cash
        msg += f"*Portfolio:*\n"
        msg += f"💰 Cash: ₹{cash:,.0f}\n"
        msg += f"📊 Invested: ₹{invested:,.0f}\n"

        # Show unrealized P&L if there are open positions
        if not portfolio.empty and total_unrealized_pnl != 0:
            unrealized_pct = (total_unrealized_pnl / invested * 100) if invested > 0 else 0
            pnl_emoji = "🟢" if total_unrealized_pnl >= 0 else "🔴"
            msg += f"{pnl_emoji} Unrealized P&L: ₹{total_unrealized_pnl:,.0f} ({unrealized_pct:+.2f}%)\n"

        if total_pnl != 0:
            msg += f"📈 Today's Realized P&L: ₹{total_pnl:,.0f}\n"

        send_telegram_message(msg)
        log("✅ Telegram notification sent")

    except Exception as e:
        log(f"⚠️ Could not send Telegram: {e}")

def main():
    """Main swing trading workflow"""
    log("="*80)
    log("📊 SWING TRADING - Smart Allocation System")
    log("="*80)

    # Get current date
    current_date = pd.Timestamp.now()
    log(f"📅 Trading date: {current_date.date()}")

    # Load portfolio
    portfolio = load_portfolio()
    log(f"📊 Current positions: {len(portfolio)}")

    # 1. Check exits (if we have positions)
    exits = []
    if not portfolio.empty:
        log("\n🔍 Checking exits...")
        # For exits, we need to load data for stocks in portfolio
        portfolio_tickers = portfolio['Ticker'].unique().tolist()
        log(f"📥 Loading data for {len(portfolio_tickers)} positions...")

        stock_data = {}
        for ticker in portfolio_tickers:
            try:
                df = yf.download(ticker, period='1mo', interval='1d', progress=False)
                if not df.empty:
                    stock_data[ticker] = df
            except:
                continue

        portfolio, exits = check_exits(portfolio, stock_data, current_date)

        if exits:
            log(f"✅ Executed {len(exits)} exits")
        else:
            log("ℹ️ No exits today")
    else:
        log("\nℹ️ No open positions, skipping exit checks")

    # 2. Smart scan for entries with 60/20/20 allocation
    log("\n🔍 Smart Screening with 60/20/20 Allocation...")
    cash = get_cash()
    log(f"💰 Available cash: ₹{cash:,.0f}")

    portfolio, entries = smart_scan_with_allocation(portfolio, current_date, cash)

    if entries:
        log(f"\n✅ Entered {len(entries)} new positions")
    else:
        log("\nℹ️ No new entries today")

    # Save portfolio
    save_portfolio(portfolio)
    log(f"\n💾 Portfolio saved: {len(portfolio)} positions")

    # Calculate total P&L for today
    total_pnl = sum(exit['PnL'] for exit in exits)

    # Send Telegram summary
    log("\n📱 Sending Telegram update...")
    send_telegram_summary(portfolio, exits, entries, total_pnl)

    # Summary
    log("\n" + "="*80)
    log("📊 SUMMARY")
    log("="*80)
    log(f"Exits: {len(exits)}")
    log(f"Entries: {len(entries)}")
    log(f"Open Positions: {len(portfolio)}")
    log(f"Cash: ₹{get_cash():,.0f}")
    if total_pnl != 0:
        log(f"Today's P&L: ₹{total_pnl:,.0f}")
    log("="*80)
    log("✅ Swing trading run complete!")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"❌ ERROR: {e}")
        import traceback
        log(traceback.format_exc())
        sys.exit(1)
