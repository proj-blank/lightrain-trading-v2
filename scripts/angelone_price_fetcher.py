#!/usr/bin/env python3
"""
AngelOne Live Price Fetcher
Fetches real-time prices from AngelOne API for position entry/exit
"""
import os
import pyotp
from datetime import datetime
import pytz
from dotenv import load_dotenv
from SmartApi import SmartConnect

load_dotenv()

# AngelOne credentials
ANGEL_API_KEY = os.getenv('ANGELONE_API_KEY')
ANGEL_CLIENT_CODE = os.getenv('ANGELONE_CLIENT_ID')
ANGEL_PASSWORD = os.getenv('ANGELONE_PASSWORD')
ANGEL_TOTP_SECRET = os.getenv('ANGELONE_TOTP_SECRET')

# Cache session to avoid multiple logins
_angel_session = None
_angel_session_time = None

def get_angel_session(force_refresh=False):
    """Get or create AngelOne session with caching"""
    global _angel_session, _angel_session_time

    # Check if we need to refresh (session >23 hours old or forced)
    if _angel_session and _angel_session_time:
        age_hours = (datetime.now() - _angel_session_time).total_seconds() / 3600
        if age_hours < 23 and not force_refresh:
            return _angel_session

    try:
        smart_api = SmartConnect(api_key=ANGEL_API_KEY)
        totp = pyotp.TOTP(ANGEL_TOTP_SECRET).now()
        data = smart_api.generateSession(ANGEL_CLIENT_CODE, ANGEL_PASSWORD, totp)

        if data['status']:
            _angel_session = smart_api
            _angel_session_time = datetime.now()
            print("✅ AngelOne session created")
            return smart_api
        else:
            print(f"❌ AngelOne session failed: {data}")
            return None
    except Exception as e:
        print(f"❌ AngelOne login error: {e}")
        return None


# NSE symbol to AngelOne token mapping for common stocks
NSE_SYMBOL_TOKENS = {
    # Nifty 50
    'RELIANCE': '2885',
    'TCS': '11536',
    'HDFCBANK': '1333',
    'INFY': '1594',
    'ICICIBANK': '4963',
    'BHARTIARTL': '10604',
    'SBIN': '3045',
    'BAJFINANCE': '317',
    'ASIANPAINT': '236',
    'MARUTI': '10999',
    'TATASTEEL': '3499',
    'SUNPHARMA': '3351',
    'TITAN': '3506',
    'WIPRO': '3787',
    'TECHM': '13538',
    'HCLTECH': '7229',
    'ULTRACEMCO': '11532',
    'AXISBANK': '5900',
    'LT': '11483',
    'KOTAKBANK': '1922',
    'ITC': '1660',
    'HINDUNILVR': '1394',
    'POWERGRID': '14977',
    'NTPC': '11630',
    'ONGC': '2475',
    'ADANIPORTS': '15083',
    'BPCL': '526',
    'BRITANNIA': '547',
    'DIVISLAB': '10940',
    'JSWSTEEL': '11723',
    'LTIM': '17818',
    'M&M': '2031',
    'SBILIFE': '21808',
    'TATACONSUM': '3432',
    'ADANIGREEN': '25317',
    'ADANIPOWER': '25',
    'APOLLOHOSP': '157',
    'APOLLOTYRE': '163',
    'ASHOKLEY': '212',
    'AUROPHARMA': '275',
    'BAJAJFINSV': '16675',
    'BIOCON': '11373',
    'CUMMINSIND': '1901',
    'HINDALCO': '1363',
    'HINDZINC': '364',
    'LAURUSLABS': '19234',
    'MOTHERSON': '4204',
    'MUTHOOTFIN': '23650',
    'NAVINFLUOR': '13755',
    'NMDC': '15332',
    'PERSISTENT': '14413',
    'POLYCAB': '9590',
    'POONAWALLA': '28716',
    'SBICARD': '17971',
    'SCHAEFFLER': '13404',
    'TORNTPHARM': '3518',
    'TVSMOTOR': '8479',
    'VEDL': '3063',
}


def get_angelone_ltp(ticker):
    """
    Get Last Traded Price from AngelOne for a given ticker

    Args:
        ticker: NSE ticker with .NS suffix (e.g., 'RELIANCE.NS')

    Returns:
        float: Last traded price, or None if unavailable
    """
    try:
        # Remove .NS suffix
        symbol = ticker.replace('.NS', '')

        # Get token for symbol
        token = NSE_SYMBOL_TOKENS.get(symbol)
        if not token:
            print(f"⚠️ AngelOne: Token not found for {symbol}, using Yahoo price")
            return None

        # Get session
        session = get_angel_session()
        if not session:
            print(f"⚠️ AngelOne: Session unavailable, using Yahoo price")
            return None

        # Fetch LTP
        ltp_data = session.ltpData('NSE', symbol, token)
        if ltp_data and ltp_data.get('status'):
            ltp = float(ltp_data['data'].get('ltp', 0))
            if ltp > 0:
                return ltp
            else:
                print(f"⚠️ AngelOne: Invalid LTP for {symbol}, using Yahoo price")
                return None
        else:
            print(f"⚠️ AngelOne: ltpData failed for {symbol}, using Yahoo price")
            return None

    except Exception as e:
        print(f"⚠️ AngelOne price fetch error for {ticker}: {e}")
        return None


def get_live_price(ticker, df_close_price):
    """
    Get live price with fallback to Yahoo

    Tries AngelOne first, falls back to df Close price if unavailable

    Args:
        ticker: NSE ticker (e.g., 'RELIANCE.NS')
        df_close_price: Fallback price from yfinance dataframe

    Returns:
        tuple: (price, source) where source is 'angelone' or 'yahoo'
    """
    # Try AngelOne first
    angel_price = get_angelone_ltp(ticker)
    if angel_price is not None:
        return (angel_price, 'angelone')

    # Fallback to Yahoo
    return (float(df_close_price), 'yahoo')


if __name__ == "__main__":
    # Test
    test_ticker = "RELIANCE.NS"
    price, source = get_live_price(test_ticker, 2500.0)
    print(f"Price for {test_ticker}: ₹{price:.2f} (source: {source})")
