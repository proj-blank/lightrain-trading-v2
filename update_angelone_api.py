#!/usr/bin/env python3
"""
Update angelone_api.py to use database for symbol lookups and fix API methods
"""
import sys

# The updated _get_symbol_token method
NEW_GET_SYMBOL_TOKEN = '''    def _get_symbol_token(self, ticker: str) -> str:
        """
        Convert ticker to AngelOne symbol token using database lookup

        Args:
            ticker: Stock symbol (e.g., 'SBIN.NS', 'RELIANCE.NS')

        Returns:
            AngelOne exchange token (numeric string)
        """
        # Convert ticker format: SBIN.NS -> SBIN-EQ
        if ticker.endswith('.NS'):
            symbol = ticker.replace('.NS', '-EQ')
        elif ticker.endswith('.BO'):
            symbol = ticker.replace('.BO', '-EQ')
        else:
            symbol = ticker

        # Lookup in database
        try:
            from scripts.db_connection import get_db_cursor

            with get_db_cursor() as cur:
                cur.execute("""
                    SELECT token FROM angelone_symbols
                    WHERE symbol = %s AND exch_seg = 'NSE'
                    LIMIT 1
                """, (symbol,))

                result = cur.fetchone()
                if result:
                    return result['token']
                else:
                    # Fallback: try without -EQ suffix
                    base_symbol = symbol.replace('-EQ', '')
                    cur.execute("""
                        SELECT token FROM angelone_symbols
                        WHERE symbol LIKE %s AND exch_seg = 'NSE'
                        LIMIT 1
                    """, (f"{base_symbol}%",))

                    result = cur.fetchone()
                    if result:
                        return result['token']

            print(f"⚠️  Symbol {ticker} not found in database")
            return None

        except Exception as e:
            print(f"❌ Error looking up symbol {ticker}: {e}")
            return None'''

# The updated get_ltp method with correct API signature
NEW_GET_LTP = '''    def get_ltp(self, ticker: str) -> float:
        """Get Last Traded Price (LTP) for a stock"""
        if not self.smart_api:
            self.login()

        symbol_token = self._get_symbol_token(ticker)
        if not symbol_token:
            return 0.0

        try:
            # Correct API signature for getMarketData
            data = self.smart_api.getMarketData("LTP", "NSE", [symbol_token])

            if data and data.get('status') and data.get('data'):
                fetched = data['data'].get('fetched')
                if fetched and len(fetched) > 0:
                    return float(fetched[0].get('ltp', 0))
            return 0.0

        except Exception as e:
            print(f"❌ Error fetching LTP for {ticker}: {e}")
            return 0.0'''

# The updated get_quote method
NEW_GET_QUOTE = '''    def get_quote(self, ticker: str) -> Dict:
        """Get full quote with OHLC, volume, bid/ask"""
        if not self.smart_api:
            self.login()

        symbol_token = self._get_symbol_token(ticker)
        if not symbol_token:
            return {}

        try:
            # Correct API signature for getMarketData
            data = self.smart_api.getMarketData("FULL", "NSE", [symbol_token])

            if data and data.get('status') and data.get('data'):
                fetched = data['data'].get('fetched')
                if fetched and len(fetched) > 0:
                    return fetched[0]
            return {}

        except Exception as e:
            print(f"❌ Error fetching quote for {ticker}: {e}")
            return {}'''

print("=" * 70)
print("Updating angelone_api.py with database lookups")
print("=" * 70)

# Read the current file
file_path = '/home/ubuntu/trading/scripts/angelone_api.py'
with open(file_path, 'r') as f:
    content = f.read()

# Replace _get_symbol_token method
import re

# Find and replace _get_symbol_token
pattern = r'    def _get_symbol_token\(self, ticker: str\) -> str:.*?(?=\n    def _log_order_to_db|\n# Singleton instance|\nclass )'
content = re.sub(pattern, NEW_GET_SYMBOL_TOKEN + '\n', content, flags=re.DOTALL)

# Find and replace get_ltp
pattern = r'    def get_ltp\(self, ticker: str\) -> float:.*?(?=\n    def get_quote|\n    def )'
content = re.sub(pattern, NEW_GET_LTP + '\n', content, flags=re.DOTALL)

# Find and replace get_quote
pattern = r'    def get_quote\(self, ticker: str\) -> Dict:.*?(?=\n    # ==================== ORDER EXECUTION ====================|\n    def place_order|\n    def )'
content = re.sub(pattern, NEW_GET_QUOTE + '\n', content, flags=re.DOTALL)

# Write back
with open(file_path, 'w') as f:
    f.write(content)

print("✅ Updated angelone_api.py")
print("   - _get_symbol_token: Now queries PostgreSQL database")
print("   - get_ltp: Fixed API signature")
print("   - get_quote: Fixed API signature")
print("=" * 70)
