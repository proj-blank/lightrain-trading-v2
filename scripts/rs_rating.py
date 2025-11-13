#!/usr/bin/env python3
"""
Relative Strength (RS) Rating System

Calculates RS rating (1-99 scale like IBD) by comparing a stock's performance
against the entire universe over multiple timeframes.

Higher RS = Stock outperforming the market
RS > 80 = Top 20% performers (strongest stocks)
RS > 70 = Top 30% performers
RS < 30 = Bottom 30% performers (weak stocks)
"""

import yfinance as yf
import pandas as pd
import numpy as np
from scipy import stats
import os
import json
from datetime import datetime, timedelta


class RelativeStrengthAnalyzer:
    def __init__(self, universe=None, cache_file='data/rs_cache.json'):
        """
        Initialize RS Analyzer

        Args:
            universe: List of tickers to compare against
            cache_file: File to cache universe returns (speeds up calculations)
        """
        self.universe = universe or self._load_default_universe()
        self.cache_file = cache_file
        self.rs_cache = self._load_cache()

    def _load_default_universe(self):
        """Load default universe from nifty_microcap150_screened.csv"""
        try:
            universe_file = 'data/nifty_microcap150_screened.csv'
            if os.path.exists(universe_file):
                df = pd.read_csv(universe_file)
                return df['Ticker'].tolist()
            else:
                # Fallback to a smaller universe
                return [
                    'SBIN.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'INFY.NS', 'TCS.NS',
                    'RELIANCE.NS', 'HINDUNILVR.NS', 'ITC.NS', 'KOTAKBANK.NS', 'LT.NS'
                ]
        except Exception as e:
            print(f"⚠️ Error loading universe: {e}")
            return []

    def _load_cache(self):
        """Load cached universe returns"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cache = json.load(f)
                # Check if cache is less than 24 hours old
                cache_date = datetime.fromisoformat(cache.get('timestamp', '2000-01-01'))
                if datetime.now() - cache_date < timedelta(hours=24):
                    return cache
            return {'timestamp': datetime.now().isoformat(), 'data': {}}
        except:
            return {'timestamp': datetime.now().isoformat(), 'data': {}}

    def _save_cache(self):
        """Save universe returns to cache"""
        try:
            self.rs_cache['timestamp'] = datetime.now().isoformat()
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(self.rs_cache, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving cache: {e}")

    def calculate_rs_rating(self, ticker, period='1y', use_cache=True):
        """
        Calculate RS rating (1-99 scale like IBD)

        Args:
            ticker: Stock ticker (e.g., 'SBIN.NS')
            period: Lookback period ('1y' for 1 year)
            use_cache: Whether to use cached universe returns

        Returns:
            int: RS rating (1-99), or 0 if error
        """
        try:
            # Get stock performance
            stock = yf.download(ticker, period=period, progress=False)
            if stock.empty or len(stock) < 60:
                return 0

            # Calculate returns for different periods (weighted)
            returns = {
                '3m': self._calculate_return(stock, 63),    # 3 months
                '6m': self._calculate_return(stock, 126),   # 6 months
                '9m': self._calculate_return(stock, 189),   # 9 months
                '12m': self._calculate_return(stock, 252)   # 12 months
            }

            # Weight recent performance more heavily (IBD methodology)
            weighted_return = (
                returns['3m'] * 0.40 +   # 40% weight on last 3 months
                returns['6m'] * 0.30 +   # 30% weight on 3-6 months
                returns['9m'] * 0.20 +   # 20% weight on 6-9 months
                returns['12m'] * 0.10    # 10% weight on 9-12 months
            )

            # Compare against universe
            universe_returns = self._get_universe_returns(period, use_cache)

            if not universe_returns or len(universe_returns) < 10:
                # Not enough data for comparison
                return 50  # Neutral rating

            # Calculate percentile rank (1-99)
            rs_rating = stats.percentileofscore(universe_returns, weighted_return)

            return round(rs_rating)

        except Exception as e:
            print(f"⚠️ RS Rating error for {ticker}: {e}")
            return 0

    def _calculate_return(self, df, days):
        """Calculate return over specified days"""
        try:
            if len(df) < days:
                # If not enough data, use what's available
                days = len(df) - 1

            if days <= 0:
                return 0

            start_price = float(df['Close'].iloc[-days])
            end_price = float(df['Close'].iloc[-1])

            return ((end_price / start_price) - 1) * 100
        except:
            return 0

    def _get_universe_returns(self, period, use_cache=True):
        """Get returns for entire universe"""
        cache_key = f"universe_{period}"

        # Check cache
        if use_cache and cache_key in self.rs_cache.get('data', {}):
            return self.rs_cache['data'][cache_key]

        print(f"📊 Calculating universe returns for {len(self.universe)} stocks...")

        returns = []
        for i, ticker in enumerate(self.universe):
            if i % 20 == 0:
                print(f"  Progress: {i}/{len(self.universe)}")

            try:
                stock = yf.download(ticker, period=period, progress=False)
                if not stock.empty and len(stock) >= 60:
                    # Calculate same weighted return
                    r = {
                        '3m': self._calculate_return(stock, 63),
                        '6m': self._calculate_return(stock, 126),
                        '9m': self._calculate_return(stock, 189),
                        '12m': self._calculate_return(stock, 252)
                    }

                    weighted = (
                        r['3m'] * 0.40 +
                        r['6m'] * 0.30 +
                        r['9m'] * 0.20 +
                        r['12m'] * 0.10
                    )

                    returns.append(weighted)
            except Exception as e:
                # Skip stocks with errors
                continue

        print(f"✅ Calculated returns for {len(returns)} stocks")

        # Save to cache
        if 'data' not in self.rs_cache:
            self.rs_cache['data'] = {}
        self.rs_cache['data'][cache_key] = returns
        self._save_cache()

        return returns

    def get_rs_category(self, rs_rating):
        """Categorize RS rating"""
        if rs_rating >= 90:
            return 'EXCELLENT', '🟢'
        elif rs_rating >= 80:
            return 'STRONG', '🟢'
        elif rs_rating >= 70:
            return 'GOOD', '🟡'
        elif rs_rating >= 50:
            return 'AVERAGE', '🟡'
        elif rs_rating >= 30:
            return 'WEAK', '🔴'
        else:
            return 'VERY WEAK', '🔴'

    def analyze_stock(self, ticker, period='1y'):
        """
        Full RS analysis for a stock

        Returns:
            dict with RS rating, category, and details
        """
        rs_rating = self.calculate_rs_rating(ticker, period)
        category, emoji = self.get_rs_category(rs_rating)

        # Get individual period returns for context
        try:
            stock = yf.download(ticker, period=period, progress=False)
            if not stock.empty:
                returns = {
                    '3m': self._calculate_return(stock, 63),
                    '6m': self._calculate_return(stock, 126),
                    '12m': self._calculate_return(stock, 252)
                }
            else:
                returns = {'3m': 0, '6m': 0, '12m': 0}
        except:
            returns = {'3m': 0, '6m': 0, '12m': 0}

        return {
            'ticker': ticker,
            'rs_rating': rs_rating,
            'category': category,
            'emoji': emoji,
            'returns': returns,
            'recommendation': 'BUY' if rs_rating >= 70 else 'HOLD' if rs_rating >= 50 else 'AVOID'
        }


def test_rs_rating():
    """Test RS Rating on a few stocks"""
    print("="*70)
    print("RS RATING SYSTEM TEST")
    print("="*70)

    analyzer = RelativeStrengthAnalyzer()

    test_stocks = ['SBIN.NS', 'HDFCBANK.NS', 'INFY.NS', 'RELIANCE.NS']

    for ticker in test_stocks:
        print(f"\nAnalyzing {ticker}...")
        result = analyzer.analyze_stock(ticker)

        print(f"  RS Rating: {result['rs_rating']}/99")
        print(f"  Category: {result['emoji']} {result['category']}")
        print(f"  Recommendation: {result['recommendation']}")
        print(f"  Returns: 3m={result['returns']['3m']:+.1f}% | 6m={result['returns']['6m']:+.1f}% | 12m={result['returns']['12m']:+.1f}%")


if __name__ == "__main__":
    test_rs_rating()
