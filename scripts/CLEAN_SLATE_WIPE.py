#!/usr/bin/env python3
"""
CLEAN SLATE - Complete Portfolio Wipe
⚠️ DANGER: This will DELETE ALL positions and P&L history!

Use this ONLY when you want to start completely fresh.
"""

import psycopg2
from datetime import datetime
import pytz

# Database config
DB_CONFIG = {
    'dbname': 'lightrain',
    'user': 'lightrain_user',
    'password': 'LightRain2025@Secure',
    'host': 'localhost',
    'port': '5432'
}

def confirm_wipe():
    """Ask for confirmation before wiping"""
    print("=" * 80)
    print("⚠️  CLEAN SLATE - COMPLETE PORTFOLIO WIPE")
    print("=" * 80)
    print()
    print("This will DELETE:")
    print("  1. ALL open positions (HOLD status)")
    print("  2. ALL closed positions (CLOSED status)")
    print("  3. ALL trade history")
    print("  4. ALL P&L records")
    print()
    print("Starting fresh with:")
    print("  - DAILY: ₹5,00,000")
    print("  - SWING: ₹5,00,000")
    print("  - TOTAL: ₹10,00,000")
    print()
    print("=" * 80)

    response = input("Type 'WIPE EVERYTHING' to confirm: ")
    return response == "WIPE EVERYTHING"

def wipe_all_data():
    """Wipe all positions and trading data"""
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False  # Explicit transaction control
    cur = conn.cursor()

    try:
        print("\n🔥 Starting clean wipe...")

        # Get counts before wipe
        cur.execute("SELECT COUNT(*) FROM positions WHERE status = 'HOLD'")
        hold_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM positions WHERE status = 'CLOSED'")
        closed_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM trades")
        trades_count = cur.fetchone()[0]

        print(f"\n📊 Current State:")
        print(f"   HOLD positions: {hold_count}")
        print(f"   CLOSED positions: {closed_count}")
        print(f"   Trade records: {trades_count}")

        # Calculate total deployed capital before wipe
        cur.execute("""
            SELECT
                strategy,
                SUM(entry_price * quantity) as deployed
            FROM positions
            WHERE status = 'HOLD'
            GROUP BY strategy
        """)

        print(f"\n💰 Deployed Capital (will be wiped):")
        deployed_rows = cur.fetchall()
        if deployed_rows:
            for row in deployed_rows:
                strategy, deployed = row
                print(f"   {strategy}: ₹{deployed:,.0f}")
        else:
            print(f"   No deployed capital (already clean)")

        print(f"\n🗑️  Deleting all data...")

        # Delete all positions (HOLD and CLOSED)
        cur.execute("DELETE FROM positions")
        deleted_positions = cur.rowcount
        print(f"   ✓ DELETE FROM positions: {deleted_positions} rows")

        # Delete all trade history
        cur.execute("DELETE FROM trades")
        deleted_trades = cur.rowcount
        print(f"   ✓ DELETE FROM trades: {deleted_trades} rows")

        # Delete circuit breaker holds
        cur.execute("DELETE FROM circuit_breaker_holds")
        deleted_cb = cur.rowcount
        print(f"   ✓ DELETE FROM circuit_breaker_holds: {deleted_cb} rows")

        # Reset capital_tracker table to fresh ₹5L each
        try:
            cur.execute("""
                UPDATE capital_tracker
                SET current_trading_capital = 500000,
                    total_profits_locked = 0,
                    total_losses = 0,
                    last_updated = CURRENT_TIMESTAMP
                WHERE strategy IN ('DAILY', 'SWING')
            """)
            updated_rows = cur.rowcount
            print(f"   ✓ Reset capital_tracker: {updated_rows} strategies reset to ₹5,00,000 each")
        except Exception as e:
            print(f"   ⚠️ Could not reset capital_tracker: {e}")

        # Explicit commit
        print(f"\n💾 Committing transaction...")
        conn.commit()
        print(f"   ✓ COMMIT successful")

        # Verify deletion worked
        print(f"\n🔍 Verifying deletion...")
        cur.execute("SELECT COUNT(*) FROM positions")
        pos_verify = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM trades")
        trades_verify = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM circuit_breaker_holds")
        cb_verify = cur.fetchone()[0]

        print(f"   positions: {pos_verify}")
        print(f"   trades: {trades_verify}")
        print(f"   circuit_breaker_holds: {cb_verify}")

        if pos_verify == 0 and trades_verify == 0:
            print(f"\n✅ CLEAN SLATE COMPLETE!")
            print(f"\n📈 Ready for Monday:")
            print(f"   DAILY: ₹5,00,000 available")
            print(f"   SWING: ₹5,00,000 available")
            print(f"   TOTAL: ₹10,00,000")
            print(f"\n🎯 System will start fresh on Monday morning.")
        else:
            print(f"\n⚠️ WARNING: Some data still remains after deletion!")
            print(f"   This should not happen. Manual cleanup may be required.")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERROR: {e}")
        print("   Rollback performed. No changes made.")
        raise

    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)

    print(f"\nCurrent time: {now.strftime('%d %b %Y, %H:%M:%S IST')}")

    if confirm_wipe():
        print("\n⏳ Processing wipe...")
        wipe_all_data()
    else:
        print("\n❌ Wipe cancelled. No changes made.")
