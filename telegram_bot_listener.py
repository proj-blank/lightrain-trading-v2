#!/usr/bin/env python3
"""
Telegram Bot Command Listener for LightRain
Responds to user commands: /help, /status, /positions, /summary
"""
import os
import sys
sys.path.insert(0, '/home/ubuntu/trading')

import requests
import time
from datetime import datetime
from dotenv import load_dotenv
from scripts.db_connection import (
    get_active_positions, get_capital, get_available_cash,
    close_position, log_trade, update_capital, is_position_on_hold,
    add_circuit_breaker_hold
)

import pytz

load_dotenv('/home/ubuntu/trading/.env')

# Import yfinance for live price fetching
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

# Import GlobalMarketFilter for /gc command
from global_market_filter import GlobalMarketFilter

# Import Angel One SmartAPI for real-time index data
try:
    from SmartApi import SmartConnect
    import pyotp
    ANGELONE_AVAILABLE = True
except ImportError:
    ANGELONE_AVAILABLE = False

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
BASE_URL = f'https://api.telegram.org/bot{TOKEN}'

# Angel One credentials
ANGEL_API_KEY = os.getenv('ANGELONE_API_KEY')
ANGEL_CLIENT_CODE = os.getenv('ANGELONE_CLIENT_ID')
ANGEL_PASSWORD = os.getenv('ANGELONE_PASSWORD')
ANGEL_TOTP_SECRET = os.getenv('ANGELONE_TOTP_SECRET')

# Global Angel One session (lazy initialization with auto-refresh)
_angel_session = None
_angel_session_time = None

def get_angel_session(force_refresh=False):
    """
    Get or create Angel One session with auto-refresh on expiry

    Args:
        force_refresh: Force create new session even if one exists

    Returns:
        SmartConnect session or None
    """
    global _angel_session, _angel_session_time

    # Check if session is expired (>23 hours old)
    session_expired = False
    if _angel_session_time:
        age_seconds = time.time() - _angel_session_time
        if age_seconds > 82800:  # 23 hours (give 1 hour buffer before 24hr expiry)
            session_expired = True
            print(f"Angel session expired ({age_seconds/3600:.1f} hours old), refreshing...")

    # Create new session if needed
    if (force_refresh or session_expired or _angel_session is None) and ANGELONE_AVAILABLE:
        try:
            print("Creating new Angel One session...")
            smart_api = SmartConnect(api_key=ANGEL_API_KEY)
            totp = pyotp.TOTP(ANGEL_TOTP_SECRET).now()
            data = smart_api.generateSession(ANGEL_CLIENT_CODE, ANGEL_PASSWORD, totp)
            if data['status']:
                _angel_session = smart_api
                _angel_session_time = time.time()
                print("Angel One session created successfully")
            else:
                print(f"Angel One session failed: {data}")
                _angel_session = None
                _angel_session_time = None
        except Exception as e:
            print(f"Angel One login failed: {e}")
            _angel_session = None
            _angel_session_time = None

    return _angel_session

def get_index_change_angelone(token, symbol_name):
    """
    Get today's percentage change for an index using Angel One

    Args:
        token: Angel One index token (e.g., "99926000" for Nifty 50)
        symbol_name: Display name (e.g., "NIFTY 50")

    Returns:
        float: Percentage change, or None if failed
    """
    # Try with existing session first
    for attempt in [False, True]:  # False = use existing, True = force refresh
        try:
            session = get_angel_session(force_refresh=attempt)
            if not session:
                continue

            # Get LTP data
            ltp_data = session.ltpData("NSE", symbol_name, token)
            if not ltp_data or ltp_data.get('status') != True:
                if attempt == False:  # First attempt failed, try refresh
                    continue
                return None

            data = ltp_data.get('data', {})
            ltp = float(data.get('ltp', 0))
            open_price = float(data.get('open', 0))

            if open_price == 0:
                return None

            change_pct = ((ltp - open_price) / open_price) * 100
            return change_pct
        except Exception as e:
            if attempt == True:  # Second attempt also failed
                print(f"Failed to fetch {symbol_name} after retry: {e}")
                return None
            # First attempt failed, will retry with fresh session

    return None

