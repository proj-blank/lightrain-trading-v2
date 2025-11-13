# scripts/intraday_data_loader.py
"""
Intraday data loader for real-time trading.
Fetches 1-minute and 5-minute interval data for quick decision making.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def load_intraday_data(tickers=None, interval='1m', period='1d'):
    """
    Load intraday data for trading.

    Args:
        tickers: List of tickers or None to load from watchlist
        interval: Data interval ('1m', '2m', '5m', '15m', '30m', '60m')
        period: Period to fetch ('1d', '5d', '1mo')

    Returns:
        dict: {ticker: DataFrame} with intraday OHLCV data
    """
    if tickers is None:
        # Load from watchlist
        try:
            watchlist = pd.read_csv("data/watchlist.csv")
            tickers = watchlist["Ticker"].tolist()
        except:
            print("⚠️ Could not load watchlist.csv")
            return {}

    stock_data = {}

    for ticker in tickers:
        try:
            df = yf.download(ticker, period=period, interval=interval, progress=False)

            if not df.empty:
                # Ensure we have all required columns
                required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
                if all(col in df.columns for col in required_cols):
                    stock_data[ticker] = df
                else:
                    print(f"⚠️ {ticker}: Missing required columns")
            else:
                print(f"⚠️ {ticker}: No data available")

        except Exception as e:
            print(f"❌ Error loading {ticker}: {e}")
            continue

    return stock_data


def get_live_price(ticker):
    """
    Get the most recent price for a ticker.

    Returns:
        float: Current price or None if unavailable
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='1d', interval='1m')

        if not hist.empty:
            return float(hist['Close'].iloc[-1])
        else:
            return None
    except:
        return None


def is_market_open():
    """
    Check if Indian stock market is currently open.

    NSE/BSE hours: 9:15 AM - 3:30 PM IST (Mon-Fri)

    Returns:
        bool: True if market is open
    """
    from datetime import datetime
    import pytz

    # Get current time in IST
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)

    # Check if weekday (Monday=0, Sunday=6)
    if now.weekday() >= 5:  # Saturday or Sunday
        return False

    # Market hours: 9:15 AM to 3:30 PM
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)

    return market_open <= now <= market_close


def get_market_time_status():
    """
    Get detailed market timing status.

    Returns:
        dict: Status information
    """
    from datetime import datetime
    import pytz

    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)

    market_open_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)

    is_open = is_market_open()

    if now.weekday() >= 5:
        return {
            'is_open': False,
            'status': 'WEEKEND',
            'message': 'Market closed (Weekend)',
            'next_open': None
        }
    elif now < market_open_time:
        return {
            'is_open': False,
            'status': 'PRE_MARKET',
            'message': f'Pre-market (Opens at 9:15 AM)',
            'minutes_to_open': int((market_open_time - now).total_seconds() / 60)
        }
    elif now > market_close_time:
        return {
            'is_open': False,
            'status': 'POST_MARKET',
            'message': 'Market closed (After hours)',
            'next_open': None
        }
    else:
        minutes_to_close = int((market_close_time - now).total_seconds() / 60)
        return {
            'is_open': True,
            'status': 'OPEN',
            'message': f'Market open ({minutes_to_close} min remaining)',
            'minutes_to_close': minutes_to_close
        }


if __name__ == "__main__":
    # Test the module
    print("Testing intraday data loader...")

    status = get_market_time_status()
    print(f"\nMarket Status: {status['status']}")
    print(f"Message: {status['message']}")

    if status['is_open']:
        print("\n✅ Market is OPEN - Loading sample intraday data...")
        data = load_intraday_data(tickers=['RELIANCE.NS'], interval='1m', period='1d')

        if 'RELIANCE.NS' in data:
            df = data['RELIANCE.NS']
            print(f"\nLoaded {len(df)} 1-minute candles for RELIANCE.NS")
            print(f"Latest price: ₹{df['Close'].iloc[-1]:.2f}")
    else:
        print("\n⏸️ Market is CLOSED")
