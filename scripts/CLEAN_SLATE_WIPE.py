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
        for row in cur.fetchall():
            strategy, deployed = row
            print(f"   {strategy}: ₹{deployed:,.0f}")

        print(f"\n🗑️  Deleting all data...")

        # Delete all positions (HOLD and CLOSED)
        cur.execute("DELETE FROM positions")
        deleted_positions = cur.rowcount
        print(f"   ✓ Deleted {deleted_positions} positions")

        # Delete all trade history
        cur.execute("DELETE FROM trades")
        deleted_trades = cur.rowcount
        print(f"   ✓ Deleted {deleted_trades} trade records")

        # Delete circuit breaker holds
        cur.execute("DELETE FROM circuit_breaker_holds")
        deleted_cb = cur.rowcount
        print(f"   ✓ Deleted {deleted_cb} circuit breaker holds")

        # Reset capital table (if exists)
        try:
            cur.execute("""
                UPDATE capital
                SET current_trading_capital = initial_capital,
                    total_realized_pnl = 0
                WHERE strategy IN ('DAILY', 'SWING')
            """)
            print(f"   ✓ Reset capital table")
        except:
            print(f"   ⚠️ No capital table to reset (ok)")

        # Commit the wipe
        conn.commit()

        print(f"\n✅ CLEAN SLATE COMPLETE!")
        print(f"\n📈 Ready for Monday:")
        print(f"   DAILY: ₹5,00,000 available")
        print(f"   SWING: ₹5,00,000 available")
        print(f"   TOTAL: ₹10,00,000")
        print(f"\n🎯 System will start fresh on Monday morning.")

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