def send_message(text):
    requests.post(f'{BASE_URL}/sendMessage', json={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'HTML'})

def get_updates(offset=None):
    url = f'{BASE_URL}/getUpdates'
    params = {'timeout': 30, 'offset': offset} if offset else {'timeout': 30}
    try:
        response = requests.get(url, params=params, timeout=35)
        return response.json()
    except:
        return {'ok': False}

def handle_help():
    return """<b>🤖 LightRain Bot Commands</b>

<b>Portfolio & Status:</b>
/help - Show this help
/status - System status
/positions - Active positions (with P&L)
/pnl - Portfolio P&L summary
/gc - Global market check (regime + live data)
/daily - DAILY strategy positions
/swing - SWING strategy positions
/cap - Capital tracker

<b>Circuit Breaker Control:</b>
/hold TICKER - Continue holding despite alert
/exit TICKER - Force exit position now
/exitall - 🚨 KILL SWITCH: Exit ALL & halt trading today
/smart-stop TICKER - Use smart stops (ATR/Chandelier)
"""

def handle_status():
    try:
        daily_pos = len(get_active_positions('DAILY'))
        swing_pos = len(get_active_positions('SWING'))
        return f"""<b>📊 System Status</b>

Active Positions:
  DAILY: {daily_pos} positions
  SWING: {swing_pos} positions

Time: {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S IST')}
Status: ✅ Running
"""
    except Exception as e:
        return f"❌ Error: {e}"

def handle_positions(strategy=None):
    try:
        strategies = [strategy] if strategy else ['DAILY', 'SWING']
        result = "<b>📈 Active Positions</b>\n\n"

        for strat in strategies:
            positions = get_active_positions(strat)
            cash = get_available_cash(strat)
            result += f"<b>{strat}</b> ({len(positions)} positions)\n"
            result += f"Cash: ₹{float(cash):,.0f}\n\n"

            total_pnl = 0
            for p in positions:
                ticker = p['ticker']
                entry_price = float(p['entry_price'])
                qty = int(p['quantity'])

                # Fetch current price
                current_price = entry_price
                if YFINANCE_AVAILABLE:
                    try:
                        stock = yf.Ticker(ticker)
                        hist = stock.history(period='1d')
                        if not hist.empty:
                            current_price = float(hist['Close'].iloc[-1])
                    except:
                        pass

                # Calculate P&L
                pnl = (current_price - entry_price) * qty
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
                total_pnl += pnl

                emoji = "🟢" if pnl >= 0 else "🔴"
                result += f"  {emoji} {ticker}: {qty} @ ₹{entry_price:.2f}\n"
                result += f"     Now: ₹{current_price:.2f} | P&L: ₹{pnl:,.0f} ({pnl_pct:+.1f}%)\n"

            if len(positions) > 0:
                result += f"\n  💰 Total P&L: ₹{total_pnl:,.0f}\n"
            result += "\n"

        return result
    except Exception as e:
        return f"❌ Error: {e}"

