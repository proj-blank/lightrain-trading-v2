#!/usr/bin/env python3
"""
LIVE Monitor - DAILY strategy positions for TP/SL hits
Uses AngelOne for prices and order execution
Runs every 5 minutes during market hours
Enhanced with regime-based capital reallocation using EXISTING global_market_filter.py
"""
from scripts.angelone_price_fetcher import get_angelone_ltp
from scripts.angelone_broker import AngelOneBroker
from datetime import datetime
from scripts.db_connection import (
    get_db_cursor, close_position, log_trade,
    update_capital, credit_capital, update_position_price,
    get_available_cash
)
from scripts.telegram_bot import send_telegram_message
from global_market_filter import get_current_regime
import os
import subprocess
import sys

STRATEGY = 'DAILY'
TRADING_MODE = 'LIVE'

# Initialize broker
broker = None

def init_broker():
    global broker
    if broker is None:
        broker = AngelOneBroker()
        if not broker.login():
            log("❌ Failed to login to AngelOne broker")
            return False
    return True

def log(msg):
    """Log with timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")

def monitor_positions():
    """Check all DAILY positions for TP/SL hits and exit if needed"""

    # Market hours check: NSE opens at 9:15 AM, closes at 3:30 PM
    now = datetime.now().time()
    market_open = datetime.strptime("09:15", "%H:%M").time()
    market_close = datetime.strptime("15:30", "%H:%M").time()

    if now < market_open:
        log(f"⏰ Market not open yet (current: {now.strftime('%H:%M')}, opens: 09:15)")
        log("   Skipping monitoring - will use stale prices before market opens")
        return

    if now > market_close:
        log(f"⏰ Market closed (current: {now.strftime('%H:%M')}, closed: 15:30)")
        return

    with get_db_cursor() as cur:
        cur.execute("""
            SELECT ticker, entry_price, quantity, stop_loss, take_profit, category
            FROM positions
            WHERE status = 'HOLD' AND strategy = %s
            ORDER BY entry_date DESC
        """, (STRATEGY,))

        positions = cur.fetchall()

    if not positions:
        log("No DAILY positions to monitor")
        return

    log(f"Monitoring {len(positions)} DAILY positions...")
    exits_made = 0

    for pos in positions:
        ticker = pos['ticker']
        entry_price = float(pos['entry_price'])
        qty = int(pos['quantity'])
        stop_loss = float(pos['stop_loss'])
        take_profit = float(pos['take_profit'])

        try:
            # Get current price
            stock = yf.Ticker(ticker)
            hist = stock.history(period='1d')

            if hist.empty:
                log(f"  {ticker}: No data available")
                continue

            current_price = float(hist['Close'].iloc[-1])
            pnl = (current_price - entry_price) * qty
            pnl_pct = ((current_price - entry_price) / entry_price) * 100

            # Update current price in database
            update_position_price(ticker, STRATEGY, current_price)

            # Check for TP hit
            if current_price >= take_profit:
                log(f"  ✅ {ticker} HIT TP @ ₹{current_price:.2f} | P&L: ₹{pnl:,.0f} ({pnl_pct:+.2f}%)")
                
                # LIVE: Place SELL order
                if not init_broker():
                    log(f"  ❌ Cannot place order - broker not connected")
                    continue
                    
                log(f"  📤 Placing LIVE SELL for TP...")
                order_id = broker.place_order(
                    symbol=ticker,
                    quantity=qty,
                    price=None,
                    order_type='MARKET',
                    transaction_type='SELL',
                    product_type='DELIVERY'
                )
                
                if not order_id:
                    log(f"  ❌ SELL order failed for {ticker}")
                    send_telegram_message(f"🔴 LIVE TP SELL FAILED - {ticker}")
                    continue
                
                log(f"  ✅ SELL order placed: {order_id}")

                # Exit position
                close_position(ticker, STRATEGY, current_price, pnl)

                # Credit back original investment
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
                    notes=f"TP Hit @ ₹{take_profit:.2f}"
                )

                # Send Telegram notification
                send_telegram_message(
                    f"🎯 DAILY TP Hit!\n\n"
                    f"Ticker: {ticker}\n"
                    f"Entry: ₹{entry_price:.2f}\n"
                    f"Exit: ₹{current_price:.2f}\n"
                    f"P&L: ₹{pnl:,.0f} ({pnl_pct:+.2f}%)\n"
                    f"Qty: {qty}"
                )

                exits_made += 1

            # Check for SL hit
            elif current_price <= stop_loss:
                log(f"  ⛔ {ticker} HIT SL @ ₹{current_price:.2f} | P&L: ₹{pnl:,.0f} ({pnl_pct:+.2f}%)")
                
                # LIVE: Place SELL order
                if not init_broker():
                    log(f"  ❌ Cannot place order - broker not connected")
                    continue
                    
                log(f"  📤 Placing LIVE SELL for SL...")
                order_id = broker.place_order(
                    symbol=ticker,
                    quantity=qty,
                    price=None,
                    order_type='MARKET',
                    transaction_type='SELL',
                    product_type='DELIVERY'
                )
                
                if not order_id:
                    log(f"  ❌ SELL order failed for {ticker}")
                    send_telegram_message(f"🔴 LIVE SL SELL FAILED - {ticker}")
                    continue
                
                log(f"  ✅ SELL order placed: {order_id}")

                # Exit position
                close_position(ticker, STRATEGY, current_price, pnl)

                # Credit back original investment
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
                    notes=f"SL Hit @ ₹{stop_loss:.2f}"
                )

                # Send Telegram notification
                send_telegram_message(
                    f"🛑 DAILY SL Hit\n\n"
                    f"Ticker: {ticker}\n"
                    f"Entry: ₹{entry_price:.2f}\n"
                    f"Exit: ₹{current_price:.2f}\n"
                    f"P&L: ₹{pnl:,.0f} ({pnl_pct:+.2f}%)\n"
                    f"Qty: {qty}"
                )

                exits_made += 1

            else:
                # Just log current status
                distance_to_tp = ((take_profit - current_price) / current_price) * 100
                distance_to_sl = ((current_price - stop_loss) / current_price) * 100
                log(f"  {ticker}: ₹{current_price:.2f} | P&L: ₹{pnl:,.0f} ({pnl_pct:+.2f}%) | TP: {distance_to_tp:.1f}% away | SL: {distance_to_sl:.1f}% away")

        except Exception as e:
            log(f"  ❌ {ticker}: Error - {e}")
            continue

    if exits_made > 0:
        log(f"✅ Exited {exits_made} position(s)")
    else:
        log("All positions within TP/SL range")

    # ========== REGIME-BASED RE-ENTRY LOGIC DISABLED ==========
    # REASON: Causing collateral damage with unintended re-entries
    # DATE DISABLED: 2026-01-08
    # TO RE-ENABLE: Uncomment the section below
    # ===========================================================
    
    # # REGIME-BASED CAPITAL REALLOCATION (using existing global_market_filter.py)
    # try:
    #     log("\n💰 Checking freed capital for regime-based re-entry...")
    #     available_cash = get_available_cash(STRATEGY)
    #     log(f"   Available capital: ₹{available_cash:,.0f}")
    # 
    #     # Only reallocate if we have significant freed capital (> Rs 1L)
    #     if available_cash > 100000:
    #         log(f"   ✅ Sufficient capital available (> ₹1,00,000)")
    # 
    #         # Check market regime using EXISTING system
    #         log(f"   🌍 Checking market regime using global_market_filter...")
    #         regime_data = get_current_regime()
    # 
    #         if regime_data:
    #             regime = regime_data['regime']
    #             score = regime_data['score']
    #             
    #             # Extract indicator details for display
    #             indicators = regime_data.get('indicators', {})
    #             nikkei = indicators.get('nikkei', {})
    #             hsi = indicators.get('hang_seng', {})
    #             sp_futures = indicators.get('sp_futures', {})
    #             gold = indicators.get('gold', {})
    #             vix = indicators.get('vix', {})
    # 
    #             log(f"   📊 Regime: {regime} (Score: {score:.2f})")
    #             log(f"       Nikkei: {nikkei.get('change_pct', 'N/A'):+.2f}% | HSI: {hsi.get('change_pct', 'N/A'):+.2f}%")
    #             log(f"       S&P Futures: {sp_futures.get('change_pct', 'N/A'):+.2f}% | Gold: {gold.get('change_pct', 'N/A'):+.2f}%")
    #             log(f"       VIX: {vix.get('value', 'N/A'):.2f}")
    # 
    #             # Calculate capital allocation based on YOUR requirements (75% BULL, 50% NEUTRAL, 0% BEAR)
    #             if regime == "BULL":
    #                 allocation_pct = 0.75
    #             elif regime in ["NEUTRAL", "CAUTION"]:  # Treat CAUTION as NEUTRAL
    #                 allocation_pct = 0.50
    #             else:  # BEAR
    #                 allocation_pct = 0.00
    # 
    #             deployable_capital = available_cash * allocation_pct
    # 
    #             log(f"   💼 Capital allocation: {allocation_pct*100:.0f}% = ₹{deployable_capital:,.0f}")
    # 
    #             if deployable_capital > 0:
    #                 log(f"   🔄 Triggering DAILY smart entry with regime-based capital allocation...")
    # 
    #                 # Get path to daily_smart_reentry.py
    #                 script_dir = os.path.dirname(os.path.abspath(__file__))
    #                 daily_smartentry_script = os.path.join(script_dir, 'daily_smart_reentry.py')
    # 
    #                 # Get python path
    #                 python_path = sys.executable
    # 
    #                 # Send Telegram notification before running
    #                 send_telegram_message(
    #                     f"🔄 <b>REGIME-BASED RE-ENTRY TRIGGERED (DAILY)</b>\n\n"
    #                     f"💰 Available: ₹{available_cash:,.0f}\n"
    #                     f"🌍 Regime: {regime} (Score: {score:.2f})\n"
    #                     f"📊 Nikkei: {nikkei.get('change_pct', 'N/A'):+.2f}% | HSI: {hsi.get('change_pct', 'N/A'):+.2f}%\n"
    #                     f"📈 S&P: {sp_futures.get('change_pct', 'N/A'):+.2f}% | Gold: {gold.get('change_pct', 'N/A'):+.2f}%\n"
    #                     f"📉 VIX: {vix.get('value', 'N/A'):.2f}\n\n"
    #                     f"💼 Deploying: ₹{deployable_capital:,.0f} ({allocation_pct*100:.0f}%)\n\n"
    #                     f"⏳ Running smart entry..."
    #                 )
    # 
    #                 # Run daily_smart_reentry.py as subprocess
    #                 log(f"   🚀 Running: {python_path} {daily_smartentry_script}")
    #                 result = subprocess.run(
    #                     [python_path, daily_smartentry_script],
    #                     capture_output=True,
    #                     text=True,
    #                     timeout=300  # 5 minute timeout
    #                 )
    # 
    #                 if result.returncode == 0:
    #                     log(f"   ✅ Smart entry completed successfully")
    #                     send_telegram_message(
    #                         f"✅ <b>DAILY RE-ENTRY COMPLETE</b>\n\n"
    #                         f"Check position updates above ⬆️"
    #                     )
    #                 else:
    #                     log(f"   ❌ Smart entry failed with exit code {result.returncode}")
    #                     log(f"   Error output: {result.stderr}")
    #                     send_telegram_message(
    #                         f"❌ <b>DAILY RE-ENTRY FAILED</b>\n\n"
    #                         f"Exit code: {result.returncode}\n"
    #                         f"Check logs for details"
    #                     )
    #             else:
    #                 log(f"   ⏸️ BEAR regime detected - skipping re-entry (0% allocation)")
    #                 send_telegram_message(
    #                     f"🐻 <b>DAILY RE-ENTRY SKIPPED</b>\n\n"
    #                     f"💰 Available: ₹{available_cash:,.0f}\n"
    #                     f"🌍 Regime: {regime} (Score: {score:.2f})\n"
    #                     f"📊 Nikkei: {nikkei.get('change_pct', 'N/A'):+.2f}% | HSI: {hsi.get('change_pct', 'N/A'):+.2f}%\n"
    #                     f"📈 S&P: {sp_futures.get('change_pct', 'N/A'):+.2f}% | Gold: {gold.get('change_pct', 'N/A'):+.2f}%\n"
    #                     f"📉 VIX: {vix.get('value', 'N/A'):.2f}\n\n"
    #                     f"⚠️ BEAR market conditions - capital preserved"
    #                 )
    # 
    #         else:
    #             log(f"   ⚠️ No regime data available (run global_market_filter.py first)")
    # 
    #     else:
    #         log(f"   ⏸️ Insufficient capital for re-entry (need > ₹1,00,000)")
    # 
    # except Exception as e:
    #     log(f"   ⚠️ Error during regime-based re-entry check: {e}")
    #     import traceback
    #     traceback.print_exc()

if __name__ == '__main__':
    try:
        monitor_positions()
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
