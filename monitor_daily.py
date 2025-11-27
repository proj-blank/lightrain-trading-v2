#!/usr/bin/env python3
"""
Monitor DAILY strategy positions for TP/SL hits
Runs every 5 minutes during market hours
"""
import yfinance as yf
from datetime import datetime
from scripts.db_connection import (
    get_db_cursor, close_position, log_trade,
    update_capital, credit_capital, update_position_price,
    get_available_cash
)
from scripts.telegram_bot import send_telegram_message
import os
import subprocess
import sys

STRATEGY = 'DAILY'

def log(msg):
    """Log with timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")

def monitor_positions():
    """Check all DAILY positions for TP/SL hits and exit if needed"""

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

    # Intraday capital reallocation logic
    if exits_made > 0:
        try:
            log("\n💰 Checking freed capital for intraday reallocation...")
            available_cash = get_available_cash(STRATEGY)
            log(f"   Available capital: ₹{available_cash:,.0f}")

            # Only reallocate if we have significant freed capital (> Rs 1L)
            if available_cash > 100000:
                log(f"   ✅ Sufficient capital available (> ₹1,00,000)")
                log(f"   🔄 Triggering intraday reallocation pipeline...")

                # Set environment flag for midday entry mode
                os.environ['MIDDAY_ENTRY'] = 'true'

                # Get path to daily_trading_pg.py
                script_dir = os.path.dirname(os.path.abspath(__file__))
                daily_trading_script = os.path.join(script_dir, 'daily_trading_pg.py')

                # Get python path (same as current interpreter)
                python_path = sys.executable

                # Send Telegram notification before running
                send_telegram_message(
                    f"🔄 <b>INTRADAY REALLOCATION TRIGGERED</b>\n\n"
                    f"💰 Freed Capital: ₹{available_cash:,.0f}\n"
                    f"📊 Exited Positions: {exits_made}\n\n"
                    f"Running full pipeline:\n"
                    f"1️⃣ Global market check\n"
                    f"2️⃣ Stock screening\n"
                    f"3️⃣ Signal generation\n"
                    f"4️⃣ Position allocation\n\n"
                    f"⏳ This may take 2-3 minutes..."
                )

                # Run daily_trading_pg.py as subprocess
                log(f"   🚀 Running: {python_path} {daily_trading_script}")
                result = subprocess.run(
                    [python_path, daily_trading_script],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )

                if result.returncode == 0:
                    log(f"   ✅ Intraday reallocation completed successfully")
                    send_telegram_message(
                        f"✅ <b>INTRADAY REALLOCATION COMPLETE</b>\n\n"
                        f"Check position updates above ⬆️"
                    )
                else:
                    log(f"   ❌ Intraday reallocation failed with exit code {result.returncode}")
                    log(f"   Error output: {result.stderr}")
                    send_telegram_message(
                        f"❌ <b>INTRADAY REALLOCATION FAILED</b>\n\n"
                        f"Exit code: {result.returncode}\n"
                        f"Check logs for details"
                    )

                # Clean up environment variable
                if 'MIDDAY_ENTRY' in os.environ:
                    del os.environ['MIDDAY_ENTRY']

            else:
                log(f"   ⏸️ Insufficient capital for reallocation (need > ₹1,00,000)")

        except Exception as e:
            log(f"   ⚠️ Error during intraday reallocation check: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    try:
        monitor_positions()
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
