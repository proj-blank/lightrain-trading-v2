#!/usr/bin/env python3
"""
Reset LightRain to clean slate - delete all positions and reset capital
"""
import sys
sys.path.insert(0, '/home/ubuntu/trading')

from scripts.db_connection import get_db_cursor

print("=" * 70)
print("🧹 RESETTING LIGHTRAIN TO CLEAN SLATE")
print("=" * 70)
print("\n⚠️  WARNING: This will:")
print("  - Delete all active positions (HOLD)")
print("  - Archive closed positions to history")
print("  - Reset capital to initial values")
print("  - Clear circuit breaker holds")
print("=" * 70)

input("\nPress ENTER to continue or Ctrl+C to cancel...")

with get_db_cursor() as cur:
    # 1. Show current positions
    print("\n📊 Current Positions:")
    cur.execute("SELECT strategy, COUNT(*) as count FROM positions WHERE status = 'HOLD' GROUP BY strategy")
    for row in cur.fetchall():
        print(f"  {row['strategy']}: {row['count']} positions")

    # 2. Mark all HOLD positions as CLOSED (for historical tracking)
    print("\n📝 Archiving positions as CLOSED...")
    cur.execute("""
        UPDATE positions
        SET status = 'CLOSED',
            updated_at = CURRENT_TIMESTAMP
        WHERE status = 'HOLD'
    """)
    print(f"  ✅ Archived positions")

    # 3. Clear circuit breaker holds
    print("\n🛡️ Clearing circuit breaker holds...")
    cur.execute("DELETE FROM circuit_breaker_holds")
    print("  ✅ Circuit breaker holds cleared")

    # 4. Reset capital tracker
    print("\n💰 Resetting capital tracker...")
    cur.execute("""
        UPDATE capital_tracker
        SET
            current_trading_capital = CASE
                WHEN strategy = 'DAILY' THEN 500000
                WHEN strategy = 'SWING' THEN 1000000
            END,
            total_profits_locked = 0,
            total_losses = 0,
            updated_at = CURRENT_TIMESTAMP
    """)
    print("  ✅ Capital reset:")
    print("     DAILY: ₹500,000")
    print("     SWING: ₹1,000,000")

print("\n" + "=" * 70)
print("✅ CLEAN SLATE COMPLETE!")
print("=" * 70)

# Verify
print("\n📋 Verification:")
with get_db_cursor() as cur:
    cur.execute("SELECT COUNT(*) as count FROM positions WHERE status = 'HOLD'")
    hold_count = cur.fetchone()['count']
    print(f"  Active positions: {hold_count}")

    cur.execute("SELECT * FROM capital_tracker ORDER BY strategy")
    for row in cur.fetchall():
        print(f"\n  {row['strategy']}:")
        print(f"    Trading Capital: ₹{float(row['current_trading_capital']):,.0f}")
        print(f"    Profits Locked: ₹{float(row['total_profits_locked']):,.0f}")
        print(f"    Total Losses: ₹{float(row['total_losses']):,.0f}")

print("\n🎯 Ready to start fresh trading!")