def handle_capital():
    try:
        from scripts.db_connection import get_db_cursor
        
        result = "<b>💰 Capital Tracker</b>\n\n"
        
        for strategy in ['DAILY', 'SWING']:
            cap = get_capital(strategy)
            current_capital = float(cap['current_trading_capital'])
            profits = float(cap['total_profits_locked'])
            losses = float(cap['total_losses'])
            
            # Calculate deployed capital (sum of active position values)
            with get_db_cursor() as cur:
                cur.execute("""
                    SELECT COALESCE(SUM(entry_price * quantity), 0) as deployed,
                           COALESCE(SUM(unrealized_pnl), 0) as unrealized_pnl
                    FROM positions 
                    WHERE strategy = %s AND status = 'HOLD'
                """, (strategy,))
                row = cur.fetchone()
                deployed = float(row['deployed'])
                unrealized_pnl = float(row['unrealized_pnl']) if row['unrealized_pnl'] else 0
            
            total_capital = current_capital + deployed
            available = current_capital
            
            result += f"<b>{strategy}</b>\n"
            result += f"  Total Capital: ₹{total_capital:,.0f}\n"
            result += f"  Deployed: ₹{deployed:,.0f}\n"
            result += f"  Available: ₹{available:,.0f}\n"
            result += f"  Unrealized P&L: ₹{unrealized_pnl:,.0f}\n"
            result += f"  Locked Profits: ₹{profits:,.0f}\n"
            result += f"  Losses: ₹{losses:,.0f}\n\n"
        
        return result
    except Exception as e:
        import traceback
        return f"❌ Error: {e}\n{traceback.format_exc()[:200]}"

