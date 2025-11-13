"""
Data loader using AngelOne API instead of Yahoo Finance
Provides historical and real-time market data for LightRain
"""
import pandas as pd
from typing import Dict
import sys
sys.path.insert(0, '/home/ubuntu/trading')
from scripts.angelone_api import get_angelone_api

def load_data_angelone(tickers: list, period: str = '1y', interval: str = 'ONE_DAY') -> Dict[str, pd.DataFrame]:
    """
    Load historical data for multiple tickers using AngelOne API

    Args:
        tickers: List of tickers (e.g., ['SBIN.NS', 'RELIANCE.NS'])
        period: Time period ('1mo', '3mo', '6mo', '1y')
        interval: Candle interval (ONE_DAY, ONE_HOUR, FIFTEEN_MINUTE, etc.)

    Returns:
        Dict of {ticker: DataFrame with OHLCV data}
    """
    api = get_angelone_api()
    stock_data = {}

    # Convert period to days
    period_days = {
        '1mo': 30,
        '3mo': 90,
        '6mo': 180,
        '1y': 365,
        '2y': 730
    }
    days = period_days.get(period, 365)

    from datetime import datetime, timedelta
    to_date = datetime.now().strftime('%Y-%m-%d %H:%M')
    from_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M')

    print(f"📥 Loading data from AngelOne ({period}, {interval})...")

    for ticker in tickers:
        try:
            df = api.get_historical_data(ticker, interval, from_date, to_date)

            if not df.empty and len(df) >= 10:  # Minimum data requirement
                stock_data[ticker] = df
                print(f"  ✅ {ticker}: {len(df)} candles")
            else:
                print(f"  ⚠️ {ticker}: Insufficient data")

        except Exception as e:
            print(f"  ❌ {ticker}: {e}")
            continue

    print(f"✅ Loaded {len(stock_data)}/{len(tickers)} stocks from AngelOne\n")
    return stock_data

def get_current_prices_angelone(tickers: list) -> Dict[str, float]:
    """
    Get current prices (LTP) for multiple tickers

    Args:
        tickers: List of tickers

    Returns:
        Dict of {ticker: current_price}
    """
    api = get_angelone_api()
    prices = {}

    for ticker in tickers:
        try:
            ltp = api.get_ltp(ticker)
            if ltp > 0:
                prices[ticker] = ltp
        except:
            continue

    return prices
