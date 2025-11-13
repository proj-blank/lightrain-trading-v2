#!/usr/bin/env python3
"""
Download and setup AngelOne symbol master in PostgreSQL
This enables proper symbol-to-token mapping for all NSE/BSE stocks
"""
import sys
sys.path.insert(0, '/home/ubuntu/trading')

import requests
import json
from scripts.db_connection import get_db_cursor
from scripts.angelone_api import get_angelone_api

print("=" * 70)
print("AngelOne Symbol Master Setup")
print("=" * 70)

# Step 1: Create symbols table
print("\n1. Creating angelone_symbols table...")
with get_db_cursor() as cur:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS angelone_symbols (
            id SERIAL PRIMARY KEY,
            token VARCHAR(20) NOT NULL,
            symbol VARCHAR(50) NOT NULL,
            name VARCHAR(200),
            expiry VARCHAR(20),
            strike VARCHAR(20),
            lotsize INTEGER,
            instrumenttype VARCHAR(20),
            exch_seg VARCHAR(10) NOT NULL,
            tick_size DECIMAL(10, 4),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(token, exch_seg)
        );

        CREATE INDEX IF NOT EXISTS idx_symbol_lookup
        ON angelone_symbols(symbol, exch_seg);

        CREATE INDEX IF NOT EXISTS idx_token_lookup
        ON angelone_symbols(token);
    """)
    print("✅ Table and indexes created")

# Step 2: Download symbol master from AngelOne
print("\n2. Downloading symbol master from AngelOne...")
try:
    # AngelOne provides symbol master at this endpoint
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

    print(f"   Fetching from: {url}")
    response = requests.get(url, timeout=30)

    if response.status_code == 200:
        symbols_data = response.json()
        print(f"   ✅ Downloaded {len(symbols_data)} symbols")

        # Step 3: Filter and load NSE symbols
        print("\n3. Loading NSE symbols into database...")

        with get_db_cursor() as cur:
            # Clear existing data
            cur.execute("DELETE FROM angelone_symbols")

            nse_count = 0
            bse_count = 0

            for symbol in symbols_data:
                try:
                    # Only load NSE equity and indices for now
                    exch_seg = symbol.get('exch_seg', '')

                    if exch_seg in ['NSE', 'BSE']:
                        instrumenttype = symbol.get('instrumenttype', '')

                        # Focus on equity and indices
                        if instrumenttype in ['', 'EQ', 'INDEX']:
                            cur.execute("""
                                INSERT INTO angelone_symbols
                                (token, symbol, name, expiry, strike, lotsize,
                                 instrumenttype, exch_seg, tick_size)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (token, exch_seg) DO UPDATE SET
                                    symbol = EXCLUDED.symbol,
                                    name = EXCLUDED.name
                            """, (
                                symbol.get('token'),
                                symbol.get('symbol'),
                                symbol.get('name'),
                                symbol.get('expiry', ''),
                                symbol.get('strike', ''),
                                symbol.get('lotsize', 1),
                                instrumenttype or 'EQ',
                                exch_seg,
                                symbol.get('tick_size', 0.05)
                            ))

                            if exch_seg == 'NSE':
                                nse_count += 1
                            else:
                                bse_count += 1

                except Exception as e:
                    continue

        print(f"   ✅ Loaded {nse_count} NSE symbols")
        print(f"   ✅ Loaded {bse_count} BSE symbols")

        # Step 4: Verify key symbols
        print("\n4. Verifying symbol lookups...")
        test_symbols = ['SBIN-EQ', 'RELIANCE-EQ', 'INFY-EQ', 'TCS-EQ', 'NIFTY 50']

        with get_db_cursor() as cur:
            for sym in test_symbols:
                cur.execute("""
                    SELECT token, symbol, name, exch_seg
                    FROM angelone_symbols
                    WHERE symbol = %s AND exch_seg = 'NSE'
                    LIMIT 1
                """, (sym,))

                result = cur.fetchone()
                if result:
                    print(f"   ✅ {sym}: Token {result['token']}")
                else:
                    print(f"   ⚠️  {sym}: Not found")

        print("\n" + "=" * 70)
        print("✅ AngelOne Symbol Master Setup Complete!")
        print("=" * 70)

    else:
        print(f"   ❌ Download failed: HTTP {response.status_code}")

except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Step 5: Show statistics
print("\n5. Database Statistics:")
with get_db_cursor() as cur:
    cur.execute("""
        SELECT
            exch_seg,
            instrumenttype,
            COUNT(*) as count
        FROM angelone_symbols
        GROUP BY exch_seg, instrumenttype
        ORDER BY exch_seg, count DESC
    """)

    print("\n   Symbol counts by exchange and type:")
    for row in cur.fetchall():
        print(f"      {row['exch_seg']:5} {row['instrumenttype']:10} {row['count']:6,} symbols")

print("\n" + "=" * 70)