def handle_pnl():
    """Dedicated P&L summary report"""
    try:
        from scripts.db_connection import get_db_cursor
        
        result = "<b>💰 Portfolio P&L Summary</b>\n"
        result += f"⏰ {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S IST')}\n\n"

        grand_total_pnl = 0

        for strategy in ['DAILY', 'SWING']:
            # Get positions with category and days held
            with get_db_cursor() as cur:
                cur.execute("""
                    SELECT ticker, entry_price, quantity, category, entry_date,
                           CURRENT_DATE - entry_date as days_held,
                           unrealized_pnl
                    FROM positions 
                    WHERE strategy = %s AND status = 'HOLD'
                    ORDER BY entry_date DESC
                """, (strategy,))
                positions = cur.fetchall()
            
            result += f"<b>{strategy}</b> ({len(positions)} positions)\n"

            strategy_pnl = 0
            for p in positions:
                ticker = p['ticker']
                entry_price = float(p['entry_price'])
                qty = int(p['quantity'])
                category = p['category'] or 'Unknown'
                days_held = int(p['days_held']) if p['days_held'] is not None else 0

                # Fetch current price
                current_price = entry_price
                if YFINANCE_AVAILABLE:
                    try:
                        stock = yf.Ticker(ticker)
                        hist = stock.history(period='1d')
                        if not hist.empty:
                            current_price = float(hist['Close'].iloc[-1])
                    except:
                        pass

                pnl = (current_price - entry_price) * qty
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
                strategy_pnl += pnl

                emoji = "🟢" if pnl >= 0 else "🔴"
                
                # Format: TICKER [Category] 5d: ₹1,234 (+2.5%)
                cat_short = category.replace('-cap', '').replace('Microcap', 'Micro')
                result += f"  {emoji} {ticker} [{cat_short}] {days_held}d: ₹{pnl:,.0f} ({pnl_pct:+.1f}%)\n"

            result += f"<b>  Subtotal: ₹{strategy_pnl:,.0f}</b>\n\n"
            grand_total_pnl += strategy_pnl

        # Calculate total portfolio value and P&L %
        total_portfolio_value = 0
        from scripts.db_connection import get_db_cursor
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT COALESCE(SUM(entry_price * quantity), 0) as total_invested
                FROM positions WHERE status = 'HOLD'
            """)
            total_portfolio_value = float(cur.fetchone()['total_invested'])

        pnl_pct = (grand_total_pnl / total_portfolio_value * 100) if total_portfolio_value > 0 else 0

        result += "━━━━━━━━━━━━━━━━\n"
        pnl_emoji = "🟢" if grand_total_pnl >= 0 else "🔴"
        result += f"<b>{pnl_emoji} Total P&L: ₹{grand_total_pnl:,.0f} ({pnl_pct:+.2f}%)</b>\n\n"

        # Add portfolio vs benchmark comparison
        result += "📊 <b>Performance vs Benchmarks (Today)</b>\n"

        # Get today's benchmark data from database
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT nifty50_change_pct, sp500_pct, nasdaq_pct
                FROM eod_history
                WHERE snapshot_date = CURRENT_DATE
                ORDER BY snapshot_time DESC LIMIT 1
            """)
            bench_row = cur.fetchone()

        if bench_row:
            nifty_pct = float(bench_row['nifty50_change_pct'] or 0)
            sp500_pct = float(bench_row['sp500_pct'] or 0)
            nasdaq_pct = float(bench_row['nasdaq_pct'] or 0)

            # Compare with portfolio
            vs_nifty = pnl_pct - nifty_pct
            vs_sp500 = pnl_pct - sp500_pct
            vs_nasdaq = pnl_pct - nasdaq_pct

            nifty_emoji = "🟢" if nifty_pct >= 0 else "🔴"
            sp500_emoji = "🟢" if sp500_pct >= 0 else "🔴"
            nasdaq_emoji = "🟢" if nasdaq_pct >= 0 else "🔴"

            vs_nifty_emoji = "📈" if vs_nifty > 0 else "📉"
            vs_sp500_emoji = "📈" if vs_sp500 > 0 else "📉"
            vs_nasdaq_emoji = "📈" if vs_nasdaq > 0 else "📉"

            result += f"  {nifty_emoji} Nifty 50: {nifty_pct:+.2f}% {vs_nifty_emoji} {vs_nifty:+.2f}%\n"
            result += f"  {sp500_emoji} S&P 500: {sp500_pct:+.2f}% {vs_sp500_emoji} {vs_sp500:+.2f}%\n"
            result += f"  {nasdaq_emoji} Nasdaq: {nasdaq_pct:+.2f}% {vs_nasdaq_emoji} {vs_nasdaq:+.2f}%\n"
            result += "<i>📈 = Outperforming | 📉 = Underperforming</i>\n\n"

        # Add market benchmarks using Angel One
        if ANGELONE_AVAILABLE:
            try:
                result += "📊 <b>Live Market Indices</b>\n"

                benchmarks = {
                    'Nifty 50': ('99926000', 'NIFTY 50'),
                    'Nifty Mid 150': ('99926023', 'NIFTY MIDCAP 150'),
                    'Nifty Small 250': ('99926037', 'NIFTY SMLCAP 250')
                }

                session = get_angel_session()
                if session:
                    for display_name, (token, symbol_name) in benchmarks.items():
                        try:
                            ltp_data = session.ltpData('NSE', symbol_name, token)
                            if ltp_data and ltp_data.get('status'):
                                data = ltp_data.get('data', {})
                                ltp = float(data.get('ltp', 0))
                                open_price = float(data.get('open', 0))
                                if open_price > 0:
                                    change_pct = ((ltp - open_price) / open_price) * 100
                                    emoji = "🟢" if change_pct >= 0 else "🔴"
                                    result += f"  {emoji} {display_name}: {change_pct:+.2f}%\n"
                        except Exception as e:
                            print(f"Failed to fetch {display_name}: {e}")
                            continue
                    
                    result += "<i>Live data from Angel One (NSE)</i>\n"
                else:
                    result += "<i>Market data temporarily unavailable</i>\n"
                    
            except Exception as e:
                print(f"Benchmark fetch error: {e}")
                result += "<i>Market data temporarily unavailable</i>\n"

        return result
    except Exception as e:
        import traceback
        return f"❌ Error: {e}\n{traceback.format_exc()[:300]}"

