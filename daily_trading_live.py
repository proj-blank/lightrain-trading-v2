# daily_trading_live.py
"""
LIVE Daily automated trading script - Uses AngelOne API for data and order execution.
Capital: ₹10,000 | Max Positions: 3 | Order Execution: REAL
Run this once per day (before market open or after close).
"""

import os
import sys
import pandas as pd
import yfinance as yf
from datetime import datetime

# Add LightRain path for db_connection
sys.path.insert(0, '/home/ubuntu/trading')

# Database imports
from scripts.db_connection import (
    get_active_positions, add_position, close_position, log_trade,
    get_capital, update_capital, get_available_cash,
    is_position_on_hold, add_circuit_breaker_hold, get_today_trades,
    get_db_cursor, debit_capital, credit_capital, get_deployed_capital
)

# Trading logic imports
from scripts.signal_generator_daily import generate_signal_daily
from scripts.signal_generator_v3 import get_enabled_indicators
from scripts.risk_manager import (
    calculate_position_metrics, check_circuit_breaker, analyze_drop_reason,
    format_circuit_breaker_message, calculate_atr
)
from scripts.telegram_bot import (
    send_daily_report, send_trade_alert, send_stop_loss_alert,
    send_take_profit_alert, format_portfolio_summary,
    format_trades_today, format_signals, send_telegram_message
)
from scripts.rs_rating import RelativeStrengthAnalyzer
from scripts.percentage_based_allocation import calculate_percentage_allocation, select_positions_for_entry

# AI analyzer with news (ai_news_analyzer.py)
try:
    from scripts.ai_news_analyzer import get_ai_recommendation
    AI_ANALYSIS_AVAILABLE = True
except ImportError:
    AI_ANALYSIS_AVAILABLE = False
    def get_ai_recommendation(*args, **kwargs):
        return None

# AngelOne price fetcher
from scripts.angelone_price_fetcher import get_live_price
from scripts.angelone_broker import AngelOneBroker
from scripts.data_loader_angelone import load_data_angelone, get_current_prices_angelone

# Sector analysis for rotation and diversification
from scripts.sector_analysis import (
    get_sector_rotation_ranking, is_sector_in_top_n,
    check_relative_strength_vs_peers, check_sector_limit, get_stock_sector
)


def calculate_trading_days(start_date, end_date):
    """
    Calculate number of ACTUAL trading days between two dates
    Excludes weekends AND NSE market holidays
    Does NOT count the start date (only counts days HELD after entry)
    """
    import pandas as pd
    from datetime import timedelta
    
    # NSE Holidays 2026 (update annually)
    NSE_HOLIDAYS_2026 = [
        '2026-01-26',  # Republic Day
        '2026-03-10',  # Maha Shivaratri
        '2026-03-17',  # Holi
        '2026-03-30',  # Id-ul-Fitr (tentative)
        '2026-04-02',  # Ram Navami
        '2026-04-03',  # Good Friday
        '2026-04-06',  # Dr. Ambedkar Jayanti (observed)
        '2026-04-14',  # Dr. Ambedkar Jayanti
        '2026-05-01',  # May Day
        '2026-06-06',  # Id-ul-Adha (Bakri Id) (tentative)
        '2026-07-06',  # Muharram (tentative)
        '2026-08-15',  # Independence Day
        '2026-08-16',  # Parsi New Year
        '2026-09-04',  # Milad-un-Nabi (tentative)
        '2026-10-02',  # Mahatma Gandhi Jayanti
        '2026-10-20',  # Dussehra
        '2026-10-21',  # Dussehra (day 2)
        '2026-11-09',  # Diwali (Lakshmi Puja)
        '2026-11-10',  # Diwali Balipratipada
        '2026-11-16',  # Gurunanak Jayanti
        '2026-12-25',  # Christmas
    ]
    
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    
    # Don't count the entry date itself, start from next day
    start_next = start + timedelta(days=1)
    
    if end < start_next:
        return 0  # Same day entry/exit
    
    # Generate business days (excludes weekends)
    business_days = pd.bdate_range(start=start_next, end=end)
    
    # Exclude NSE holidays
    holidays = pd.to_datetime(NSE_HOLIDAYS_2026)
    trading_days = [d for d in business_days if d not in holidays]
    
    return len(trading_days)



# Configuration - LIVE TRADING (₹10,000 capital)
ACCOUNT_SIZE = 10000  # ₹10K for LIVE DAILY trading
MAX_DAILY_POSITIONS = 3  # Maximum 3 concurrent positions for ₹10K
MAX_POSITION_PCT = 0.40  # 40% max position size (₹4,000 per position)
MAX_POSITIONS_PER_SECTOR = 1  # Max 1 position per sector for diversification
MIN_COMBINED_SCORE = 50
USE_ATR_SIZING = True
MIN_RS_RATING = 60  # Minimum Relative Strength rating for daily trading (1-99 scale)
MIN_SCORE = 60  # Minimum technical score to qualify for entry
MAX_HOLD_DAYS = 3  # Maximum TRADING days to hold a position (excludes weekends)
RISK_PER_TRADE_PCT = 0.01  # 1% risk per trade (Fixed Risk Position Sizing)
TARGET_RR_RATIO = 1.5  # 1.5:1 Risk:Reward for faster exits (3-day max hold)
STRATEGY = 'DAILY'
TRADING_MODE = 'LIVE'  # LIVE trading - real money, real orders

print("=" * 70)
print("🔴 LIVE DAILY TRADING (AngelOne + Real Orders)")
print("=" * 70)
print(f"📅 {datetime.now().strftime('%d %b %Y, %H:%M:%S')}")
print("=" * 70)

# Initialize AngelOne broker for LIVE order execution
print("🔐 Initializing AngelOne broker...")
broker = AngelOneBroker()
if not broker.login():
    error_msg = "🔴 LIVE: ❌ Failed to login to AngelOne. Cannot proceed."
    print(error_msg)
    send_telegram_message(error_msg)
    sys.exit(1)
print("✅ Broker connected")

# MARKET HOURS AND HOLIDAY CHECK
def is_market_open():
    """Check if Indian stock market (NSE) is currently open"""
    import pytz
    
    # Check market hours (9:15 AM - 3:30 PM IST)
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    hour, minute = now.hour, now.minute
    
    # Time check
    market_hours_open = (hour == 9 and minute >= 15) or (9 < hour < 15) or (hour == 15 and minute <= 30)
    
    if not market_hours_open:
        return False, f"Outside market hours: {now.strftime('%I:%M %p IST')} (Market: 9:15 AM - 3:30 PM)"
    
    # Holiday check - fetch NIFTY data to see if market is actually open
    try:
        nifty = yf.Ticker("^NSEI")
        hist = nifty.history(period="2d")
        
        if hist.empty:
            return False, "No market data available (likely holiday)"
        
        # Check if today's date appears in the data
        today_str = now.strftime('%Y-%m-%d')
        dates_in_data = hist.index.strftime('%Y-%m-%d').tolist()
        
        if today_str not in dates_in_data:
            last_day = dates_in_data[-1] if dates_in_data else 'unknown'
            return False, f"Market holiday detected (last trading day: {last_day})"
        
        return True, f"Market open - {now.strftime('%I:%M %p IST')}"
    
    except Exception as e:
        # On error, assume market is open (fail-safe for connectivity issues)
        print(f"⚠️ Warning: Could not verify holiday status ({e}). Proceeding with caution.")
        return True, f"Market hours OK (holiday check failed)"

is_open, reason = is_market_open()
if not is_open:
    message = f"❌ Market Closed - {reason}"
    print(message)
    send_telegram_message(f"⏸️ {STRATEGY} Trading Skipped\n\n{reason}")
    sys.exit(0)
