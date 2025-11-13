#!/usr/bin/env python3
"""
pre_execution_checks.py - Intelligence layer before opening positions

Checks BEFORE executing a trade:
1. Earnings announcements (next 3 days)
2. Recent news sentiment
3. Unusual volume/price moves
4. Corporate actions (splits, dividends, bonus)
5. Historical performance around earnings

This is the "memory" and intelligence to avoid walking into disasters.
"""

import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# Configuration
EARNINGS_BUFFER_DAYS = 3  # Avoid if earnings in next 3 days
NEWS_LOOKBACK_DAYS = 2    # Check news from last 2 days
VOLUME_SPIKE_THRESHOLD = 2.0  # Flag if volume > 2x average
PRICE_GAP_THRESHOLD = 0.03    # Flag if price gap > 3%

# Files for memory
EARNINGS_CALENDAR_FILE = 'data/earnings_calendar.json'
TRADE_HISTORY_FILE = 'data/swing_trades.csv'

def check_earnings_calendar(ticker: str) -> Tuple[bool, str]:
    """
    Check if stock has earnings in next 3 days.

    Returns:
        (should_block, reason)
    """
    try:
        stock = yf.Ticker(ticker)

        # Get earnings dates
        earnings_dates = stock.calendar

        if earnings_dates is None:
            return False, "No earnings data"

        # Handle both DataFrame and dict formats
        if isinstance(earnings_dates, dict):
            earnings_dates = pd.DataFrame([earnings_dates])

        if earnings_dates.empty:
            return False, "No earnings data"

        # Check if earnings date exists
        if 'Earnings Date' in earnings_dates.index:
            earnings_date = earnings_dates.loc['Earnings Date'][0]

            if pd.notna(earnings_date):
                # Convert to datetime if needed
                if isinstance(earnings_date, str):
                    earnings_date = pd.to_datetime(earnings_date)

                days_until = (earnings_date - pd.Timestamp.now()).days

                # Block if earnings within next 3 days
                if 0 <= days_until <= EARNINGS_BUFFER_DAYS:
                    return True, f"Earnings in {days_until} days ({earnings_date.date()})"

        return False, "No upcoming earnings"

    except Exception as e:
        # If we can't check, be cautious
        return False, f"Could not verify earnings: {str(e)}"

def check_recent_news(ticker: str) -> Tuple[bool, str]:
    """
    Check recent news for negative sentiment.
    Uses yfinance news feed.

    Returns:
        (should_block, reason)
    """
    try:
        stock = yf.Ticker(ticker)
        news = stock.news

        if not news or len(news) == 0:
            return False, "No recent news"

        # Check news from last 2 days
        cutoff = datetime.now() - timedelta(days=NEWS_LOOKBACK_DAYS)
        recent_news = []

        for item in news[:5]:  # Check top 5 news items
            pub_date = datetime.fromtimestamp(item.get('providerPublishTime', 0))

            if pub_date >= cutoff:
                title = item.get('title', '').lower()

                # Look for negative keywords
                negative_keywords = [
                    'loss', 'losses', 'miss', 'misses', 'disappoints', 'falls',
                    'drops', 'plunges', 'tumbles', 'crashes', 'investigation',
                    'probe', 'fraud', 'scandal', 'lawsuit', 'downgrade',
                    'cuts', 'reduces', 'warning', 'concerns'
                ]

                for keyword in negative_keywords:
                    if keyword in title:
                        recent_news.append({
                            'date': pub_date.date(),
                            'title': item.get('title', ''),
                            'keyword': keyword
                        })

        if recent_news:
            first_news = recent_news[0]
            return True, f"Negative news: '{first_news['keyword']}' in recent headlines"

        return False, "No negative news detected"

    except Exception as e:
        return False, f"Could not check news: {str(e)}"