def handle_gc():
    """Global Check - LIVE global regime using GlobalMarketFilter (refactored Nov 19, 2024)"""
    try:
        import json

        result = "<b>🌍 GLOBAL CHECK (LIVE)</b>\n"
        result += f"⏰ {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S IST')}\n\n"

        # Read morning regime (8:30 AM baseline)
        regime_file = '/home/ubuntu/trading/data/market_regime.json'
        morning_regime = "UNKNOWN"
        morning_score = 0

        if os.path.exists(regime_file):
            with open(regime_file, 'r') as f:
                regime_data = json.load(f)
            morning_regime = regime_data.get('regime', 'UNKNOWN')
            morning_score = regime_data.get('score', 0)

        # Use GlobalMarketFilter for live data (same logic as 8:30 AM check)
        filter_system = GlobalMarketFilter()
        filter_system.fetch_us_markets()      # S&P Futures
        filter_system.fetch_asian_markets()   # Nikkei + Hang Seng
        filter_system.fetch_gold()             # Gold (inverse)
        filter_system.fetch_vix()              # VIX

        # Analyze regime (does NOT save to file/database)
        analysis = filter_system.analyze_regime()

        # Format live market data
        result += "<b>━━━ LIVE GLOBAL MARKETS ━━━</b>\n"

        # S&P Futures
        if 'sp_futures' in filter_system.indicators:
            sp = filter_system.indicators['sp_futures']
            sp_emoji = "🟢" if sp['change_pct'] >= 0 else "🔴"
            result += f"{sp_emoji} S&P Futures: {sp['change_pct']:+.2f}%\n"

        # Nikkei
        if 'nikkei' in filter_system.indicators:
            nikkei = filter_system.indicators['nikkei']
            nikkei_emoji = "🟢" if nikkei['change_pct'] >= 0 else "🔴"
            result += f"{nikkei_emoji} Nikkei: {nikkei['change_pct']:+.2f}%\n"

        # Hang Seng
        if 'hang_seng' in filter_system.indicators:
            hs = filter_system.indicators['hang_seng']
            hs_emoji = "🟢" if hs['change_pct'] >= 0 else "🔴"
            result += f"{hs_emoji} Hang Seng: {hs['change_pct']:+.2f}%\n"

        # Gold (inverse)
        if 'gold' in filter_system.indicators:
            gold = filter_system.indicators['gold']
            gold_emoji = "🟢" if gold['change_pct'] < 0 else "🔴" if gold['change_pct'] > 0 else "⚪"
            result += f"{gold_emoji} Gold: {gold['change_pct']:+.2f}% (inverse)\n"

        # VIX
        if 'vix' in filter_system.indicators:
            vix = filter_system.indicators['vix']
            vix_emoji = "🟢" if vix['value'] < 20 else "🟡" if vix['value'] < 30 else "🔴"
            result += f"{vix_emoji} VIX: {vix['value']:.1f} ({vix['level']})\n"

        # Regime analysis
        regime_emoji = "🟢" if analysis['regime'] == "BULL" else "🟡" if analysis['regime'] in ["NEUTRAL", "CAUTION"] else "🔴"
        sizing_pct = f"{int(analysis['position_sizing_multiplier'] * 100)}%"
        if not analysis['allow_new_entries']:
            sizing_pct += " (HALT)"

        result += f"\n<b>━━━ REGIME ANALYSIS ━━━</b>\n"
        result += f"<b>Total Score:</b> {analysis['score']:.1f}\n"
        result += f"<b>Current Regime:</b> {regime_emoji} {analysis['regime']}\n"
        result += f"<b>Position Sizing:</b> {sizing_pct}\n\n"

        # Comparison with morning
        result += f"<b>Baseline (8:30 AM):</b> {morning_regime} (Score: {morning_score:.1f})\n"

        score_change = analysis['score'] - morning_score
        if abs(score_change) >= 2:
            change_emoji = "📈" if score_change > 0 else "📉"
            result += f"{change_emoji} <b>Score moved {score_change:+.1f} points since morning!</b>\n"

        return result

    except Exception as e:
        import traceback
        return f"❌ Error: {str(e)}\n{traceback.format_exc()[:300]}"

def handle_hold(ticker):
    """Mark position to hold (suppress alerts, wait for hard stop)"""
    try:
        # Check if position exists
        positions = get_active_positions()
        ticker_found = False
        for p in positions:
            if p['ticker'] == ticker:
                ticker_found = True
                break

        if not ticker_found:
            return f"❌ Position {ticker} not found"

        # Add to circuit breaker holds
        add_circuit_breaker_hold(ticker, 'SWING')  # Adjust strategy detection if needed

        return f"""✅ <b>HOLD COMMAND RECEIVED</b>

📊 Ticker: {ticker}

Position will continue holding.
Alert suppressed for today.
Circuit breaker (5%) still active."""

    except Exception as e:
        return f"❌ Error: {e}"