print(f"✅ {reason}")


# Check if trading is enabled
TRADING_ENABLED = os.getenv("TRADING_ENABLED", "true").lower() == "true"

if not TRADING_ENABLED:
    message = "⏸️ Trading is PAUSED\n\nTo resume, set TRADING_ENABLED=true in .env"
    print(message)
    send_telegram_message(message)
    sys.exit(0)

# Check for KILL SWITCH halt flag
halt_file = '/home/ubuntu/trading/data/trading_halted.flag'
if os.path.exists(halt_file):
    try:
        with open(halt_file, 'r') as f:
            halt_data = json.load(f)

        halt_date = halt_data.get('date', '')
        today_str = datetime.now().strftime('%Y-%m-%d')

        if halt_date == today_str:
            print(f"🚫 TRADING HALTED BY KILL SWITCH")
            print(f"   Triggered: {halt_data.get('timestamp', 'Unknown')}")
            print(f"   Reason: {halt_data.get('reason', 'Unknown')}")

            send_telegram_message(
                f"🚫 DAILY Trading Blocked\n\n"
                f"Kill switch active since {halt_data.get('timestamp', 'Unknown')[:16]}\n"
                f"Reason: {halt_data.get('reason', 'Kill switch')}\n\n"
                f"Trading will resume tomorrow."
            )
            sys.exit(0)
        else:
            # Halt expired, remove file
            os.remove(halt_file)
            print(f"✅ Removed expired halt flag from {halt_date}")
    except Exception as e:
        print(f"⚠️ Error reading halt file: {e}")
        # Continue trading on error to be safe
        pass


# ========== LOAD PORTFOLIO AND CHECK EXITS (BEFORE REGIME CHECKS) ==========
print("\n📥 Loading portfolio and checking exits...")

# Load existing positions
positions = get_active_positions(STRATEGY, TRADING_MODE)

if positions:
    # Get tickers for price fetching
    position_tickers = [pos['ticker'] for pos in positions if pos['status'] == 'HOLD']
    
    if position_tickers:
        print(f"📊 Found {len(position_tickers)} active positions")
        
        # Download price data for positions
        print(f"📥 Loading price data for positions...")
        position_stock_data = {}
        
        for ticker in position_tickers:
            try:
                df = yf.download(ticker, period='5d', interval='1d', progress=False)
                
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                
                if not df.empty:
                    position_stock_data[ticker] = df
            except Exception as e:
                print(f"  ⚠️ {ticker}: Failed to fetch data - {e}")
        
        print(f"✅ Loaded data for {len(position_stock_data)} positions")
        
        # Check MAX-HOLD exits
        max_hold_exits = 0
        
        for pos in positions:
            if pos['status'] != 'HOLD':
                continue
            
            ticker = pos['ticker']
            entry_price = float(pos['entry_price'])
            entry_date = pos['entry_date']
            qty = int(pos['quantity'])
            
            # Calculate trading days held
            entry_dt = pd.to_datetime(entry_date)
            current_dt = pd.to_datetime(datetime.now().strftime("%Y-%m-%d"))
            days_held = calculate_trading_days(entry_dt, current_dt)
            
            # Check MAX-HOLD
            if days_held >= MAX_HOLD_DAYS:
                if ticker in position_stock_data and not position_stock_data[ticker].empty:
                    current_price = float(position_stock_data[ticker]['Close'].iloc[-1])
                else:
                    print(f"  ⚠️ {ticker}: MAX-HOLD reached ({days_held}d) but no price data")
                    continue
                
                pnl = (current_price - entry_price) * qty
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
                pnl_emoji = "🟢" if pnl >= 0 else "🔴"
                
                print(f"  ⏰ MAX-HOLD EXIT: {ticker} @ ₹{current_price:.2f} | P&L: ₹{pnl:,.0f} ({pnl_pct:+.2f}%) | {days_held}d")
                
                send_telegram_message(
                    f"🔴 {pnl_emoji} <b>LIVE MAX-HOLD EXIT</b>\n\n"
                    f"📊 Ticker: {ticker} ({STRATEGY})\n"
                    f"⏰ Reason: Held {days_held} days (max: {MAX_HOLD_DAYS})\n"
                    f"💰 Entry: ₹{entry_price:.2f} → Exit: ₹{current_price:.2f}\n"
                    f"💵 P&L: ₹{pnl:,.0f} ({pnl_pct:+.2f}%)\n\n"
                    f"<i>Freeing capital for new opportunities</i>"
                )
                
                try:
                    # LIVE: Place SELL order via AngelOne
                    print(f"   📤 Placing LIVE SELL order for {ticker}...")
                    sell_order_id = broker.place_order(
                        symbol=ticker,
                        quantity=qty,
                        price=None,
                        order_type='MARKET',
                        transaction_type='SELL',
                        product_type='DELIVERY'
                    )
                    
                    if not sell_order_id:
                        print(f"   ❌ LIVE SELL order failed for {ticker}")
                        send_telegram_message(f"🔴 <b>LIVE SELL FAILED</b> - {ticker} MAX-HOLD exit failed")
                        continue
                    
                    print(f"   ✅ LIVE SELL order placed: {sell_order_id}")
                    
                    close_position(ticker, STRATEGY, current_price, pnl)
                    credit_capital(STRATEGY, entry_price * qty)
                    update_capital(STRATEGY, pnl)
                    
                    log_trade(
                        ticker=ticker,
                        strategy=STRATEGY,
                        signal='SELL',
                        price=current_price,
                        quantity=qty,
                        pnl=pnl,
                        notes=f"LIVE MAX-HOLD exit after {days_held} days | Order: {sell_order_id}",
                        trading_mode=TRADING_MODE
                    )
                    
                    max_hold_exits += 1
                    print(f"  ✅ Position closed")
                except Exception as e:
                    print(f"  ❌ Failed to close: {e}")
        
        if max_hold_exits > 0:
            print(f"✅ Exited {max_hold_exits} MAX-HOLD position(s)")
        else:
            print(f"✅ No MAX-HOLD exits needed")
    else:
        print("✅ No active positions")
else:
    print("✅ No positions in database")

# ========== END EXIT CHECKS ==========

# Check global market regime
import json

regime_file = '/home/ubuntu/trading/data/market_regime.json'
if os.path.exists(regime_file):
    with open(regime_file, 'r') as f:
        regime = json.load(f)

    # Store regime data for later checks (SOFT BLOCK - no sys.exit)
    GLOBAL_ALLOW_NEW_ENTRIES = regime.get('allow_new_entries', True)
    REGIME_MULTIPLIER = regime.get('position_sizing_multiplier', 1.0)
    
    if not GLOBAL_ALLOW_NEW_ENTRIES:
        print(f"🚫 Global regime: {regime.get('regime', 'UNKNOWN')}")
        print(f"   Score: {regime.get('score', 0)}")
        print(f"   Allow entries: False")
        print(f"   Will check exits, then skip new entries")
    else:
        print(f"✅ Global regime: {regime.get('regime', 'UNKNOWN')} (score: {regime.get('score', 0)})")
        print(f"   Allow entries: True")
        print(f"   Position multiplier: {REGIME_MULTIPLIER*100}%")
else:
    # No regime data found, default to 100%
    REGIME_MULTIPLIER = 1.0
    GLOBAL_ALLOW_NEW_ENTRIES = True  # Default to allowing entries
    print("⚠️ No market regime data found (run global_market_filter.py at 8:30 AM)")
    print("   Using default 100% position sizing")

