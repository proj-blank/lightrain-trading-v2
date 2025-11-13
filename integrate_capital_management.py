#!/usr/bin/env python3
"""
Integrate capital debit/credit into trading scripts
This ensures capital is properly debited when entering positions and credited when exiting
"""
import re

def integrate_daily_trading():
    """Integrate capital management into daily_trading_pg.py"""
    file_path = '/home/ubuntu/trading/daily_trading_pg.py'

    with open(file_path, 'r') as f:
        content = f.read()

    print("🔧 Integrating capital management into daily_trading_pg.py...")

    # Step 1: Add debit_capital and credit_capital to imports
    old_import = """from scripts.db_connection import (
    get_active_positions, add_position, close_position, log_trade,
    get_capital, update_capital, get_available_cash,
    is_position_on_hold, add_circuit_breaker_hold, get_today_trades,
    get_db_cursor"""

    new_import = """from scripts.db_connection import (
    get_active_positions, add_position, close_position, log_trade,
    get_capital, update_capital, get_available_cash,
    is_position_on_hold, add_circuit_breaker_hold, get_today_trades,
    get_db_cursor, debit_capital, credit_capital"""

    if old_import in content:
        content = content.replace(old_import, new_import)
        print("  ✅ Added debit_capital and credit_capital to imports")
    else:
        print("  ⚠️  Could not find exact import match - may already be updated")

    # Step 2: Add debit_capital after add_position (around line 341)
    old_add_position = """            add_position(
                ticker=ticker,
                strategy=STRATEGY,
                entry_price=price,
                quantity=qty,
                stop_loss=stop_loss,
                take_profit=take_profit,
                category=stock_categories.get(ticker, 'Unknown'),
                entry_date=datetime.now().strftime('%Y-%m-%d')
            )

            # Log trade"""

    new_add_position = """            add_position(
                ticker=ticker,
                strategy=STRATEGY,
                entry_price=price,
                quantity=qty,
                stop_loss=stop_loss,
                take_profit=take_profit,
                category=stock_categories.get(ticker, 'Unknown'),
                entry_date=datetime.now().strftime('%Y-%m-%d')
            )

            # Debit capital for this position
            position_cost = price * qty
            debit_capital(STRATEGY, position_cost)

            # Log trade"""

    if old_add_position in content:
        content = content.replace(old_add_position, new_add_position)
        print("  ✅ Added debit_capital call after add_position")
    else:
        print("  ⚠️  Could not find add_position block - may already be updated")

    # Step 3: Add credit_capital before update_capital at exit points
    # Pattern 1: Exit on take profit/stop loss (around line 275)
    old_exit_1 = """        try:
            close_position(ticker, STRATEGY, current_price, pnl)
            update_capital(STRATEGY, pnl)

            # Log trade"""

    new_exit_1 = """        try:
            close_position(ticker, STRATEGY, current_price, pnl)

            # Credit back the original investment
            original_investment = entry_price * qty
            credit_capital(STRATEGY, original_investment)

            # Update capital with P&L
            update_capital(STRATEGY, pnl)

            # Log trade"""

    # Count and replace all occurrences of this pattern
    exit_count = content.count(old_exit_1)
    if exit_count > 0:
        content = content.replace(old_exit_1, new_exit_1)
        print(f"  ✅ Added credit_capital calls at {exit_count} exit point(s)")
    else:
        print("  ⚠️  Could not find exit pattern - may already be updated")

    # Write back
    with open(file_path, 'w') as f:
        f.write(content)

    print("  ✅ daily_trading_pg.py updated!")


def integrate_swing_trading():
    """Integrate capital management into swing_trading_pg.py"""
    file_path = '/home/ubuntu/trading/swing_trading_pg.py'

    with open(file_path, 'r') as f:
        content = f.read()

    print("\n🔧 Integrating capital management into swing_trading_pg.py...")

    # Step 1: Add debit_capital and credit_capital to imports
    old_import = """from scripts.db_connection import (
    get_active_positions, add_position, close_position, log_trade,
    get_capital, update_capital, get_available_cash,
    is_position_on_hold, add_circuit_breaker_hold,
    get_db_cursor"""

    new_import = """from scripts.db_connection import (
    get_active_positions, add_position, close_position, log_trade,
    get_capital, update_capital, get_available_cash,
    is_position_on_hold, add_circuit_breaker_hold,
    get_db_cursor, debit_capital, credit_capital"""

    if old_import in content:
        content = content.replace(old_import, new_import)
        print("  ✅ Added debit_capital and credit_capital to imports")
    else:
        print("  ⚠️  Could not find exact import match - may already be updated")

    # Step 2: Add debit_capital after add_position (around line 542)
    old_add_position = """        try:
            add_position(
                ticker=ticker,
                strategy=STRATEGY,
                entry_price=price,
                quantity=qty,
                stop_loss=stop_loss,
                take_profit=take_profit,
                category=cat_label,
                entry_date=current_date.strftime('%Y-%m-%d')
            )
        except Exception as e:
            log(f"  ❌ Failed to add position to database: {e}")
            continue"""

    new_add_position = """        try:
            add_position(
                ticker=ticker,
                strategy=STRATEGY,
                entry_price=price,
                quantity=qty,
                stop_loss=stop_loss,
                take_profit=take_profit,
                category=cat_label,
                entry_date=current_date.strftime('%Y-%m-%d')
            )

            # Debit capital for this position
            position_cost = price * qty
            debit_capital(STRATEGY, position_cost)

        except Exception as e:
            log(f"  ❌ Failed to add position to database: {e}")
            continue"""

    if old_add_position in content:
        content = content.replace(old_add_position, new_add_position)
        print("  ✅ Added debit_capital call after add_position")
    else:
        print("  ⚠️  Could not find add_position block - may already be updated")

    # Step 3: Add credit_capital before update_capital at exit points
    old_exit = """        try:
            close_position(ticker, STRATEGY, current_price, pnl)
            update_capital(STRATEGY, pnl)

            # Log"""

    new_exit = """        try:
            close_position(ticker, STRATEGY, current_price, pnl)

            # Credit back the original investment
            original_investment = entry_price * qty
            credit_capital(STRATEGY, original_investment)

            # Update capital with P&L
            update_capital(STRATEGY, pnl)

            # Log"""

    # Count and replace all occurrences
    exit_count = content.count(old_exit)
    if exit_count > 0:
        content = content.replace(old_exit, new_exit)
        print(f"  ✅ Added credit_capital calls at {exit_count} exit point(s)")
    else:
        print("  ⚠️  Could not find exit pattern - may already be updated")

    # Write back
    with open(file_path, 'w') as f:
        f.write(content)

    print("  ✅ swing_trading_pg.py updated!")


if __name__ == '__main__':
    print("=" * 60)
    print("INTEGRATING CAPITAL MANAGEMENT")
    print("=" * 60)
    print()
    print("This will:")
    print("  1. Add debit_capital and credit_capital to imports")
    print("  2. Debit capital when entering positions")
    print("  3. Credit capital when exiting positions")
    print()

    integrate_daily_trading()
    integrate_swing_trading()

    print()
    print("=" * 60)
    print("✅ CAPITAL MANAGEMENT INTEGRATION COMPLETE!")
    print("=" * 60)
    print()
    print("Summary:")
    print("  - Capital will be debited when entering positions")
    print("  - Capital will be credited when exiting positions")
    print("  - Capital utilization will now be accurate")
    print()
    print("Next: Run a dry-run test to verify the changes work correctly")