def handle_exit(ticker):
    """Force exit position immediately"""
    try:
        # Find position
        positions = get_active_positions()
        position = None
        for p in positions:
            if p['ticker'] == ticker:
                position = p
                break

        if not position:
            return f"❌ Position {ticker} not found"

        entry_price = float(position['entry_price'])
        qty = int(position['quantity'])
        strategy = position['strategy']

        # Get current price
        current_price = entry_price
        if YFINANCE_AVAILABLE:
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period='1d')
                if not hist.empty:
                    current_price = float(hist['Close'].iloc[-1])
            except:
                pass

        # Calculate P&L
        pnl = (current_price - entry_price) * qty
        pnl_pct = ((current_price - entry_price) / entry_price) * 100

        # Close position
        close_position(ticker, strategy, current_price, pnl)
        update_capital(strategy, pnl)

        # Log trade
        log_trade(
            ticker=ticker,
            strategy=strategy,
            signal='SELL',
            price=current_price,
            quantity=qty,
            pnl=pnl,
            notes='MANUAL-EXIT via Telegram'
        )

        return f"""✅ <b>MANUAL EXIT EXECUTED</b>

📊 Ticker: {ticker}
📥 Entry: ₹{entry_price:.2f}
📤 Exit: ₹{current_price:.2f}
💰 P&L: ₹{pnl:,.0f} ({pnl_pct:+.2f}%)
📦 Qty: {qty}

Position closed per your command."""

    except Exception as e:
        return f"❌ Error exiting position: {e}"

def handle_exitall():
    """KILL SWITCH - Exit all positions and halt trading for the day"""
    try:
        import json
        from datetime import date

        result = "<b>🚨 KILL SWITCH ACTIVATED</b>\n\n"

        # Get all active positions (DAILY + SWING)
        positions = get_active_positions()

        if not positions:
            result += "ℹ️ No active positions to exit.\n\n"
        else:
            result += f"<b>Exiting {len(positions)} positions...</b>\n\n"

            total_pnl = 0
            exit_count = 0

            for position in positions:
                ticker = position['ticker']
                entry_price = float(position['entry_price'])
                qty = int(position['quantity'])
                strategy = position['strategy']

                try:
                    # Get current price
                    current_price = entry_price
                    if YFINANCE_AVAILABLE:
                        try:
                            stock = yf.Ticker(ticker)
                            hist = stock.history(period='1d')
                            if not hist.empty:
                                current_price = float(hist['Close'].iloc[-1])
                        except:
                            pass

                    # Calculate P&L
                    pnl = (current_price - entry_price) * qty
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                    total_pnl += pnl

                    # Close position
                    close_position(ticker, strategy, current_price, pnl)
                    update_capital(strategy, pnl)

                    # Log trade
                    log_trade(
                        ticker=ticker,
                        strategy=strategy,
                        signal='SELL',
                        price=current_price,
                        quantity=qty,
                        pnl=pnl,
                        notes='KILL-SWITCH-EXITALL via Telegram'
                    )

                    # Add to result
                    pnl_emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
                    result += f"{pnl_emoji} {ticker} ({strategy}): ₹{pnl:,.0f} ({pnl_pct:+.2f}%)\n"
                    exit_count += 1

                except Exception as e:
                    result += f"⚠️ {ticker}: Failed - {str(e)[:50]}\n"

            pnl_emoji = "🟢" if total_pnl > 0 else "🔴" if total_pnl < 0 else "⚪"
            result += f"\n<b>Total P&L:</b> {pnl_emoji} ₹{total_pnl:,.0f}\n"
            result += f"<b>Exited:</b> {exit_count}/{len(positions)} positions\n\n"

        # Create HALT flag file (blocks trading for rest of day)
        halt_file = '/home/ubuntu/trading/data/trading_halted.flag'
        halt_data = {
            'date': str(date.today()),
            'timestamp': datetime.now().isoformat(),
            'reason': 'KILL-SWITCH-EXITALL command',
            'triggered_by': 'Telegram'
        }

        os.makedirs(os.path.dirname(halt_file), exist_ok=True)
        with open(halt_file, 'w') as f:
            json.dump(halt_data, f, indent=2)

        result += "🛑 <b>TRADING HALTED FOR TODAY</b>\n"
        result += "✅ No new positions will be opened\n"
        result += f"📅 Halt expires: {date.today()} EOD\n\n"
        result += "<i>Trading will auto-resume tomorrow at 9:15 AM</i>"

        return result

    except Exception as e:
        import traceback
        return f"❌ Kill switch error: {str(e)}\n{traceback.format_exc()[:200]}"