# ========== SMART ENTRY VALIDATOR (9:15 AM + 9:30 AM) ==========
from scripts.smart_entry_validator import (
    validate_nifty_at_open,
    analyze_nifty_strength_930
)

# STEP 1: Check Nifty regime at 9:15 AM
print("\n🔍 SMART ENTRY: Checking Nifty regime (9:15 AM)...")
action_915, regime_915, regime_multiplier_915, reason_915, nifty_data_915 = validate_nifty_at_open()

# Store 9:15 regime data (SOFT BLOCK - no sys.exit)
NIFTY_915_ALLOW_ENTRIES = (action_915 != "SKIP")

if action_915 == "SKIP":
    print(f"❌ BEAR regime detected: {regime_915}")
    print(f"   Regime multiplier: {regime_multiplier_915} (0% = SKIP ALL)")
    print(f"   Will check exits, then skip new entries")
else:
    print(f"✅ Nifty regime: {regime_915} (multiplier: {regime_multiplier_915*100:.0f}%)")

# STEP 2: Check market conditions (9:30 candle OR mid-day IGC)
current_hour = datetime.now().hour
current_minute = datetime.now().minute

# Mid-day mode: After 10:00 AM, use IGC (Intraday Global Check) instead of 9:30 candle
if current_hour >= 10:
    print(f"🕙 MID-DAY MODE: Running at {current_hour}:{current_minute:02d} - using IGC check")
    
    # Run quick IGC check
    from scripts.angelone_price_fetcher import get_angel_session
    igc_session = get_angel_session()
    
    green_count = 0
    total_count = 0
    
    if igc_session:
        indices = [
            ('NIFTY 50', '99926000'),
            ('Nifty Midcap 150', '99926009'),
            ('Nifty Smallcap 250', '99926013')
        ]
        
        print("   Checking live indices:")
        for idx_name, token in indices:
            try:
                ltp_data = igc_session.ltpData('NSE', idx_name, token)
                if ltp_data and ltp_data.get('status'):
                    data = ltp_data['data']
                    ltp = float(data.get('ltp', 0))
                    open_price = float(data.get('open', 0))
                    if open_price > 0:
                        change_pct = ((ltp - open_price) / open_price) * 100
                        is_green = change_pct >= 0
                        emoji = '🟢' if is_green else '🔴'
                        print(f"     {emoji} {idx_name}: {change_pct:+.2f}%")
                        total_count += 1
                        if is_green:
                            green_count += 1
            except Exception as e:
                print(f"     ⚠️ {idx_name}: {e}")
        
        breadth_pct = (green_count / total_count * 100) if total_count > 0 else 50
        print(f"   Breadth: {green_count}/{total_count} GREEN ({breadth_pct:.0f}%)")
        
        # Convert breadth to deployment
        if breadth_pct >= 67:
            slice_pct = 0.75
            candle_level = 'STRONG'
            notes_930 = f'IGC: {breadth_pct:.0f}% bullish - Deploy 75%'
        elif breadth_pct >= 33:
            slice_pct = 0.50
            candle_level = 'NEUTRAL'
            notes_930 = f'IGC: {breadth_pct:.0f}% mixed - Deploy 50%'
        else:
            slice_pct = 0.0
            candle_level = 'VERY_WEAK'
            notes_930 = f'IGC: {breadth_pct:.0f}% bearish - Skip'
    else:
        slice_pct = 0.50
        candle_level = 'NEUTRAL'
        notes_930 = 'IGC unavailable - Default 50%'
    
    candle_data = {'pattern': 'IGC_MIDDAY', 'strength': slice_pct, 'sentiment': candle_level}
else:
    print("🔍 SMART ENTRY: Analyzing Nifty opening candle (9:30 AM)...")
    candle_level, slice_pct, notes_930, candle_data = analyze_nifty_strength_930()

# Debug logging to see actual values
print(f"🔍 DEBUG - Candle Analysis:")
print(f"   Pattern: {candle_data.get('pattern', 'None')}")
print(f"   Level: {candle_level}")
print(f"   slice_pct (raw decimal): {slice_pct}")
print(f"   slice_pct as %: {slice_pct*100:.1f}%")

# Check for UNKNOWN pattern (SOFT BLOCK - no sys.exit)
CANDLE_PATTERN_VALID = not (candle_data.get("pattern") is None or candle_level == "UNKNOWN")

if not CANDLE_PATTERN_VALID:
    print(f"❌ UNKNOWN/None candle pattern detected (likely holiday or no data)")
    print(f"   Pattern: {candle_data.get('pattern', 'None')}")
    print(f"   Level: {candle_level}")
    print(f"   Will check exits, then skip new entries")
    slice_pct = 0  # Force 0% deployment


# Check candle strength (SOFT BLOCK - no sys.exit)
CANDLE_ALLOWS_ENTRIES = (slice_pct > 0)

if slice_pct == 0:
    print(f"❌ STRONG_BEARISH opening candle detected")
    print(f"   Pattern: {candle_data.get('pattern', 'Unknown')}")
    print(f"   Slice %: {slice_pct*100:.0f}% (0% = SKIP ALL)")
    print(f"   Will check exits, then skip new entries")
else:
    print(f"✅ Nifty candle: {candle_level} ({notes_930}, slice: {slice_pct*100:.0f}%)")

# STEP 3: Calculate final deployment percentage
# slice_pct is already a decimal (0.0 to 1.0), so just multiply directly
SMART_ENTRY_DEPLOYMENT_PCT = regime_multiplier_915 * slice_pct

print(f"\n💡 SMART ENTRY FINAL DEPLOYMENT:")
print(f"   Regime multiplier: {regime_multiplier_915*100:.0f}%")
print(f"   Candle slice: {slice_pct*100:.0f}%")
print(f"   Final deployment: {SMART_ENTRY_DEPLOYMENT_PCT*100:.1f}%")

# Override position sizing with smart entry result
REGIME_MULTIPLIER = SMART_ENTRY_DEPLOYMENT_PCT
print(f"   Overriding position sizing with {REGIME_MULTIPLIER*100:.1f}% deployment\n")

# Send telegram notification with final deployment decision
send_telegram_message(
    f"🔴 <b>LIVE DAILY - Smart Entry Analysis</b>\n\n"
    f"<b>Global Regime (8:30 AM):</b> {regime.get('regime', 'UNKNOWN') if os.path.exists(regime_file) else 'N/A'}\n"
    f"<b>Nifty Regime (9:15 AM):</b> {regime_915}\n"
    f"<b>Nifty Candle (9:30 AM):</b> {candle_data.get('pattern', 'Unknown')}\n\n"
    f"<b>Calculation:</b>\n"
    f"  • Regime multiplier: {regime_multiplier_915*100:.0f}%\n"
    f"  • Candle slice: {slice_pct*100:.0f}%\n"
    f"  • <b>Final Deployment: {REGIME_MULTIPLIER*100:.1f}%</b>\n\n"
    f"⏳ Proceeding with stock screening..."
)

# Check deployment level (SOFT BLOCK - no sys.exit)
DEPLOYMENT_ALLOWS_ENTRIES = (REGIME_MULTIPLIER >= 0.01)

if not DEPLOYMENT_ALLOWS_ENTRIES:
    print(f"🚫 SMART ENTRY: Deployment too low ({REGIME_MULTIPLIER*100:.1f}%) - Skipping new entries")
    print(f"   Will check exits first")

# ========== END SMART ENTRY VALIDATOR ==========


