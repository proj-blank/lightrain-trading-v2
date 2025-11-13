#!/usr/bin/env python3
"""
Test AngelOne API connection after credentials migration
"""
import sys
sys.path.insert(0, '/home/ubuntu/trading')

from scripts.angelone_api import get_angelone_api

print("=" * 70)
print("Testing AngelOne API Connection")
print("=" * 70)

try:
    api = get_angelone_api()
    if api:
        print("✅ AngelOne API connected successfully!")

        # Try to get profile to confirm it's working
        try:
            profile = api.getProfile(api.refreshToken)
            if profile and profile.get('status') and profile.get('data'):
                print(f"✅ Profile fetched successfully")
                print(f"   Name: {profile['data'].get('name', 'N/A')}")
                print(f"   Client ID: {profile['data'].get('clientcode', 'N/A')}")
                print(f"   Email: {profile['data'].get('email', 'N/A')}")
            else:
                print(f"⚠️  Profile response: {profile}")
        except Exception as e:
            print(f"⚠️  Profile fetch error: {e}")
    else:
        print("❌ AngelOne API connection failed (returned None)")

except Exception as e:
    print(f"❌ Error testing AngelOne API: {e}")
    import traceback
    traceback.print_exc()

print("=" * 70)
print("\nNext: Test data fetching...")
print("=" * 70)

# Test data fetching
try:
    from scripts.data_loader_angelone import get_stock_data_angelone

    # Test with a simple ticker
    print("\nTesting data fetch for NIFTY 50...")
    data = get_stock_data_angelone("NIFTY 50", "NSE")
    if data is not None and not data.empty:
        print(f"✅ Data fetched successfully")
        print(f"   Rows: {len(data)}")
        print(f"   Latest close: {data['close'].iloc[-1]}")
    else:
        print("⚠️  No data returned")
except Exception as e:
    print(f"⚠️  Data fetch test error: {e}")

print("=" * 70)
