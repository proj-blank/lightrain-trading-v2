#!/usr/bin/env python3
"""
Test AngelOne data fetching capabilities
"""
import sys
sys.path.insert(0, '/home/ubuntu/trading')

from scripts.data_loader_angelone import load_data_angelone, get_current_prices_angelone

print("=" * 70)
print("Testing AngelOne Data Fetching")
print("=" * 70)

# Test 1: Load historical data
print("\n1. Testing historical data loading...")
try:
    test_tickers = ['RELIANCE', 'TCS', 'INFY']
    print(f"   Fetching data for: {', '.join(test_tickers)}")

    data = load_data_angelone(test_tickers, period='1mo', interval='ONE_DAY')

    if data:
        print(f"   ✅ Data loaded for {len(data)} tickers")
        for ticker, df in data.items():
            if df is not None and not df.empty:
                print(f"      {ticker}: {len(df)} rows, Latest close: ₹{df['close'].iloc[-1]:.2f}")
            else:
                print(f"      {ticker}: No data")
    else:
        print("   ⚠️  No data returned")

except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Get current prices
print("\n2. Testing current price fetching...")
try:
    test_tickers = ['RELIANCE', 'TCS']
    print(f"   Fetching prices for: {', '.join(test_tickers)}")

    prices = get_current_prices_angelone(test_tickers)

    if prices:
        print(f"   ✅ Prices fetched for {len(prices)} tickers")
        for ticker, price in prices.items():
            print(f"      {ticker}: ₹{price:.2f}")
    else:
        print("   ⚠️  No prices returned")

except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("AngelOne Integration Test Complete")
print("=" * 70)