# ========== COMBINED REGIME CHECK (ALL FLAGS) ==========
# Combine all regime flags to determine if new entries are allowed
ALLOW_NEW_ENTRIES = (
    GLOBAL_ALLOW_NEW_ENTRIES and 
    NIFTY_915_ALLOW_ENTRIES and 
    CANDLE_PATTERN_VALID and 
    CANDLE_ALLOWS_ENTRIES and 
    DEPLOYMENT_ALLOWS_ENTRIES
)

print(f"\n💡 REGIME CHECK SUMMARY:")
print(f"   Global regime: {'✅' if GLOBAL_ALLOW_NEW_ENTRIES else '❌'}")
print(f"   Nifty 9:15 regime: {'✅' if NIFTY_915_ALLOW_ENTRIES else '❌'}")
print(f"   Candle pattern valid: {'✅' if CANDLE_PATTERN_VALID else '❌'}")
print(f"   Candle allows entries: {'✅' if CANDLE_ALLOWS_ENTRIES else '❌'}")
print(f"   Deployment sufficient: {'✅' if DEPLOYMENT_ALLOWS_ENTRIES else '❌'}")
print(f"   => ALLOW NEW ENTRIES: {'✅ YES' if ALLOW_NEW_ENTRIES else '❌ NO'}")

if not ALLOW_NEW_ENTRIES:
    print(f"\n🚫 Regime blocks new entries - Exits completed, skipping entry scan")
    
    # Send summary notification
    send_telegram_message(
        f"🚫 <b>DAILY Trading - No New Entries</b>\n\n"
        f"<b>Global Regime (8:30 AM):</b> {regime.get('regime', 'UNKNOWN') if 'regime' in locals() else 'N/A'}\n"
        f"<b>Nifty Regime (9:15 AM):</b> {regime_915 if 'regime_915' in locals() else 'N/A'}\n"
        f"<b>Nifty Candle (9:30 AM):</b> {candle_data.get('pattern', 'Unknown') if 'candle_data' in locals() else 'N/A'}\n\n"
        f"<b>Final Deployment:</b> {REGIME_MULTIPLIER*100:.1f}%\n\n"
        f"✅ Exits completed\n"
        f"❌ No new positions entered today"
    )
    
    sys.exit(0)  # Exit after completing exits

print(f"\n✅ Regime allows new entries - Proceeding with stock screening...")
print(f"   Deployment level: {REGIME_MULTIPLIER*100:.1f}%")

# ========== END COMBINED REGIME CHECK ==========

# Load stocks from screened_stocks table
print("\n📥 Loading stocks from NSE universe...")
stocks_to_screen = []
stock_categories = {}  # Map ticker to category

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
            error_msg = "❌ No stocks found in screened_stocks table for today. Run stocks_screening.py first."
            print(error_msg)
            send_telegram_message(error_msg)
            sys.exit(1)

        for row in results:
            ticker = row['ticker']
            category = row['category']
            stocks_to_screen.append(ticker)
            stock_categories[ticker] = category

        print(f"✅ Loaded {len(stocks_to_screen)} stocks from database")

        # Count by category
        from collections import Counter
        category_counts = Counter(stock_categories.values())
        for cat, count in sorted(category_counts.items()):
            print(f"   {cat}: {count}")

except Exception as e:
    error_msg = f"❌ Failed to load stocks from database: {e}"
    print(error_msg)
    send_telegram_message(error_msg)
    sys.exit(1)
# Download OHLCV data for all stocks using yfinance (faster, no rate limits)
# AngelOne is only used for final LTP when placing orders
print(f"\n📥 Downloading data for {len(stocks_to_screen)} stocks via yfinance...")
stock_data = {}
download_errors = 0

for i, ticker in enumerate(stocks_to_screen, 1):
    if i % 50 == 0:
        print(f"   Progress: {i}/{len(stocks_to_screen)}")

    try:
        df = yf.download(ticker, period="6mo", interval="1d", progress=False)

        # Flatten MultiIndex columns if present (yfinance bug fix)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        if not df.empty and len(df) >= 60:
            stock_data[ticker] = df
    except Exception as e:
        download_errors += 1

print(f"✅ Downloaded {len(stock_data)} stocks ({download_errors} errors)")

print(f"✅ Downloaded {len(stock_data)} stocks ({download_errors} errors)")

if not stock_data:
    error_msg = "❌ No stock data downloaded. Check network or yfinance."
    print(error_msg)
    send_telegram_message(error_msg)
    sys.exit(1)

# Load portfolio from database
print("📥 Loading portfolio from database...")
positions = get_active_positions(STRATEGY, TRADING_MODE)

# Convert to DataFrame format for compatibility with existing code
portfolio_data = []
for pos in positions:
    portfolio_data.append({
        'Ticker': pos['ticker'],
        'Status': pos['status'],
        'EntryPrice': float(pos['entry_price']),
        'EntryDate': pos['entry_date'].strftime('%Y-%m-%d') if hasattr(pos['entry_date'], 'strftime') else str(pos['entry_date']),
        'Quantity': int(pos['quantity']),
        'StopLoss': float(pos['stop_loss']),
        'TakeProfit': float(pos['take_profit'])
    })

if portfolio_data:
    portfolio = pd.DataFrame(portfolio_data)
    print(f"✅ Portfolio loaded: {len(portfolio[portfolio['Status']=='HOLD'])} positions")
else:
    portfolio = pd.DataFrame(columns=["Ticker", "Status", "EntryPrice", "EntryDate", "Quantity", "StopLoss", "TakeProfit"])
    print("⚠️ No positions in database")

# Track today's activity
signals_generated = []
trades_today = []

# Circuit Breaker FIRST (v8 fix: exit old positions before capital calculation)
print("\n🛡️ Pre-Trading Circuit Breaker Check...")

for _, row in portfolio[portfolio['Status'] == 'HOLD'].iterrows():
    ticker = row['Ticker']
    entry_price = float(row['EntryPrice'])
    entry_date = row.get('EntryDate', datetime.now().strftime("%Y-%m-%d"))
    qty = int(row['Quantity'])

    # Calculate days held
    entry_dt = pd.to_datetime(entry_date)
    current_dt = pd.to_datetime(datetime.now().strftime("%Y-%m-%d"))
    days_held = calculate_trading_days(entry_dt, current_dt)  # Trading days (weekdays only)

print(f"💰 POST-EXIT CHECK: {len(portfolio[portfolio['Status']=='HOLD'])} positions remain")

print(f"\n🎯 Analyzing {len(stock_data)} stocks...")

# Show which indicators are enabled
enabled = get_enabled_indicators()
print(f"📊 Using indicators: {', '.join(enabled)}")
print()

# Initialize RS Analyzer
rs_analyzer = RelativeStrengthAnalyzer()
rs_filtered_count = 0


# SECTOR ROTATION ANALYSIS (before scanning for signals)
print("📊 Calculating sector rotation rankings...")
sector_ranking = get_sector_rotation_ranking(period='30d', benchmark='^NSEI')

if sector_ranking:
    print("\n📈 Sector Rankings (vs Nifty 50):")
    sorted_sectors = sorted(sector_ranking.items(), key=lambda x: x[1]['rank'])
    for sector, data in sorted_sectors[:5]:  # Show top 5
        print(f"   #{data['rank']} {sector}: {data['relative_strength']:+.2f}%")
    print(f"   ... ({len(sector_ranking)} sectors tracked)")
else:
    print("⚠️ Warning: Sector rotation data unavailable - proceeding without sector filter")

# Track sector filter statistics
sector_rotation_filtered = 0
sector_peer_filtered = 0

# PHASE 1: Collect all BUY signals (don't execute positions yet)
print("🔍 PHASE 1: Scanning for BUY signals...")
candidates_by_category = {'large_caps': [], 'mid_caps': [], 'micro_caps': []}
sell_signals = []  # Track SELL signals for existing positions
all_scores = {}  # Track scores for all stocks to save to DB

