"""
position_tracker.py - Track open positions for dynamic watchlist management

Maintains data/positions.json with list of stocks that have open positions.
This ensures stocks with positions are retained in the watchlist during screening.
"""

import json
import os
import pandas as pd
from pathlib import Path


POSITIONS_FILE = 'data/positions.json'


def update_positions_file(portfolio_df):
    """
    Update positions.json based on current portfolio.

    Args:
        portfolio_df: DataFrame from portfolio.csv
    """
    # Get stocks with HOLD status (open positions)
    if portfolio_df.empty:
        open_positions = []
    else:
        hold_positions = portfolio_df[portfolio_df['Status'] == 'HOLD']
        open_positions = [
            {
                'ticker': row['Ticker'],
                'entry_price': float(row['EntryPrice']),
                'shares': int(row['Quantity']),
                'stop_loss': float(row['StopLoss']),
                'take_profit': float(row['TakeProfit'])
            }
            for _, row in hold_positions.iterrows()
        ]

    # Ensure data directory exists
    os.makedirs('data', exist_ok=True)

    # Save to JSON
    with open(POSITIONS_FILE, 'w') as f:
        json.dump(open_positions, f, indent=2)

    return len(open_positions)


def load_positions():
    """Load current open positions."""
    if not os.path.exists(POSITIONS_FILE):
        return []

    try:
        with open(POSITIONS_FILE, 'r') as f:
            return json.load(f)
    except:
        return []


def get_position_tickers():
    """Get list of tickers with open positions."""
    positions = load_positions()
    return [p['ticker'] for p in positions]


def has_position(ticker):
    """Check if ticker has an open position."""
    return ticker in get_position_tickers()
