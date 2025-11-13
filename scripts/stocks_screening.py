#!/usr/bin/env python3
"""
stocks_screening.py - NSE Universe Populator

Populates screened_stocks table with 351 NSE stocks for daily/swing strategies.
Runs once daily (early morning before market opens).

Strategies (daily_trading.py, swing_trading.py) read from this table and
apply their own scoring models.
"""

import sys
from datetime import datetime
from scripts.nse_universe import get_nse_universe
from scripts.db_connection import get_db_cursor

print("=" * 80)
print("📊 NSE UNIVERSE SCREENING")
print("=" * 80)
print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Get NSE universe (351 stocks)
universe = get_nse_universe()

total_stocks = 0
for category, tickers in universe.items():
    total_stocks += len(tickers)

print(f"🌍 Universe Size:")
print(f"  Large-caps: {len(universe['large_caps'])} stocks")
print(f"  Mid-caps:   {len(universe['mid_caps'])} stocks")
print(f"  Micro-caps: {len(universe['micro_caps'])} stocks")
print(f"  Total:      {total_stocks} stocks")
print()

# Save to database
print("💾 Saving to database...")

with get_db_cursor() as cur:
    # Delete old data (older than today)
    cur.execute("""
        DELETE FROM screened_stocks
        WHERE last_updated < CURRENT_DATE
    """)
    deleted_count = cur.rowcount

    if deleted_count > 0:
        print(f"  🗑️  Deleted {deleted_count} old stocks")

    # Insert/update stocks
    inserted_count = 0
    updated_count = 0

    for category_key, tickers in universe.items():
        # Convert category key to display name
        category = category_key.replace('_caps', '').capitalize() + '-cap'

        for ticker in tickers:
            cur.execute("""
                INSERT INTO screened_stocks (ticker, category, last_updated)
                VALUES (%s, %s, CURRENT_DATE)
                ON CONFLICT (ticker)
                DO UPDATE SET
                    category = EXCLUDED.category,
                    last_updated = CURRENT_DATE
                RETURNING (xmax = 0) AS inserted
            """, (ticker, category))

            result = cur.fetchone()
            if result['inserted']:
                inserted_count += 1
            else:
                updated_count += 1

    print(f"  ✅ Inserted {inserted_count} new stocks")
    print(f"  🔄 Updated {updated_count} existing stocks")

# Verify the data
print()
print("📊 Verification:")

with get_db_cursor() as cur:
    cur.execute("""
        SELECT category, COUNT(*) as count
        FROM screened_stocks
        WHERE last_updated = CURRENT_DATE
        GROUP BY category
        ORDER BY
            CASE category
                WHEN 'Large-cap' THEN 1
                WHEN 'Mid-cap' THEN 2
                WHEN 'Micro-cap' THEN 3
            END
    """)

    results = cur.fetchall()

    for row in results:
        print(f"  {row['category']:12} {row['count']:3} stocks")

    total = sum(row['count'] for row in results)
    print(f"  {'Total:':12} {total:3} stocks")

print()
print("=" * 80)
print("✅ SCREENING COMPLETE")
print("=" * 80)
print(f"Database: screened_stocks table updated")
print(f"Next step: Daily/swing strategies will read from this table")
print("=" * 80)