for ticker, df in stock_data.items():
    if df.empty or len(df) < 60:
        continue

    try:
        # RS Rating Filter (Pre-filter before expensive indicator calculations)
        rs_rating = rs_analyzer.calculate_rs_rating(ticker)
        if rs_rating < MIN_RS_RATING:
            rs_filtered_count += 1
            continue  # Skip weak stocks

        # Generate signal using v3 (configurable)
        signal, score, details = generate_signal_daily(df, min_score=MIN_COMBINED_SCORE, use_guards=True)

        # Save score and RS for ALL stocks (for re-entry use)
        all_scores[ticker] = {'score': score, 'rs_rating': rs_rating}

        # Track signal
        if signal != "HOLD":
            signals_generated.append({
                'ticker': ticker,
                'action': signal,
                'score': score,
                'details': details,
                'rs_rating': rs_rating
            })
            print(f"{ticker}: {signal} (Score: {score} | RS: {rs_rating})")

        # Categorize BUY signals by market cap
        if signal == "BUY":
            # Skip if already holding
            if not portfolio.empty and ticker in portfolio['Ticker'].values:
                continue

            # Get category from database lookup
            category = stock_categories.get(ticker, 'Unknown')

            # Map database category to allocation category
            category_map = {
                'Large-cap': 'large_caps',
                'Mid-cap': 'mid_caps',
                'Micro-cap': 'micro_caps', 'Microcap': 'micro_caps'
            }
            allocation_category = category_map.get(category)

            if allocation_category:
                # SECTOR ROTATION CHECK: Only enter stocks from top 3 sectors
                in_top_sector, sector_reason = is_sector_in_top_n(ticker, sector_ranking, top_n=3)
                if not in_top_sector:
                    sector_rotation_filtered += 1
                    print(f"   ⏭️  {ticker}: Skipped - {sector_reason}")
                    continue

                # RELATIVE STRENGTH VS SECTOR PEERS CHECK
                peer_check, peer_reason = check_relative_strength_vs_peers(ticker, stock_data, min_percentile=50)
                if not peer_check:
                    sector_peer_filtered += 1
                    print(f"   ⏭️  {ticker}: Skipped - {peer_reason}")
                    continue

                print(f"   ✅ {ticker}: Sector checks passed - {sector_reason}, {peer_reason}")

                # Calculate ATR for risk-based sizing
                atr = calculate_atr(df, period=14)
                atr_pct = (atr / float(df['Close'].iloc[-1])) * 100 if atr > 0 else 2.0

                # Get current price (try regularMarketPrice if available, else Close)
                try:
                    ticker_obj = yf.Ticker(ticker)
                    current_price = ticker_obj.info.get('regularMarketPrice') or ticker_obj.info.get('currentPrice')
                    if current_price and current_price > 0:
                        latest_price = float(current_price)
                    else:
                        latest_price = float(df['Close'].iloc[-1])  # Fallback to Close
                except:
                    latest_price = float(df['Close'].iloc[-1])  # Fallback to Close

                candidates_by_category[allocation_category].append({
                    'ticker': ticker,
                    'score': score,
                    'price': latest_price,
                    'atr_pct': atr_pct,
                    'rs_rating': rs_rating,
                    'df': df  # Store for later use
                })

        elif signal == "SELL":
            # Track SELL signals for existing positions
            if not portfolio.empty and ticker in portfolio['Ticker'].values:
                sell_signals.append({
                    'ticker': ticker,
                    'score': score,
                    'df': df
                })

    except Exception as e:
        print(f"⚠️ Error processing {ticker}: {e}")
        continue

# Save all scores to database for re-entry use
print(f"\n💾 Saving {len(all_scores)} stock scores to database...")
saved_count = 0
with get_db_cursor() as cur:
    for ticker, data in all_scores.items():
        try:
            cur.execute("""
                UPDATE screened_stocks
                SET score = %s,
                    rs_rating = %s,
                    trading_mode = %s,
                    screen_date = CURRENT_TIMESTAMP
                WHERE ticker = %s AND last_updated = CURRENT_DATE
            """, (data['score'], data['rs_rating'], TRADING_MODE, ticker))
            saved_count += 1
        except Exception as e:
            print(f"⚠️ Error saving score for {ticker}: {e}")
print(f"✅ Saved scores for {saved_count} stocks (Mode: {TRADING_MODE})")

# Count candidates
total_candidates = sum(len(v) for v in candidates_by_category.values())
print(f"\n📊 BUY Signals Found: {total_candidates}")
print(f"   Large-caps: {len(candidates_by_category['large_caps'])}")
print(f"   Mid-caps: {len(candidates_by_category['mid_caps'])}")
print(f"   Micro-caps: {len(candidates_by_category['micro_caps'])}")
print(f"   Stocks filtered by RS < {MIN_RS_RATING}: {rs_filtered_count}")
print(f"   Stocks filtered by sector rotation (not in top 3): {sector_rotation_filtered}")
print(f"   Stocks filtered by sector peer strength (< top 50%): {sector_peer_filtered}")
print(f"   SELL Signals: {len(sell_signals)}")

# PHASE 2: Process SELL signals first (close positions)
print("\n🔍 PHASE 2: Processing SELL signals...")

for sell in sell_signals:
    ticker = sell['ticker']
    df = sell['df']

    if ticker in portfolio['Ticker'].values:
        pos = portfolio[portfolio['Ticker'] == ticker].iloc[0]
        entry_price = float(pos['EntryPrice'])
        current_price = float(df['Close'].iloc[-1])
        qty = int(pos['Quantity'])
        pnl = (current_price - entry_price) * qty

        try:
            close_position(ticker, STRATEGY, current_price, pnl)

            # Credit back the original investment
            original_investment = entry_price * qty
            credit_capital(STRATEGY, original_investment)

            # Update capital with P&L
            update_capital(STRATEGY, pnl)

            # Log trade
            log_trade(
                ticker=ticker,
                strategy=STRATEGY,
                signal='SELL',
                price=current_price,
                quantity=qty,
                pnl=pnl,
                notes=f"Exit signal (Score: {sell['score']})",
                trading_mode=TRADING_MODE
            )

            # Update local portfolio
            portfolio.loc[portfolio['Ticker'] == ticker, 'Status'] = 'SOLD'

            print(f"   🛑 SOLD {ticker} @ ₹{current_price:.2f} | P&L: ₹{pnl:,.0f}")

            # Send Telegram alert (SELL signal, not stop loss)
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
            pnl_emoji = "🟢" if pnl > 0 else "🔴"
            send_telegram_message(
                f"{pnl_emoji} <b>STRATEGIC EXIT</b>\n\n"
                f"📊 Ticker: {ticker} ({STRATEGY})\n"
                f"📉 Reason: SELL signal (Score: {sell['score']:.1f})\n"
                f"📥 Entry: ₹{entry_price:.2f}\n"
                f"📤 Exit: ₹{current_price:.2f}\n"
                f"💰 P&L: ₹{pnl:,.0f} ({pnl_pct:+.2f}%)\n"
                f"📦 Qty: {qty}\n\n"
                f"<i>Technical signals weakened, exited proactively</i>"
            )

        except Exception as e:
            print(f"   ⚠️ Failed to close position {ticker}: {e}")

# PHASE 3: Apply percentage-based allocation with position limit
print("\n🔍 PHASE 3: Applying percentage-based 60/20/20 allocation...")

