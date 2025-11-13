# scripts/performance_learner.py
"""
Performance-based learning system that adapts trading strategy based on historical results.

Features:
1. Stock-level performance tracking (win rate, avg P&L, consistency)
2. Indicator performance analysis (which indicators work best)
3. Adaptive position sizing based on past performance
4. Stock filtering based on historical win rates
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

TRADES_FILE = "data/trades.csv"


def load_trade_history(days=None):
    """
    Load trade history from trades.csv.

    Args:
        days: If specified, only load trades from last N days

    Returns:
        pd.DataFrame: Trade history
    """
    if not os.path.exists(TRADES_FILE):
        return pd.DataFrame()

    try:
        trades = pd.read_csv(TRADES_FILE)

        if trades.empty:
            return pd.DataFrame()

        # Convert date column to datetime if it exists
        if 'Date' in trades.columns:
            trades['Date'] = pd.to_datetime(trades['Date'])

            # Filter by days if specified
            if days is not None:
                cutoff_date = datetime.now() - timedelta(days=days)
                trades = trades[trades['Date'] >= cutoff_date]

        return trades
    except Exception as e:
        print(f"Error loading trade history: {e}")
        return pd.DataFrame()


def calculate_stock_performance(ticker, lookback_days=90):
    """
    Calculate performance metrics for a specific stock.

    Returns:
        dict: Performance metrics including win_rate, avg_pnl, trade_count
    """
    trades = load_trade_history(days=lookback_days)

    if trades.empty:
        return {
            'ticker': ticker,
            'trade_count': 0,
            'win_count': 0,
            'loss_count': 0,
            'win_rate': 0.5,  # Neutral
            'avg_pnl': 0,
            'total_pnl': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'profit_factor': 1.0,
            'consistency_score': 50,
            'performance_score': 50
        }

    # Filter for this ticker's SELL trades (where we have P&L)
    stock_trades = trades[
        (trades['Ticker'] == ticker) &
        (trades['Signal'] == 'SELL') &
        (trades['PnL'].notna())
    ].copy()

    if stock_trades.empty or len(stock_trades) < 2:
        return {
            'ticker': ticker,
            'trade_count': len(stock_trades),
            'win_count': 0,
            'loss_count': 0,
            'win_rate': 0.5,
            'avg_pnl': 0,
            'total_pnl': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'profit_factor': 1.0,
            'consistency_score': 50,
            'performance_score': 50
        }

    # Convert P&L to numeric
    stock_trades['PnL'] = pd.to_numeric(stock_trades['PnL'], errors='coerce')
    stock_trades = stock_trades[stock_trades['PnL'].notna()]

    # Calculate metrics
    win_trades = stock_trades[stock_trades['PnL'] > 0]
    loss_trades = stock_trades[stock_trades['PnL'] < 0]

    trade_count = len(stock_trades)
    win_count = len(win_trades)
    loss_count = len(loss_trades)
    win_rate = win_count / trade_count if trade_count > 0 else 0.5

    total_pnl = stock_trades['PnL'].sum()
    avg_pnl = stock_trades['PnL'].mean()

    avg_win = win_trades['PnL'].mean() if len(win_trades) > 0 else 0
    avg_loss = abs(loss_trades['PnL'].mean()) if len(loss_trades) > 0 else 1

    profit_factor = (win_trades['PnL'].sum() / abs(loss_trades['PnL'].sum())) if len(loss_trades) > 0 and loss_trades['PnL'].sum() != 0 else 1.0

    # Consistency score: Lower volatility in P&L = higher score
    pnl_std = stock_trades['PnL'].std() if len(stock_trades) > 1 else 0
    pnl_mean_abs = abs(stock_trades['PnL'].mean())
    coefficient_of_variation = (pnl_std / pnl_mean_abs) if pnl_mean_abs > 0 else 1.0
    consistency_score = max(0, min(100, 100 - (coefficient_of_variation * 20)))

    # Overall performance score (0-100)
    # Factors: win_rate (40%), profit_factor (30%), consistency (30%)
    performance_score = (
        (win_rate * 40) +
        (min(profit_factor / 2.0, 1.0) * 30) +  # Normalize profit_factor to 0-1
        (consistency_score * 0.30)
    )

    return {
        'ticker': ticker,
        'trade_count': trade_count,
        'win_count': win_count,
        'loss_count': loss_count,
        'win_rate': round(win_rate, 3),
        'avg_pnl': round(avg_pnl, 2),
        'total_pnl': round(total_pnl, 2),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'profit_factor': round(profit_factor, 2),
        'consistency_score': round(consistency_score, 2),
        'performance_score': round(performance_score, 2)
    }


def should_trade_stock(ticker, min_trades=3, min_win_rate=0.35, min_performance_score=30, lookback_days=90):
    """
    Determine if we should trade this stock based on historical performance.

    Args:
        ticker: Stock ticker
        min_trades: Minimum number of trades needed for filtering
        min_win_rate: Minimum win rate to continue trading (default 35%)
        min_performance_score: Minimum overall performance score
        lookback_days: Days of history to consider

    Returns:
        tuple: (should_trade: bool, reason: str, metrics: dict)
    """
    metrics = calculate_stock_performance(ticker, lookback_days)

    # Not enough data - allow trading (give stock a chance)
    if metrics['trade_count'] < min_trades:
        return True, f"Insufficient history ({metrics['trade_count']} trades)", metrics

    # Check win rate
    if metrics['win_rate'] < min_win_rate:
        return False, f"Low win rate: {metrics['win_rate']*100:.1f}% < {min_win_rate*100:.1f}%", metrics

    # Check performance score
    if metrics['performance_score'] < min_performance_score:
        return False, f"Low performance score: {metrics['performance_score']:.1f} < {min_performance_score}", metrics

    # Check if consistently losing money
    if metrics['total_pnl'] < -5000 and metrics['avg_pnl'] < -500:
        return False, f"Consistent losses: Total P&L ₹{metrics['total_pnl']:.0f}", metrics

    return True, "Performance acceptable", metrics


def calculate_adaptive_position_multiplier(ticker, lookback_days=90):
    """
    Calculate position size multiplier based on historical performance.

    Returns:
        float: Multiplier (0.5 to 1.5)
        - 1.5x for excellent performers (>60% win rate, good profit factor)
        - 1.0x for average performers
        - 0.5x for poor performers (but not filtered out)
    """
    metrics = calculate_stock_performance(ticker, lookback_days)

    # Not enough data - use default
    if metrics['trade_count'] < 3:
        return 1.0

    performance_score = metrics['performance_score']

    # Map performance score to multiplier
    if performance_score >= 70:
        return 1.5  # Excellent - increase position
    elif performance_score >= 55:
        return 1.2  # Good - slight increase
    elif performance_score >= 45:
        return 1.0  # Average - no change
    elif performance_score >= 35:
        return 0.8  # Below average - reduce
    else:
        return 0.5  # Poor - reduce significantly


def analyze_indicator_performance(lookback_days=90):
    """
    Analyze which indicators have been most predictive.

    This is a placeholder for future implementation where we:
    1. Track which indicator combinations led to successful trades
    2. Adjust indicator weights dynamically

    Returns:
        dict: Recommended indicator weights
    """
    # TODO: Implement indicator performance tracking
    # For now, return default weights
    return {
        'rsi': 0.15,
        'macd': 0.20,
        'bollinger': 0.15,
        'volume': 0.15,
        'trend': 0.15,
        'volatility': 0.20
    }


def get_performance_summary(lookback_days=90):
    """
    Get overall performance summary for all stocks.

    Returns:
        pd.DataFrame: Performance metrics for all traded stocks
    """
    trades = load_trade_history(days=lookback_days)

    if trades.empty:
        return pd.DataFrame()

    # Get unique tickers
    tickers = trades['Ticker'].unique()

    # Calculate performance for each
    results = []
    for ticker in tickers:
        metrics = calculate_stock_performance(ticker, lookback_days)
        if metrics['trade_count'] > 0:
            results.append(metrics)

    if not results:
        return pd.DataFrame()

    # Convert to DataFrame and sort by performance score
    df = pd.DataFrame(results)
    df = df.sort_values('performance_score', ascending=False)

    return df


def print_performance_report(lookback_days=90):
    """
    Print a detailed performance report.
    """
    summary = get_performance_summary(lookback_days)

    if summary.empty:
        print(f"\n📊 No trade history found (last {lookback_days} days)")
        return

    print(f"\n{'='*80}")
    print(f"📊 STOCK PERFORMANCE REPORT (Last {lookback_days} days)")
    print(f"{'='*80}\n")

    # Overall stats
    total_trades = summary['trade_count'].sum()
    total_wins = summary['win_count'].sum()
    overall_win_rate = (total_wins / total_trades) if total_trades > 0 else 0
    total_pnl = summary['total_pnl'].sum()

    print(f"Overall Statistics:")
    print(f"  Total Trades: {total_trades}")
    print(f"  Overall Win Rate: {overall_win_rate*100:.1f}%")
    print(f"  Total P&L: ₹{total_pnl:,.2f}")
    print(f"  Stocks Traded: {len(summary)}\n")

    # Top performers
    print(f"🏆 Top 5 Performers:")
    top_5 = summary.head(5)
    for idx, row in top_5.iterrows():
        print(f"  {row['ticker']:15} | Win Rate: {row['win_rate']*100:5.1f}% | "
              f"P&L: ₹{row['total_pnl']:8,.0f} | Trades: {row['trade_count']:2} | "
              f"Score: {row['performance_score']:5.1f}")

    # Bottom performers
    print(f"\n⚠️  Bottom 5 Performers:")
    bottom_5 = summary.tail(5).sort_values('performance_score')
    for idx, row in bottom_5.iterrows():
        print(f"  {row['ticker']:15} | Win Rate: {row['win_rate']*100:5.1f}% | "
              f"P&L: ₹{row['total_pnl']:8,.0f} | Trades: {row['trade_count']:2} | "
              f"Score: {row['performance_score']:5.1f}")

    # Recommendations
    print(f"\n💡 Recommendations:")
    filtered_stocks = summary[
        (summary['trade_count'] >= 3) &
        ((summary['win_rate'] < 0.35) | (summary['performance_score'] < 30))
    ]

    if len(filtered_stocks) > 0:
        print(f"  Consider pausing trading for these {len(filtered_stocks)} stocks:")
        for idx, row in filtered_stocks.iterrows():
            print(f"    • {row['ticker']} (Win Rate: {row['win_rate']*100:.1f}%, Score: {row['performance_score']:.1f})")
    else:
        print(f"  ✅ All stocks meeting minimum performance criteria")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    # Test the module
    print_performance_report(lookback_days=90)
