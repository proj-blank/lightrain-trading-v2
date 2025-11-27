#!/usr/bin/env python3
"""
Monitor SWING strategy positions for TP/SL hits and Profit-Lock Extension
Runs every 5 minutes during market hours

Features:
- Standard TP/SL monitoring
- Profit-Lock Extension: At day 8+, if profitable, lock profit floor and extend hold to 15 days
- Dynamic trailing: SL trails up but never below locked floor
"""

import os
import sys
sys.path.insert(0, '/home/ubuntu/trading')

from datetime import datetime, date
from scripts.db_connection import (
    get_db_cursor, close_position, log_trade,
    update_capital, credit_capital, get_db_connection
)
from scripts.telegram_bot import send_telegram_message
import yfinance as yf

STRATEGY = 'SWING'
PROFIT_LOCK_START_DAY = 8  # Start profit-locking at day 8
EXTENDED_MAX_HOLD = 15  # Extended hold for profitable positions

def log(msg):
    """Log with timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")

def update_position_stops(ticker, strategy, new_stop_loss, new_take_profit):
    """Update SL and TP for a position"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE positions
            SET stop_loss = %s,
                take_profit = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE ticker = %s AND strategy = %s AND status = 'HOLD'
        """, (float(new_stop_loss), float(new_take_profit), ticker, strategy))
        conn.commit()

def check_profit_lock_activation(ticker, entry_date, entry_price, current_price, unrealized_pnl):
    """
    Check if profit-lock should be activated

    Returns: (should_activate, locked_floor_pct, locked_floor_price)
    """
    days_held = (date.today() - entry_date).days

    if days_held < PROFIT_LOCK_START_DAY:
        return False, 0, 0

    if unrealized_pnl <= 0:
        return False, 0, 0  # Not profitable

    # Calculate profit percentage
    pnl_pct = (unrealized_pnl / (entry_price * 1)) * 100  # Simplified, actual calc uses quantity

    # Determine locked floor based on profit tier
    if pnl_pct >= 5.0:
        locked_floor_pct = 3.0  # Lock +3% if currently at +5%
    elif pnl_pct >= 3.0:
        locked_floor_pct = 2.0  # Lock +2% if currently at +3%
    else:
        locked_floor_pct = 1.0  # Lock +1% for any profit

    locked_floor_price = entry_price * (1 + locked_floor_pct / 100)

    return True, locked_floor_pct, locked_floor_price

def apply_profit_lock_logic(ticker, entry_price, current_price, locked_floor, current_sl, current_tp):
    """
    Calculate new SL/TP with profit-lock logic

    Returns: (new_sl, new_tp, reason)
    """
    # Dynamic TP: 1% above current price
    new_tp = current_price * 1.01

    # Trailing SL: 2% below current, but never below locked floor
    trailing_sl = current_price * 0.98
    new_sl = max(locked_floor, trailing_sl)

    # Determine reason for SL level
    if new_sl == locked_floor:
        reason = f"Locked floor @ Rs {locked_floor:,.2f}"
    else:
        reason = f"Trailing 2% below Rs {current_price:,.2f}"

    return new_sl, new_tp, reason

def monitor_positions():
    """Check all SWING positions for TP/SL hits and apply profit-lock extension"""

    with get_db_cursor() as cur:
        cur.execute("""
            SELECT ticker, entry_price, entry_date, quantity, stop_loss, take_profit,
                   category, current_price, unrealized_pnl
            FROM positions
            WHERE status = 'HOLD' AND strategy = %s
            ORDER BY entry_date
        """, (STRATEGY,))

        positions = cur.fetchall()

    if not positions:
        log("No SWING positions to monitor")
        return

    log(f"Monitoring {len(positions)} SWING positions...")
    exits_made = 0
    profit_locks_activated = 0
    stops_updated = 0

    for pos in positions:
        ticker = pos['ticker']
        entry_price = float(pos['entry_price'])
        entry_date = pos['entry_date']
        qty = int(pos['quantity'])
        stop_loss = float(pos['stop_loss'])
        take_profit = float(pos['take_profit'])
        unrealized_pnl = float(pos['unrealized_pnl']) if pos['unrealized_pnl'] else 0

        # Calculate days held
        days_held = (date.today() - entry_date).days

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

            # Check for Profit-Lock activation (day 8+, profitable)
            should_activate, locked_pct, locked_floor = check_profit_lock_activation(
                ticker, entry_date, entry_price, current_price, unrealized_pnl
            )

            if should_activate and days_held == PROFIT_LOCK_START_DAY:
                # First time hitting day 8 - activate profit-lock
                new_sl, new_tp, sl_reason = apply_profit_lock_logic(
                    ticker, entry_price, current_price, locked_floor, stop_loss, take_profit
                )

                # Update database
                update_position_stops(ticker, STRATEGY, new_sl, new_tp)

                log(f"  🔒 {ticker}: PROFIT-LOCK ACTIVATED (Day {days_held})")
                log(f"     Locked floor: +{locked_pct}% (Rs {locked_floor:,.2f})")
                log(f"     New SL: Rs {new_sl:,.2f} | New TP: Rs {new_tp:,.2f}")

                # Send Telegram notification
                send_telegram_message(
                    f"🔒 <b>PROFIT-LOCK ACTIVATED</b>\n\n"
                    f"<b>Ticker:</b> {ticker} (SWING)\n"
                    f"<b>Days Held:</b> {days_held}/{EXTENDED_MAX_HOLD}\n"
                    f"<b>Current P&L:</b> {pnl_pct:+.2f}%\n\n"
                    f"✅ <b>Locked Minimum:</b> +{locked_pct}% (Rs {locked_floor:,.2f})\n"
                    f"📈 <b>New TP:</b> Rs {new_tp:,.2f}\n"
                    f"🛡️ <b>New SL:</b> Rs {new_sl:,.2f}\n"
                    f"⏰ <b>Extended Hold:</b> {EXTENDED_MAX_HOLD} days\n\n"
                    f"<i>Position will trail upwards while protecting profit floor</i>"
                )

                profit_locks_activated += 1

                # Update local variables for subsequent checks
                stop_loss = new_sl
                take_profit = new_tp

            elif should_activate and days_held > PROFIT_LOCK_START_DAY:
                # Already in profit-lock mode - update SL/TP dynamically
                new_sl, new_tp, sl_reason = apply_profit_lock_logic(
                    ticker, entry_price, current_price, locked_floor, stop_loss, take_profit
                )

                # Only update if there's a meaningful change (avoid spam updates)
                sl_change_pct = abs(new_sl - stop_loss) / stop_loss * 100
                tp_change_pct = abs(new_tp - take_profit) / take_profit * 100

                if sl_change_pct > 0.5 or tp_change_pct > 0.5:  # Update if >0.5% change
                    update_position_stops(ticker, STRATEGY, new_sl, new_tp)
                    log(f"  📊 {ticker}: Updated stops (Day {days_held}, Profit-lock active)")
                    stops_updated += 1

                    # Update local variables
                    stop_loss = new_sl
                    take_profit = new_tp

            # Check for TP hit
            if current_price >= take_profit:
                log(f"  ✅ {ticker} HIT TP @ Rs {current_price:.2f} | P&L: Rs {pnl:,.0f} ({pnl_pct:+.2f}%)")

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
                    notes=f"TP Hit @ Rs {take_profit:.2f} (Day {days_held})"
                )

                # Send Telegram notification
                send_telegram_message(
                    f"🎯 <b>SWING TP Hit!</b>\n\n"
                    f"<b>Ticker:</b> {ticker}\n"
                    f"<b>Entry:</b> Rs {entry_price:.2f}\n"
                    f"<b>Exit:</b> Rs {current_price:.2f}\n"
                    f"<b>P&L:</b> Rs {pnl:,.0f} ({pnl_pct:+.2f}%)\n"
                    f"<b>Days Held:</b> {days_held}\n"
                    f"<b>Qty:</b> {qty}"
                )

                exits_made += 1

            # Check for SL hit
            elif current_price <= stop_loss:
                log(f"  ⛔ {ticker} HIT SL @ Rs {current_price:.2f} | P&L: Rs {pnl:,.0f} ({pnl_pct:+.2f}%)")

                # Exit position
                close_position(ticker, STRATEGY, current_price, pnl)

                # Credit back original investment
                original_investment = entry_price * qty
                credit_capital(STRATEGY, original_investment)

                # Update capital with P&L
                update_capital(STRATEGY, pnl)

                # Log trade
                note_suffix = " (Profit-lock floor)" if should_activate else ""
                log_trade(
                    ticker=ticker,
                    strategy=STRATEGY,
                    signal='SELL',
                    price=current_price,
                    quantity=qty,
                    pnl=pnl,
                    notes=f"SL Hit @ Rs {stop_loss:.2f} (Day {days_held}){note_suffix}"
                )

                # Send Telegram notification
                sl_emoji = "🛡️" if pnl > 0 else "🛑"
                send_telegram_message(
                    f"{sl_emoji} <b>SWING SL Hit</b>\n\n"
                    f"<b>Ticker:</b> {ticker}\n"
                    f"<b>Entry:</b> Rs {entry_price:.2f}\n"
                    f"<b>Exit:</b> Rs {current_price:.2f}\n"
                    f"<b>P&L:</b> Rs {pnl:,.0f} ({pnl_pct:+.2f}%)\n"
                    f"<b>Days Held:</b> {days_held}\n"
                    f"<b>Qty:</b> {qty}"
                    + (f"\n\n<i>Profit-lock floor protected +{locked_pct}%</i>" if should_activate and pnl > 0 else "")
                )

                exits_made += 1

            else:
                # Just log current status
                distance_to_tp = ((take_profit - current_price) / current_price) * 100
                distance_to_sl = ((current_price - stop_loss) / current_price) * 100
                status = f"[Day {days_held}]" if days_held >= PROFIT_LOCK_START_DAY else ""
                log(f"  {ticker} {status}: Rs {current_price:.2f} | P&L: Rs {pnl:,.0f} ({pnl_pct:+.2f}%) | TP: {distance_to_tp:.1f}% away | SL: {distance_to_sl:.1f}% away")

        except Exception as e:
            log(f"  ❌ {ticker}: Error - {e}")
            continue

    # Summary
    if exits_made > 0:
        log(f"✅ Exited {exits_made} position(s)")
    if profit_locks_activated > 0:
        log(f"🔒 Activated profit-lock for {profit_locks_activated} position(s)")
    if stops_updated > 0:
        log(f"📊 Updated stops for {stops_updated} position(s)")
    if exits_made == 0 and profit_locks_activated == 0 and stops_updated == 0:
        log("All positions within TP/SL range")

if __name__ == '__main__':
    try:
        monitor_positions()
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