if total_candidates > 0:
    # Check current position count
    with get_db_cursor() as cur:
        cur.execute("SELECT COUNT(*) as cnt FROM positions WHERE category = %s AND status = 'ACTIVE'", (STRATEGY,))
        current_positions = cur.fetchone()['cnt']

    print(f"\n📊 POSITION LIMITS:")
    print(f"   Current DAILY positions: {current_positions}/{MAX_DAILY_POSITIONS}")

    # If at max positions, skip entry
    if current_positions >= MAX_DAILY_POSITIONS:
        print(f"\n⚠️ MAX DAILY POSITIONS REACHED ({MAX_DAILY_POSITIONS})")
        print(f"   Skipping new entries. Wait for positions to close.")
        send_telegram_message(
            f"⚠️ DAILY Max Positions Reached\n\n"
            f"Current: {current_positions}/{MAX_DAILY_POSITIONS}\n\n"
            f"No new positions entered. Monitoring existing positions."
        )
        sys.exit(0)

    # Check already deployed capital to prevent over-deployment
    deployed_capital = get_deployed_capital(strategy=STRATEGY)
    # Use get_available_cash() to account for losses (not just deployed)
    from scripts.db_connection import get_available_cash
    available_capital = get_available_cash(STRATEGY)

    print(f"\n💰 CAPITAL STATUS:")
    print(f"   Account Size:      ₹{ACCOUNT_SIZE:,.0f}")
    print(f"   Already Deployed:  ₹{deployed_capital:,.0f}")
    print(f"   Available:         ₹{available_capital:,.0f}")

    # Check for mid-day entry mode (50% position sizing)
    # Apply regime-based position sizing multiplier
    midday_mode = os.getenv('MIDDAY_ENTRY', 'false').lower() == 'true'
    position_multiplier = float(os.getenv('POSITION_SIZE_MULTIPLIER', '1.0'))

    # Start with regime multiplier (from global market check)
    effective_capital = available_capital * REGIME_MULTIPLIER

    # If midday mode, apply additional multiplier
    if midday_mode:
        effective_capital = effective_capital * position_multiplier
        print(f"\n🕥 MID-DAY ENTRY MODE: Applying additional {position_multiplier*100:.0f}% multiplier")
        print(f"   Combined multiplier: {REGIME_MULTIPLIER * position_multiplier * 100:.0f}%")
        print(f"   Effective capital: ₹{effective_capital:,.0f} (of ₹{available_capital:,.0f} available)")
    else:
        print(f"\n💰 Regime-based position sizing: {REGIME_MULTIPLIER*100:.0f}%")
        print(f"   Effective capital: ₹{effective_capital:,.0f} (of ₹{available_capital:,.0f} available)")

    # Safety check: If no capital available, skip trading
    if effective_capital <= 0:
        print(f"\n⚠️ NO CAPITAL AVAILABLE FOR NEW POSITIONS")
        print(f"   All capital (₹{ACCOUNT_SIZE:,.0f}) is already deployed")
        print(f"   Skipping new entries. Wait for positions to close.")

        # Send Telegram alert
        send_telegram_message(
            f"⚠️ DAILY Trading Skipped\n\n"
            f"Account Size: ₹{ACCOUNT_SIZE:,.0f}\n"
            f"Deployed: ₹{deployed_capital:,.0f}\n"
            f"Available: ₹{effective_capital:,.0f}\n\n"
            f"All capital is deployed. No new positions entered."
        )
        sys.exit(0)

    # Calculate percentage-based allocation (variable position count!)
    allocation_plan = calculate_percentage_allocation(
        candidates_by_category,
        total_capital=effective_capital,
        target_allocation={'large': 0.60, 'mid': 0.20, 'micro': 0.20},
        min_position_size=20000,  # Min ₹20K per position
        max_position_size=75000,  # Max ₹75K per position (reduced from 150K)
        min_score=MIN_SCORE,
        min_rs_rating=MIN_RS_RATING
    )

    # Get selected positions (already filtered and scored)
    selected_positions = select_positions_for_entry(allocation_plan)


    # Apply sector rotation fallback if slots remain unfilled
    selected_positions = apply_sector_rotation_fallback(
        selected_positions, 
        candidates_by_category, 
        effective_capital, 
        max_positions=MAX_DAILY_POSITIONS
    )
    # Calculate total allocated capital from Phase 3
    total_allocated = sum(p.get('position_size', 0) or p.get('capital_allocated', 0) for p in selected_positions)

    # Send pre-trading Telegram notification with regime info
    if os.path.exists(regime_file):
        with open(regime_file, 'r') as f:
            regime_data = json.load(f)

        regime_name = regime_data.get('regime', 'UNKNOWN')
        regime_score = regime_data.get('score', 0)

        pre_trade_msg = f"📊 <b>DAILY TRADING - Pre-Entry Summary</b>\n\n"
        pre_trade_msg += f"<b>Market Regime (8:30 AM):</b> {regime_name}\n"
        pre_trade_msg += f"<b>Regime Score:</b> {regime_score:.1f}\n\n"
        pre_trade_msg += f"<b>Final Deployment Multiplier:</b> {REGIME_MULTIPLIER*100:.0f}%\n"
        pre_trade_msg += f"<b>Positions to Open:</b> {len(selected_positions)}\n"
        pre_trade_msg += f"<b>Capital to Deploy:</b> ₹{total_allocated:,.0f}\n\n"
        pre_trade_msg += f"⏰ Opening positions now..."

        send_telegram_message(pre_trade_msg)

    print(f"\n🔍 PHASE 4: Executing {len(selected_positions)} selected positions...")

    # Track available capital
    available_capital = get_available_cash('DAILY')
    print(f"💰 Available capital: ₹{available_capital:,.0f}")
    positions_entered = 0
    capital_deployed = 0

    # Execute selected positions
    for position in selected_positions:
        ticker = position['ticker']

        # Check for existing position in SAME strategy (prevent duplicate entries)
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT entry_date
                FROM positions
                WHERE ticker = %s AND strategy = %s AND status = 'HOLD'
            """, (ticker, STRATEGY))
            existing = cur.fetchone()
            
            if existing:
                print(f"   ⏭️  SKIPPING {ticker}: Already holding in {STRATEGY} (since {existing['entry_date']})")
                continue

        score = position['score']
        yahoo_price = position.get('price')
        capital_allocated = position.get('position_size') or position.get('capital_allocated')
        df = position['df']

        # SECTOR DIVERSIFICATION LIMIT CHECK (before position entry)
        # Get current positions from portfolio
        current_positions = portfolio.to_dict('records') if not portfolio.empty else []
        sector_limit_ok, sector_limit_reason = check_sector_limit(ticker, current_positions, max_per_sector=MAX_POSITIONS_PER_SECTOR)

        if not sector_limit_ok:
            print(f"   ⏭️  SKIPPING {ticker}: {sector_limit_reason}")
            continue
        else:
            sector = get_stock_sector(ticker)
            print(f"   ✅ {ticker}: Sector limit OK - {sector_limit_reason}")

        # Safety check: Ensure yahoo_price is valid
        if not yahoo_price or not isinstance(yahoo_price, (int, float)):
            print(f"   ⚠️ SKIPPING {ticker}: Invalid price data (got {type(yahoo_price).__name__}: {yahoo_price})")
            continue

        yahoo_price = float(yahoo_price)  # Ensure it's float

        # Get live price from AngelOne (with Yahoo fallback)
        price, price_source = get_live_price(ticker, yahoo_price)
        
        # Skip if price validation failed (mismatch between sources)
        if price is None:
            print(f"   ❌ SKIPPING {ticker}: Price validation failed - sources disagree")
            send_telegram_message(f"⚠️ <b>LIVE - PRICE MISMATCH</b> - {ticker}: AngelOne and Yahoo prices differ too much. Skipping entry.")
            continue
        print(f"   💰 {ticker}: ₹{price:.2f} ({price_source.upper()})")

        # Calculate stop loss based on ATR
        atr = calculate_atr(df, period=14)
        stop_loss = price - (2 * atr) if atr > 0 else price * 0.98  # 2 ATR or 2%

        # POSITION SIZING: Use Phase 3 allocated capital
        # Phase 3 already calculated position sizes based on regime multiplier
        if capital_allocated and capital_allocated > 0:
            # Use Phase 3's allocated amount
            qty = int(capital_allocated / price)
            print(f"   📦 Using Phase 3 allocation: ₹{capital_allocated:,.0f} → {qty} shares")
        else:
            # Fallback to fixed risk (should rarely happen)
            print(f"   ⚠️ No Phase 3 allocation found, using Fixed Risk fallback")
            risk_amount = available_capital * RISK_PER_TRADE_PCT  # Use available capital, not account size
            risk_per_share = price - stop_loss

            if risk_per_share <= 0:
                print(f"   ⚠️ SKIPPING {ticker}: Invalid stop loss (SL >= Entry)")
                continue

            qty = int(risk_amount / risk_per_share)

        if qty == 0:
            print(f"   ⚠️ SKIPPING {ticker}: Position size too small (qty=0)")
            continue

        # Calculate position value
        position_value = qty * price

        # Check if we have enough capital
        if position_value > available_capital:
            print(f"   ⚠️ SKIPPING {ticker}: Insufficient capital (need ₹{position_value:,.0f}, have ₹{available_capital:,.0f})")
            continue

        # Check if position exceeds max position limit
        max_position_value = ACCOUNT_SIZE * MAX_POSITION_PCT  # 15% of capital
        if position_value > max_position_value:
            # Scale down quantity to fit within limit
            qty = int(max_position_value / price)
            if qty == 0:
                print(f"   ⚠️ SKIPPING {ticker}: Price too high for position limit")
                continue
            position_value = qty * price
            print(f"   ⚠️ Position capped at {qty} shares (₹{position_value:,.0f}) due to 15% limit")

        # Calculate take profit using Risk:Reward ratio OR fixed profit target
        # Use whichever comes FIRST (min) for quick exits
        sl_distance = price - stop_loss
        rr_target_per_share = sl_distance * TARGET_RR_RATIO  # 1.5:1 R:R
        fixed_target_per_share = 3000 / qty  # ₹3,000 absolute profit

        # Exit at whichever threshold comes FIRST
        target_profit_per_share = min(rr_target_per_share, fixed_target_per_share)
        take_profit = price + target_profit_per_share

        # Get AI validation BEFORE adding position (Claude 3 Haiku)
        ai_agrees = None
        ai_confidence = None
        ai_reasoning = None
        try:
            from scripts.ai_validator import validate_position, get_verdict_emoji

            # Ensure all numeric fields are float (fix: avoid passing ticker string as price)
            ai_result = validate_position(
                ticker=ticker,
                entry_price=float(price),  # Explicit float conversion
                technical_score=score,
                rs_rating=position.get('rs_rating', 50),
                indicators_fired=position.get('indicators_fired', []),
                df=df
            )
            
            ai_agrees = ai_result.get('agrees')
            ai_confidence = ai_result.get('confidence')
            ai_reasoning = ai_result.get('reasoning')

            # Print AI opinion
            print(f"  🤖 AI Opinion: {ai_result['verdict']} ({ai_result['confidence']:.0%})")
            
            # Send AI opinion to Telegram
            emoji = get_verdict_emoji(ai_result['verdict'])
            ai_msg = f"🤖 <b>{ticker}</b> AI Analysis\n{emoji} {ai_result['verdict']} ({ai_result['confidence']:.0%})\n{ai_result['reasoning']}"
            send_telegram_message(ai_msg)

        except Exception as ai_error:
            print(f"  ⚠️ AI validation failed: {ai_error}")
            # Continue with default values

        # LIVE: Check funds before placing order
        try:
            funds = broker.get_funds()
            available_cash = float(funds.get('availablecash', 0)) if funds else 0
            order_value = price * qty
            
            if available_cash < order_value:
                print(f"   ❌ INSUFFICIENT FUNDS: Need ₹{order_value:,.0f}, have ₹{available_cash:,.0f}")
                send_telegram_message(f"🔴 <b>LIVE - INSUFFICIENT FUNDS</b> - {ticker}: Need ₹{order_value:,.0f}, have ₹{available_cash:,.0f}")
                continue
            
            print(f"   💰 Funds OK: ₹{available_cash:,.0f} available, need ₹{order_value:,.0f}")
        except Exception as fund_error:
            print(f"   ⚠️ Could not verify funds: {fund_error}")
        
        # LIVE: Place actual order via AngelOne
        try:
            print(f"   📤 Placing LIVE BUY order for {ticker}...")
            order_id = broker.place_order(
                symbol=ticker,
                quantity=qty,
                price=None,  # Market order
                order_type='MARKET',
                transaction_type='BUY',
                product_type='DELIVERY'
            )
            
            if not order_id:
                print(f"   ❌ LIVE order failed for {ticker} - skipping")
                send_telegram_message(f"🔴 <b>LIVE ORDER FAILED</b> - {ticker} BUY rejected, Qty: {qty}")
                continue
            
            print(f"   ✅ LIVE order placed: {order_id}")
            
            # Get actual fill price from AngelOne
            import time
            time.sleep(2)  # Wait for order to fill
            actual_price = get_live_price(ticker) or price
            
        except Exception as order_error:
            print(f"   ❌ Order placement error: {order_error}")
            send_telegram_message(f"🔴 <b>LIVE ORDER ERROR</b> - {ticker}: {order_error}")
            continue

        # Add position to database with AI validation data
        try:
            add_position(
                ticker=ticker,
                strategy=STRATEGY,
                entry_price=actual_price,  # Use actual fill price
                quantity=qty,
                stop_loss=stop_loss,
                take_profit=take_profit,
                category=stock_categories.get(ticker, 'Unknown'),
                entry_date=datetime.now().strftime('%Y-%m-%d'),
                ai_agrees=ai_agrees,
                ai_confidence=ai_confidence,
                ai_reasoning=ai_reasoning,
                trading_mode=TRADING_MODE,
                order_id=order_id  # Store AngelOne order ID
            )

            # Debit capital for this position
            position_cost = actual_price * qty
            debit_capital(STRATEGY, position_cost, TRADING_MODE)

            # Track capital deployed
            capital_deployed += position_cost
            available_capital -= position_cost
            positions_entered += 1

            # Log trade
            log_trade(
                ticker=ticker,
                strategy=STRATEGY,
                signal='BUY',
                price=price,
                quantity=qty,
                pnl=0,
                notes=f"Signal score: {score:.0f} | RS: {position.get('rs_rating', 'N/A')}",
                trading_mode=TRADING_MODE
            )

            # Add to local portfolio
            new_row = pd.DataFrame([{
                'Ticker': ticker,
                'Status': 'HOLD',
                'EntryPrice': price,
                'EntryDate': datetime.now().strftime('%Y-%m-%d'),
                'Quantity': qty,
                'StopLoss': stop_loss,
                'TakeProfit': take_profit
            }])
            portfolio = pd.concat([portfolio, new_row], ignore_index=True)

            print(f"   ✅ BOUGHT {ticker} @ ₹{price:.2f} | Qty: {qty} | {stock_categories.get(ticker, 'Unknown')}")

            # Send Telegram alert
            details_str = f"Score: {score:.0f} | RS: {position.get('rs_rating', 'N/A')}"
            send_trade_alert(ticker, 'BUY', price, qty, details_str, strategy=STRATEGY)

        except Exception as e:
            print(f"   ⚠️ Failed to add position {ticker}: {e}")

else:
    print(f"   ℹ️ No qualified candidates found for entry")

print(f"\n✅ Portfolio processing complete")

# Update positions tracker (for dynamic watchlist)
from scripts.position_tracker import update_positions_file
num_positions = len(portfolio[portfolio['Status'] == 'HOLD'])
print(f"✅ Active positions: {num_positions}")

# Update performance metrics
from scripts.performance_tracker import update_results
update_results(portfolio, stock_data)

# Circuit Breaker Monitoring (4% alert / 5% hard stop only - max-hold already processed)
print("\n🛡️ Checking stop-loss circuit breakers...")

for _, row in portfolio[portfolio['Status'] == 'HOLD'].iterrows():
    ticker = row['Ticker']
    entry_price = float(row['EntryPrice'])
    entry_date = row.get('EntryDate', datetime.now().strftime("%Y-%m-%d"))
    qty = int(row['Quantity'])

    # Skip if on hold (check database)
    if is_position_on_hold(ticker, STRATEGY):
        print(f"  ⏸️ {ticker}: On hold (suppressed)")
        continue

    if ticker in stock_data and not stock_data[ticker].empty:
        current_price = float(stock_data[ticker]['Close'].iloc[-1])

        # Check circuit breaker (4% alert, 5% hard stop)
        action, loss, analysis = check_circuit_breaker(
            ticker, entry_price, current_price, entry_date,
            alert_threshold=0.015,  # 1.5% AI analysis alert
            hard_stop=0.025  # 2.5% circuit breaker
        )

        if action == 'CIRCUIT_BREAKER':
            # Hard stop - immediate exit
            print(f"  🔴 CIRCUIT BREAKER: {ticker} | Loss: {analysis['loss_pct']:.2f}%")

            # Format and send message
            msg = format_circuit_breaker_message(ticker, analysis)
            send_telegram_message(msg)

            # Execute exit in database
            pnl = (current_price - entry_price) * qty
            try:
                close_position(ticker, STRATEGY, current_price, pnl)
                update_capital(STRATEGY, pnl)

                log_trade(
                    ticker=ticker,
                    strategy=STRATEGY,
                    signal='SELL',
                    price=current_price,
                    quantity=qty,
                    pnl=pnl,
                    notes=f"Circuit breaker at {analysis['loss_pct']:.2f}%",
                    trading_mode=TRADING_MODE
                )
            except Exception as e:
                print(f"  ❌ Failed to exit position: {e}")

            # Update local portfolio
            portfolio.loc[portfolio['Ticker'] == ticker, 'Status'] = 'SOLD'

            print(f"  ✅ Position exited: {ticker}")

        elif action == 'ALERT':
            # 4% alert - investigate
            print(f"  ⚠️ ALERT: {ticker} | Loss: {analysis['loss_pct']:.2f}%")

            # Analyze drop reason
            drop_analysis = analyze_drop_reason(ticker)

            # Get AI analysis with news
            ai_analysis = None
            try:
                loss_pct = analysis['loss_pct']
                ai_analysis = get_ai_recommendation(
                    ticker=ticker,
                    technical_analysis=drop_analysis,
                    entry_price=entry_price,
                    current_price=current_price,
                    loss_pct=loss_pct
                )
                if ai_analysis:
                    print(f"    🤖 AI: {ai_analysis.get('ai_recommendation')} ({ai_analysis.get('ai_confidence')})")
                    if ai_analysis.get('news_count', 0) > 0:
                        print(f"    📰 Analyzed {ai_analysis['news_count']} recent news articles")
            except Exception as e:
                print(f"    ⚠️ AI analysis failed: {e}")

            # Format alert message
            from scripts.risk_manager import format_alert_message
            msg = format_alert_message(ticker, analysis, drop_analysis, ai_analysis)
            send_telegram_message(msg)

print("✅ Circuit breaker check complete\n")

# Calculate portfolio metrics
metrics = calculate_position_metrics(portfolio, stock_data)

# Get today's trades from database
today_trades_list = get_today_trades(STRATEGY)
today_trades_df = pd.DataFrame(today_trades_list) if today_trades_list else pd.DataFrame()

# Format and send daily report
portfolio_summary = format_portfolio_summary(metrics)
trades_summary = format_trades_today(today_trades_df)
signals_summary = format_signals(signals_generated)

send_daily_report(portfolio_summary, trades_summary, signals_summary, strategy=STRATEGY)

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


# ============================================================================
# SECTOR ROTATION FALLBACK LOGIC
# ============================================================================
def apply_sector_rotation_fallback(selected_positions, all_candidates, effective_capital, max_positions=3):
    """
    If we don't have positions in all categories (Large/Mid/Micro),
    fill remaining slots with sector-diversified picks from available categories.
    
    Logic:
    1. Track which sectors we already have positions in
    2. For each empty slot, find best candidate from a NEW sector
    3. Prefer different sectors over same sector
    """
    if not selected_positions:
        return selected_positions
    
    # Track sectors already selected
    sectors_used = set()
    for pos in selected_positions:
        sector = get_stock_sector(pos.get('ticker', '').replace('.NS', ''))
        if sector:
            sectors_used.add(sector)
    
    print(f"\n🔄 SECTOR ROTATION CHECK:")
    print(f"   Current positions: {len(selected_positions)}/{max_positions}")
    print(f"   Sectors used: {', '.join(sectors_used) if sectors_used else 'None'}")
    
    # If we have all positions, no need for fallback
    if len(selected_positions) >= max_positions:
        print(f"   ✅ All {max_positions} slots filled - no rotation needed")
        return selected_positions
    
    # Calculate remaining slots and capital per slot
    slots_remaining = max_positions - len(selected_positions)
    capital_used = sum(p.get('position_size', 0) or p.get('capital_allocated', 0) for p in selected_positions)
    capital_remaining = effective_capital - capital_used
    capital_per_slot = capital_remaining / slots_remaining if slots_remaining > 0 else 0
    
    print(f"   Slots remaining: {slots_remaining}")
    print(f"   Capital remaining: ₹{capital_remaining:,.0f} (₹{capital_per_slot:,.0f} per slot)")
    
    # Flatten all candidates from all categories
    all_flat = []
    for category, candidates in all_candidates.items():
        for c in candidates:
            c['category'] = category
            all_flat.append(c)
    
    # Sort by score descending
    all_flat.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    # Find candidates from new sectors
    added_count = 0
    for candidate in all_flat:
        if added_count >= slots_remaining:
            break
            
        ticker = candidate.get('ticker', '')
        sector = get_stock_sector(ticker.replace('.NS', ''))
        
        # Skip if already selected or same sector
        if any(p.get('ticker') == ticker for p in selected_positions):
            continue
        if sector and sector in sectors_used:
            continue
        
        # Add this candidate
        candidate['position_size'] = capital_per_slot
        candidate['capital_allocated'] = capital_per_slot
        candidate['rotation_fill'] = True  # Mark as rotation fill
        selected_positions.append(candidate)
        
        if sector:
            sectors_used.add(sector)
        
        print(f"   ➕ Added {ticker} ({sector or 'Unknown'}) - Score: {candidate.get('score', 0):.1f}")
        added_count += 1
    
    if added_count > 0:
        print(f"   ✅ Added {added_count} positions via sector rotation")
    else:
        print(f"   ⚠️ No additional candidates found for rotation")
    
    return selected_positions