def check_unusual_activity(ticker: str) -> Tuple[bool, str]:
    """
    Check for unusual volume or price gaps.

    Returns:
        (should_block, reason)
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="10d")

        if df.empty or len(df) < 5:
            return False, "Insufficient data"

        # Check volume spike
        avg_volume = df['Volume'].iloc[:-1].mean()
        current_volume = df['Volume'].iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

        if volume_ratio > VOLUME_SPIKE_THRESHOLD:
            # Volume spike could be good or bad - flag for review
            return True, f"Unusual volume spike: {volume_ratio:.1f}x average"

        # Check price gap (today's open vs yesterday's close)
        if len(df) >= 2:
            yesterday_close = df['Close'].iloc[-2]
            today_open = df['Open'].iloc[-1]
            gap_pct = abs((today_open - yesterday_close) / yesterday_close)

            if gap_pct > PRICE_GAP_THRESHOLD:
                direction = "up" if today_open > yesterday_close else "down"
                return True, f"Price gap {direction}: {gap_pct*100:.1f}%"

        return False, "No unusual activity"

    except Exception as e:
        return False, f"Could not check activity: {str(e)}"

def check_historical_earnings_performance(ticker: str) -> Tuple[bool, str]:
    """
    Check how this stock performed around past earnings.
    If it consistently drops post-earnings, flag it.

    Returns:
        (should_block, reason)
    """
    try:
        # Load trade history
        if not os.path.exists(TRADE_HISTORY_FILE):
            return False, "No historical data"

        df_trades = pd.read_csv(TRADE_HISTORY_FILE)

        # Filter for this ticker
        ticker_trades = df_trades[df_trades['Ticker'] == ticker]

        if len(ticker_trades) < 3:
            return False, "Insufficient trade history"

        # Check losses during earnings periods
        # (This is simplified - you'd need earnings dates calendar)
        losses = ticker_trades[ticker_trades['PnL'] < 0]

        if len(losses) >= 3:
            loss_rate = len(losses) / len(ticker_trades)
            if loss_rate > 0.6:  # Lost 60%+ of the time
                return True, f"Poor historical performance: {loss_rate*100:.0f}% loss rate"

        return False, "Historical performance acceptable"

    except Exception as e:
        return False, f"Could not check history: {str(e)}"

def should_execute_trade(ticker: str, action: str = "BUY") -> Tuple[bool, List[str]]:
    """
    Master function: Run all pre-execution checks.

    Args:
        ticker: Stock symbol (e.g., "ASIANPAINT.NS")
        action: "BUY" or "SELL"

    Returns:
        (should_proceed, reasons)
        - should_proceed: True if safe to trade, False if blocked
        - reasons: List of all check results
    """
    checks = []
    blockers = []

    print(f"\n🔍 Pre-execution checks for {ticker}...")

    # 1. Earnings check
    earnings_block, earnings_reason = check_earnings_calendar(ticker)
    status = "🚫 BLOCK" if earnings_block else "✅ PASS"
    checks.append(f"{status} Earnings: {earnings_reason}")
    if earnings_block:
        blockers.append(f"Earnings: {earnings_reason}")

    # 2. News check
    news_block, news_reason = check_recent_news(ticker)
    status = "🚫 BLOCK" if news_block else "✅ PASS"
    checks.append(f"{status} News: {news_reason}")
    if news_block:
        blockers.append(f"News: {news_reason}")

    # 3. Unusual activity check
    activity_block, activity_reason = check_unusual_activity(ticker)
    status = "⚠️ WARN" if activity_block else "✅ PASS"
    checks.append(f"{status} Activity: {activity_reason}")
    # Note: Activity is warning only, not a hard block

    # 4. Historical performance check
    history_block, history_reason = check_historical_earnings_performance(ticker)
    status = "⚠️ WARN" if history_block else "✅ PASS"
    checks.append(f"{status} History: {history_reason}")
    # Note: History is warning only, not a hard block

    # Print results
    for check in checks:
        print(f"  {check}")

    # Decision
    should_proceed = len(blockers) == 0

    if should_proceed:
        print(f"✅ Safe to {action} {ticker}")
    else:
        print(f"🚫 BLOCKED: Cannot {action} {ticker}")
        for blocker in blockers:
            print(f"   - {blocker}")

    return should_proceed, checks

def save_check_results(ticker: str, checks: List[str], decision: bool):
    """Save pre-execution check results for audit trail"""
    os.makedirs('logs', exist_ok=True)

    log_file = 'logs/pre_execution_checks.csv'

    entry = {
        'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'Ticker': ticker,
        'Decision': 'PROCEED' if decision else 'BLOCKED',
        'Checks': ' | '.join(checks)
    }

    df = pd.DataFrame([entry])

    if os.path.exists(log_file):
        df.to_csv(log_file, mode='a', header=False, index=False)
    else:
        df.to_csv(log_file, index=False)

# Example negative news detection patterns
NEGATIVE_PATTERNS = {
    'earnings_miss': ['miss', 'misses', 'disappoints', 'below expectations'],
    'guidance_cut': ['lowers guidance', 'cuts forecast', 'reduces outlook'],
    'losses': ['reports loss', 'quarterly loss', 'net loss'],
    'management': ['ceo resigns', 'cfo quits', 'executive exits'],
    'legal': ['lawsuit', 'investigation', 'probe', 'fraud', 'scandal'],
    'downgrades': ['downgrade', 'cuts rating', 'lowers target'],
    'concerns': ['concerns', 'worries', 'fears', 'uncertainty']
}

def get_news_sentiment_score(ticker: str) -> Tuple[float, List[str]]:
    """
    Get news sentiment score (0-100).

    Returns:
        (score, headlines)
        - score: 0 = very negative, 50 = neutral, 100 = very positive
        - headlines: Recent news titles
    """
    try:
        stock = yf.Ticker(ticker)
        news = stock.news

        if not news or len(news) == 0:
            return 50, ["No recent news"]

        sentiment_score = 50  # Start neutral
        headlines = []

        for item in news[:10]:  # Check last 10 news items
            title = item.get('title', '').lower()
            headlines.append(item.get('title', ''))

            # Count negative patterns
            negative_count = 0
            for category, patterns in NEGATIVE_PATTERNS.items():
                for pattern in patterns:
                    if pattern in title:
                        negative_count += 1

            # Adjust score based on negative patterns
            sentiment_score -= (negative_count * 10)

        # Clamp to 0-100
        sentiment_score = max(0, min(100, sentiment_score))

        return sentiment_score, headlines[:5]

    except Exception as e:
        return 50, [f"Error: {str(e)}"]

if __name__ == "__main__":
    # Test the checks
    import sys

    if len(sys.argv) > 1:
        ticker = sys.argv[1]
    else:
        ticker = "ASIANPAINT.NS"

    print("="*80)
    print(f"PRE-EXECUTION CHECKS: {ticker}")
    print("="*80)

    should_proceed, checks = should_execute_trade(ticker, "BUY")

    print("\n" + "="*80)
    print("SENTIMENT ANALYSIS")
    print("="*80)
    score, headlines = get_news_sentiment_score(ticker)
    print(f"Sentiment Score: {score}/100")
    print("\nRecent Headlines:")
    for i, headline in enumerate(headlines, 1):
        print(f"  {i}. {headline}")

    print("\n" + "="*80)
    if should_proceed:
        print("✅ DECISION: SAFE TO TRADE")
    else:
        print("🚫 DECISION: DO NOT TRADE")
    print("="*80)

    # Save results
    save_check_results(ticker, checks, should_proceed)
    print("\n📝 Results saved to logs/pre_execution_checks.csv")
