#!/usr/bin/env python3
"""
Fix capital tracker to reflect invested capital
"""
import sys
sys.path.insert(0, '/home/ubuntu/trading')

from scripts.db_connection import get_db_cursor

print("=" * 70)
print("Fixing Capital Tracker")
print("=" * 70)

with get_db_cursor() as cur:
    # Calculate invested capital from positions
    print("\nCalculating invested capital from positions...")
    cur.execute("""
        SELECT
            strategy,
            COUNT(*) as position_count,
            SUM(entry_price * quantity) as invested_capital
        FROM positions
        WHERE status = 'HOLD'
        GROUP BY strategy
        ORDER BY strategy;
    """)

    positions = cur.fetchall()

    for pos in positions:
        strategy = pos['strategy']
        count = pos['position_count']
        invested = float(pos['invested_capital'])

        print(f"\n{strategy}:")
        print(f"  Positions: {count}")
        print(f"  Invested: ₹{invested:,.2f}")

        # Get initial capital
        if strategy == 'DAILY':
            initial_capital = 500000
        else:  # SWING
            initial_capital = 1000000

        # Calculate available cash
        available_cash = initial_capital - invested

        print(f"  Initial Capital: ₹{initial_capital:,.2f}")
        print(f"  Available Cash: ₹{available_cash:,.2f}")

        # Update capital tracker
        cur.execute("""
            UPDATE capital_tracker
            SET current_trading_capital = %s
            WHERE strategy = %s
        """, (available_cash, strategy))

        print(f"  ✅ Updated capital tracker")

print("\n" + "=" * 70)
print("Capital tracker fixed successfully!")
print("=" * 70)

# Verify
print("\nVerifying updated values:")
with get_db_cursor() as cur:
    cur.execute("SELECT * FROM capital_tracker ORDER BY strategy")
    for row in cur.fetchall():
        print(f"\n{row['strategy']}:")
        print(f"  Trading Capital: ₹{float(row['current_trading_capital']):,.2f}")
        print(f"  Profits Locked: ₹{float(row['total_profits_locked']):,.2f}")
        print(f"  Total Losses: ₹{float(row['total_losses']):,.2f}")