def handle_smart_stop(ticker):
    """Enable smart-stop mode (use ATR/Chandelier stops instead of circuit breaker)"""
    try:
        # Check if position exists
        positions = get_active_positions()
        ticker_found = False
        for p in positions:
            if p['ticker'] == ticker:
                ticker_found = True
                break

        if not ticker_found:
            return f"❌ Position {ticker} not found"

        # In PostgreSQL version, this is handled via circuit_breaker_holds table
        # We can add a special note or use a different mechanism
        # For now, use the hold mechanism with a note
        add_circuit_breaker_hold(ticker, 'SWING', hold_type='SMART_STOP')

        return f"""✅ <b>SMART-STOP MODE ENABLED</b>

📊 Ticker: {ticker}

System will use ATR/Chandelier/Support stops.
Circuit breaker suppressed."""

    except Exception as e:
        return f"❌ Error: {e}"

def process_command(text):
    parts = text.strip().split()
    cmd = parts[0].lower()

    # Simple commands (no arguments)
    if cmd == '/help':
        return handle_help()
    elif cmd == '/status':
        return handle_status()
    elif cmd == '/positions':
        return handle_positions()
    elif cmd == '/pnl':
        return handle_pnl()
    elif cmd == '/gc':
        return handle_gc()
    elif cmd == '/daily':
        return handle_positions('DAILY')
    elif cmd == '/swing':
        return handle_positions('SWING')
    elif cmd == '/cap':
        return handle_capital()

    # KILL SWITCH - Exit all positions and halt trading
    elif cmd == '/exitall':
        return handle_exitall()

    # Commands with ticker argument
    elif cmd == '/hold' and len(parts) == 2:
        ticker = parts[1].upper()
        return handle_hold(ticker)
    elif cmd == '/exit' and len(parts) == 2:
        ticker = parts[1].upper()
        return handle_exit(ticker)
    elif cmd == '/smart-stop' and len(parts) == 2:
        ticker = parts[1].upper()
        return handle_smart_stop(ticker)

    # Unknown or malformed command
    else:
        return "Unknown command or missing arguments. Try /help"

print("🤖 LightRain Telegram Bot Listener Starting...")
print(f"Time: {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%d %b %Y, %H:%M:%S IST')}")
send_message("🤖 LightRain Bot online! Type /help for commands.")

offset = None
while True:
    try:
        updates = get_updates(offset)

        if updates.get('ok') and updates.get('result'):
            for update in updates['result']:
                offset = update['update_id'] + 1

                if 'message' in update and 'text' in update['message']:
                    text = update['message']['text']
                    user_id = str(update['message']['chat']['id'])

                    # Only respond to authorized user
                    if user_id == CHAT_ID:
                        print(f"Command received: {text}")
                        response = process_command(text)
                        send_message(response)

        time.sleep(1)

    except KeyboardInterrupt:
        print("\n👋 Bot stopping...")
        send_message("🤖 Bot going offline")
        break
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)
