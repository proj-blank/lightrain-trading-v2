#!/usr/bin/env python3
import sys
sys.path.insert(0, "/home/ubuntu/trading")
from scripts.db_connection import get_db_connection

print("Checking screened_stocks data...")

with get_db_connection() as conn:
    with conn.cursor() as cur:
        # First, check what data exists
        cur.execute("SELECT last_updated, category, COUNT(*) FROM screened_stocks GROUP BY last_updated, category ORDER BY last_updated DESC")
        print("\nCurrent screened_stocks data:")
        for row in cur.fetchall():
            print(f"  {row[0]} - {row[1]}: {row[2]} stocks")

        # Delete ALL data (will be repopulated by screening)
        cur.execute("DELETE FROM screened_stocks")
        deleted = cur.rowcount
        print(f"\n✅ Deleted {deleted} rows (all old data cleared)")

        # Show remaining data
        cur.execute("SELECT last_updated, category, COUNT(*) FROM screened_stocks GROUP BY last_updated, category ORDER BY last_updated DESC")
        print("\nRemaining data:")
        remaining = cur.fetchall()
        if remaining:
            for row in remaining:
                print(f"  {row[0]} - {row[1]}: {row[2]} stocks")
        else:
            print("  (No data remaining - ready for fresh screening)")
