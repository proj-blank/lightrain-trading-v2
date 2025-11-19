#!/usr/bin/env python3
"""
swing_trading.py - Daily swing trading system (PostgreSQL + NSE Universe version)

Runs once per day at market close (4 PM IST)
- Scans NSE universe for swing trade setups (2-7 day holds)
- Uses daily candles (not intraday)
- Manages existing positions (check TP/SL/trailing)
- Sends Telegram updates

Strategy:
- Target: 4% profit
- Stop: 2% loss
- Trailing: 1% once in profit
- Max hold: 10 days
- Max positions: 7
- 60/20/20 allocation (Large/Mid/Micro caps)

Separate from daily_trading.py (which trades intraday)
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add LightRain path for db_connection
sys.path.insert(0, '/home/ubuntu/trading')
sys.path.append(os.path.dirname(__file__))

# Database imports
from scripts.db_connection import (
    get_active_positions, add_position, close_position, log_trade,
    get_capital, update_capital, get_available_cash,
    is_position_on_hold, add_circuit_breaker_hold,
    get_db_cursor, debit_capital, credit_capital
)

# Trading logic imports
from scripts.signal_generator_swing import generate_signal_swing
from scripts.portfolio_manager import get_stock_category
from scripts.pre_execution_checks import should_execute_trade, save_check_results
from scripts.risk_manager import check_circuit_breaker, analyze_drop_reason, format_alert_message, format_circuit_breaker_message
from scripts.telegram_bot import check_if_position_on_hold
from scripts.rs_rating import RelativeStrengthAnalyzer
from scripts.percentage_based_allocation import calculate_percentage_allocation, select_positions_for_entry
from scripts.angelone_price_fetcher import get_live_price
import yfinance as yf

# Configuration
ACCOUNT_SIZE = 500000  # ₹5 Lakh (separate from daily trading, ₹500K each for daily+swing)
# NO MAX_POSITIONS - using percentage-based allocation (60/20/20 split)
MAX_POSITION_PCT = 0.14  # 14% per position
MIN_SIGNAL_SCORE = 65  # Raised from 60 to be more selective
MIN_RS_RATING = 65  # Minimum Relative Strength rating (1-99 scale)
TARGET_PROFIT_PCT = 0.04  # 4%
STOP_LOSS_PCT = 0.02  # 2%
TRAILING_STOP_PCT = 0.01  # 1%
MAX_HOLD_DAYS = 10
STRATEGY = 'SWING'

# Log file
SWING_LOG_FILE = 'logs/swing_trading.log'

def log(msg):
    """Log to console and file"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)

    os.makedirs('logs', exist_ok=True)
    with open(SWING_LOG_FILE, 'a') as f:
        f.write(log_msg + '\n')

def load_portfolio():
    """Load swing portfolio from database"""
    positions = get_active_positions(STRATEGY)

    if not positions:
        return pd.DataFrame(columns=[
            'Ticker', 'EntryDate', 'EntryPrice', 'Quantity',
            'StopLoss', 'TakeProfit', 'HighestPrice', 'DaysHeld', 'Category'
        ])

    # Convert to DataFrame with expected columns
    df_data = []
    for pos in positions:
        df_data.append({
            'Ticker': pos['ticker'],
            'EntryDate': pos['entry_date'].strftime('%Y-%m-%d') if hasattr(pos['entry_date'], 'strftime') else str(pos['entry_date']),
            'EntryPrice': float(pos['entry_price']),
            'Quantity': int(pos['quantity']),
            'StopLoss': float(pos['stop_loss']),
            'TakeProfit': float(pos['take_profit']),
            'HighestPrice': float(pos.get('highest_price', pos['entry_price'])),
            'DaysHeld': int(pos.get('days_held', 0)),
            'Category': pos.get('category', 'Unknown')
        })

    return pd.DataFrame(df_data)

def save_portfolio(portfolio):
    """Save portfolio handled by database operations during trading"""
    # No-op: Portfolio changes are saved via add_position() and close_position()
    # This function kept for compatibility with existing code flow
    pass

