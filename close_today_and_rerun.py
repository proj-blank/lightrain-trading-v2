#\!/usr/bin/env python3
"""
Close all DAILY positions entered today and re-run daily trading.
This is needed because we fixed the category constraint bug (Micro-cap -> Microcap)
"""

import sys
sys.path.insert(0, '/home/ubuntu/trading')

from scripts.db_connection import get_db_cursor, close_position
from datetime import datetime

print("=" * 80)
print("CLOSING TODAY'S DAILY POSITIONS")
print("=" * 80)
print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Get all DAILY positions entered today
positions_to_close = []

with get_db_cursor() as cur:
    cur.execute("""
        SELECT id, ticker, entry_date, entry_time, entry_price, qty, category
        FROM positions
        WHERE strategy = 'DAILY'
          AND status = 'ACTIVE'
          AND entry_date = CURRENT_DATE
        ORDER BY entry_time
    """)
    positions_to_close = cur.fetchall()

if not positions_to_close:
    print("✅ No DAILY positions from today found. Nothing to close.")
    sys.exit(0)

print(f"Found {len(positions_to_close)} DAILY positions from today:")
print()

for pos in positions_to_close:
    print(f"  {pos['ticker']:15s} | {pos['category']:10s} | "
          f"Qty: {pos['qty']:4d} | Entry: ₹{pos['entry_price']:.2f}")

print()
print("=" * 80)
print("CLOSING POSITIONS...")
print("=" * 80)
print()

# Close each position
closed_count = 0
for pos in positions_to_close:
    position_id = pos['id']
    ticker = pos['ticker']
    entry_price = pos['entry_price']
    qty = pos['qty']
    
    try:
        # Close at entry price (no P&L impact)
        close_position(
            position_id=position_id,
            exit_price=entry_price,
            exit_reason="MANUAL_CLOSE_FOR_RERUN"
        )
        print(f"✅ Closed: {ticker}")
        closed_count += 1
    except Exception as e:
        print(f"❌ Failed to close {ticker}: {e}")

print()
print("=" * 80)
print(f"SUMMARY: Closed {closed_count}/{len(positions_to_close)} positions")
print("=" * 80)
print()
print("Now run: bash run_daily_trading.sh")
print()