def log_trade_record(trade_data):
    """Log trade to database"""
    log_trade(
        ticker=trade_data['Ticker'],
        strategy=STRATEGY,
        signal=trade_data['Action'],
        price=float(trade_data['Price']),
        quantity=int(trade_data['Qty']),
        pnl=float(trade_data.get('PnL', 0)),
        notes=trade_data.get('Reason', ''),
        category=trade_data.get('Category', None)
    )

def get_trading_capital():
    """Get current trading capital (profit-protected)"""
    capital = get_capital(STRATEGY)
    if capital:
        return float(capital['current_trading_capital'])
    return ACCOUNT_SIZE

def get_cash():
    """Calculate available cash from database"""
    return get_available_cash(STRATEGY)

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
        # Note: Day-before warnings now handled by check_max_hold_warnings.py at 3 PM
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

            # Send telegram alert
            pnl_emoji = "🟢" if pnl >= 0 else "🔴"
            from scripts.telegram_bot import send_telegram_message
            send_telegram_message(
                f"{pnl_emoji} <b>MAX-HOLD EXIT</b>\n\n"
                f"📊 Ticker: {ticker} ({STRATEGY})\n"
                f"⏰ Reason: Held {days_held} days (max: {MAX_HOLD_DAYS})\n"
                f"💰 P&L: ₹{pnl:,.0f} ({pnl_pct:+.2f}%)\n\n"
                f"<i>Freeing capital for new opportunities</i>"
            )

            # Log to database and close position
            log_trade_record(exits[-1])
            close_position(ticker, STRATEGY, current_price, pnl)

            # Credit back the original investment
            original_investment = entry_price * qty
            credit_capital(STRATEGY, original_investment)

            # Update capital with P&L
            update_capital(STRATEGY, pnl)

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

            # Log to database and close position
            log_trade_record(exits[-1])
            close_position(ticker, STRATEGY, current_price, pnl)

            # Credit back the original investment
            original_investment = entry_price * qty
            credit_capital(STRATEGY, original_investment)

            # Update capital with P&L
            update_capital(STRATEGY, pnl)

            portfolio = portfolio[portfolio['Ticker'] != ticker]
            continue

        elif action == 'ALERT':
            # 3% loss - check if user already said to hold
            if check_if_position_on_hold(ticker) or is_position_on_hold(ticker, STRATEGY):
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

            # Log to database and close position
            log_trade_record(exits[-1])
            close_position(ticker, STRATEGY, current_price, pnl)

            # Credit back the original investment
            original_investment = entry_price * qty
            credit_capital(STRATEGY, original_investment)

            # Update capital with P&L
            update_capital(STRATEGY, pnl)

            # Remove from portfolio
            portfolio = portfolio[portfolio['Ticker'] != ticker]

    return portfolio, exits

def smart_scan_with_allocation(portfolio, current_date, cash, regime_multiplier=1.0):
    """Percentage-based screening with 60/20/20 capital allocation (NO FIXED POSITION COUNTS)"""
    entries = []
    active_positions = len(portfolio)

    # No MAX_POSITIONS check - using percentage-based allocation
    if cash < 20000:  # Minimum ₹20K needed for at least 1 position
        log(f"💰 Insufficient cash (₹{cash:,.0f}), skipping entry scan")
        return portfolio, entries

    # Load stock universe from database
    log(f"🔍 Phase 1: Loading NSE universe from database...")
    stock_universe = {'large_caps': [], 'mid_caps': [], 'micro_caps': []}

    try:
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT ticker, category
                FROM screened_stocks
                WHERE last_updated = CURRENT_DATE
                ORDER BY category, ticker
            """)
            results = cur.fetchall()

            if not results:
                log("❌ No stocks found in screened_stocks table for today")
                return portfolio, entries

            # Group by category
            category_map = {
                'Large-cap': 'large_caps',
                'Mid-cap': 'mid_caps',
                'Micro-cap': 'micro_caps'
            }

            for row in results:
                ticker = row['ticker']
                category = row['category']
                allocation_category = category_map.get(category)

                if allocation_category:
                    stock_universe[allocation_category].append(ticker)

            total_stocks = sum(len(v) for v in stock_universe.values())
            log(f"✅ Loaded {total_stocks} stocks from NSE universe")
            log(f"   Large-caps: {len(stock_universe['large_caps'])}")
            log(f"   Mid-caps: {len(stock_universe['mid_caps'])}")
            log(f"   Micro-caps: {len(stock_universe['micro_caps'])}")

    except Exception as e:
        log(f"❌ Failed to load stocks from database: {e}")
        return portfolio, entries

    # Screen all stocks for BUY signals
    log(f"\n🔍 Phase 2: Screening stocks for BUY signals...")

    # Initialize RS Analyzer
    rs_analyzer = RelativeStrengthAnalyzer()

    candidates = {'large_caps': [], 'mid_caps': [], 'micro_caps': []}
    rs_filtered_count = 0

    for category, tickers in stock_universe.items():
        for ticker in tickers:
            # Skip if already holding
            if not portfolio.empty and ticker in portfolio['Ticker'].values:
                continue

            try:
                # Download data
                df = yf.download(ticker, period='3mo', interval='1d', progress=False)

                # Flatten MultiIndex columns if present (yfinance bug fix)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                if df.empty or len(df) < 50:
                    continue

                # RS Rating Filter (Pre-filter before expensive indicator calculations)
                rs_rating = rs_analyzer.calculate_rs_rating(ticker)
                if rs_rating < MIN_RS_RATING:
                    rs_filtered_count += 1
                    continue  # Skip weak stocks

                # Generate signal (only for stocks that passed RS filter)
                print(f"DEBUG: Generating signal for {ticker} (RS={rs_rating})")
                signal, score, details = generate_signal_swing(df, min_score=MIN_SIGNAL_SCORE)
                print(f"DEBUG: {ticker} -> Signal={signal}, Score={score:.1f}")

                # DEBUG: Log ALL scores for RS-filtered stocks (temporary)
                with open('/home/ubuntu/trading/logs/swing_scores_debug.txt', 'a') as f:
                    f.write(f"{ticker}|{signal}|{score:.1f}|{rs_rating}\n")

                if signal == "BUY" and score >= MIN_SIGNAL_SCORE:
                    current_price = float(df['Close'].iloc[-1])

                    # Validate price is a number
                    if not isinstance(current_price, (int, float)):
                        log(f"  ⚠️ Skipping {ticker}: Invalid price type {type(current_price)}")
                        continue
                    
                    candidates[category].append({
                        'ticker': ticker,
                        'score': score,
                        'price': float(current_price),  # Ensure float
                        'category': category,
                        'rs_rating': rs_rating,  # Store RS rating for reference
                        'df': df  # Store dataframe for later use
                    })

                    log(f"  ✅ {ticker}: Score {score:.0f} | RS {rs_rating} | ₹{current_price:.2f}")

            except Exception as e:
                print(f"ERROR processing {ticker}: {e}")
                continue

    # Count candidates
    total_candidates = sum(len(v) for v in candidates.values())
    log(f"\n📊 Found {total_candidates} BUY signals:")
    log(f"  Large-caps: {len(candidates['large_caps'])}")
    log(f"  Mid-caps: {len(candidates['mid_caps'])}")
    log(f"  Micro-caps: {len(candidates['micro_caps'])}")
    log(f"  Stocks filtered by RS < {MIN_RS_RATING}: {rs_filtered_count}")

    if total_candidates == 0:
        log("❌ No BUY signals found")
        return portfolio, entries

    # Phase 3: Apply percentage-based 60/20/20 allocation (NO FIXED POSITION COUNTS)
    log(f"\n🔍 Phase 3: Percentage-based allocation (60/20/20)...")

    # Calculate percentage-based allocation using available cash
    account_size = get_cash()  # Available cash = capital - invested

    allocation_plan = calculate_percentage_allocation(
        candidates,
        total_capital=account_size * regime_multiplier,  # Apply regime-based position sizing
        target_allocation={'large': 0.60, 'mid': 0.20, 'micro': 0.20},
        min_position_size=20000,  # Min ₹20K per position
        max_position_size=100000,  # Max ₹100K per position (swing holds longer, smaller sizes)
        min_score=MIN_SIGNAL_SCORE,
        min_rs_rating=MIN_RS_RATING
    )

    # Get selected positions from allocation plan
    selected_positions_list = select_positions_for_entry(allocation_plan)

    # Phase 4: Execute selected positions with pre-execution checks
    log(f"\n🔍 Phase 4: Executing {len(selected_positions_list)} selected positions...")

    for position in selected_positions_list:
        ticker = position['ticker']
        yahoo_price = float(position["price"])  # Ensure float conversion
        score = position['score']
        capital_allocated = position['capital_allocated']
        df = position['df']

        # Get live price from AngelOne (with Yahoo fallback)
        price, price_source = get_live_price(ticker, yahoo_price)
        log(f"  💰 {ticker}: ₹{price:.2f} ({price_source.upper()})")

        # Pre-execution checks
        log(f"\n  🔍 Checking {ticker}...")
        should_proceed, check_results = should_execute_trade(ticker, "BUY")
        save_check_results(ticker, check_results, should_proceed)

        if not should_proceed:
            log(f"  🚫 BLOCKED: {ticker} due to risk factors")
            continue

        log(f"  ✅ Approved: {ticker}")

        # Calculate position size
        qty = int(capital_allocated // price)

        if qty == 0:
            continue

        actual_investment = qty * price

        # Calculate smart hybrid stops (ATR + Fixed + Chandelier)
        from scripts.risk_manager import calculate_atr, calculate_smart_stops_swing

        # Get ATR for this stock (need to download data again)
        df = yf.download(ticker, period='3mo', interval='1d', progress=False)

        # Flatten MultiIndex columns if present (yfinance bug fix)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

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

        # Get category label from position
        cat_label = position.get('category', 'Unknown')

        # Get AI validation BEFORE adding position (Claude 3 Haiku)
        ai_agrees = None
        ai_confidence = None
        ai_reasoning = None
        try:
            from scripts.ai_validator import validate_position, get_verdict_emoji
            from scripts.telegram_bot import send_telegram_message

            ai_result = validate_position(
                ticker=ticker,
                entry_price=price,
                technical_score=score,
                rs_rating=position.get('rs_rating', 50),
                indicators_fired=position.get('indicators_fired', []),
                df=df
            )

            ai_agrees = ai_result.get('agrees')
            ai_confidence = ai_result.get('confidence')
            ai_reasoning = ai_result.get('reasoning')

            # Send AI opinion to Telegram
            emoji = get_verdict_emoji(ai_result['verdict'])
            ticker_clean = ticker.replace('.NS', '')
            ai_msg = f"  🤖 AI for {ticker_clean}: {emoji} {ai_result['verdict']} ({ai_result['confidence']:.0%}) - {ai_result['reasoning']}"
            send_telegram_message(ai_msg)

            log(f"  🤖 AI Opinion: {ai_result['verdict']} ({ai_result['confidence']:.0%})")

        except Exception as ai_error:
            log(f"  ⚠️ AI validation failed: {ai_error}")
            # Continue with default values

        # Add to database with AI validation data
        try:
            add_position(
                ticker=ticker,
                strategy=STRATEGY,
                entry_price=price,
                quantity=qty,
                stop_loss=stop_loss,
                take_profit=take_profit,
                category=cat_label,
                entry_date=current_date.strftime('%Y-%m-%d'),
                ai_agrees=ai_agrees,
                ai_confidence=ai_confidence,
                ai_reasoning=ai_reasoning
            )

            # Debit capital for this position
            position_cost = price * qty
            debit_capital(STRATEGY, position_cost)

        except Exception as e:
            log(f"  ❌ Failed to add position to database: {e}")
            continue

        # Add to portfolio DataFrame for current session
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
        log_trade_record(entries[-1])

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

                    # Flatten MultiIndex columns if present (yfinance bug fix)
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)

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
    log("📊 SWING TRADING - Smart Allocation System (PostgreSQL + NSE Universe)")
    log("="*80)

    # Get current date
    current_date = pd.Timestamp.now()
    log(f"📅 Trading date: {current_date.date()}")

    # Check for KILL SWITCH halt flag
    halt_file = '/home/ubuntu/trading/data/trading_halted.flag'
    if os.path.exists(halt_file):
        try:
            import json
            with open(halt_file, 'r') as f:
                halt_data = json.load(f)

            halt_date = halt_data.get('date', '')
            today_str = current_date.strftime('%Y-%m-%d')

            if halt_date == today_str:
                log(f"🚫 TRADING HALTED BY KILL SWITCH")
                log(f"   Triggered: {halt_data.get('timestamp', 'Unknown')}")
                log(f"   Reason: {halt_data.get('reason', 'Unknown')}")

                from scripts.telegram_bot import send_telegram_message
                send_telegram_message(
                    f"🚫 SWING Trading Blocked\n\n"
                    f"Kill switch active since {halt_data.get('timestamp', 'Unknown')[:16]}\n"
                    f"Reason: {halt_data.get('reason', 'Kill switch')}\n\n"
                    f"Trading will resume tomorrow."
                )
                return
            else:
                # Halt expired, remove file
                os.remove(halt_file)
                log(f"✅ Removed expired halt flag from {halt_date}")
        except Exception as e:
            log(f"⚠️ Error reading halt file: {e}")
            # Continue trading on error to be safe

    # 🌍 Global Market Regime Check
    from global_market_filter import get_current_regime
    regime_data = get_current_regime()

    if regime_data:
        regime = regime_data['regime']
        regime_emoji = {'BULL': '🟢', 'NEUTRAL': '🟡', 'CAUTION': '🟠', 'BEAR': '🔴'}.get(regime, '⚪')
        log(f"{regime_emoji} Global Market Regime: {regime}")
        log(f"   Position Sizing Multiplier: {regime_data['position_sizing_multiplier']:.0%}")
        log(f"   New Entries Allowed: {regime_data['allow_new_entries']}")

        # Store regime multiplier for position sizing
        REGIME_MULTIPLIER = regime_data['position_sizing_multiplier']
        ALLOW_NEW_ENTRIES = regime_data['allow_new_entries']

        if regime == 'BEAR':
            log("⚠️  BEAR REGIME: No new positions will be taken today")
            log("⚠️  Consider tightening stops on existing positions")
    else:
        log("⚠️ No market regime data found (run global_market_filter.py at 8:30 AM)")
        REGIME_MULTIPLIER = 1.0  # Default to normal if no data
        ALLOW_NEW_ENTRIES = True


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

                # Flatten MultiIndex columns if present (yfinance bug fix)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

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
    entries = []

    # Check global regime before allowing new entries
    if not ALLOW_NEW_ENTRIES:
        log("\n⛔ BEAR REGIME: Skipping entry scan (allow_new_entries=False)")
        log("   Focus: Managing existing positions only")
    else:
        log("\n🔍 Smart Screening with 60/20/20 Allocation (NSE Universe)...")
        cash = get_cash()
        log(f"💰 Available cash: ₹{cash:,.0f}")

        portfolio, entries = smart_scan_with_allocation(portfolio, current_date, cash, REGIME_MULTIPLIER)

    if entries:
        log(f"\n✅ Entered {len(entries)} new positions")
    else:
        log("\nℹ️ No new entries today")

    # Portfolio saved via database operations
    log(f"\n💾 Portfolio in database: {len(portfolio)} positions")

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
