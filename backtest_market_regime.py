#!/usr/bin/env python3
"""
Backtest Market Regime Filter Impact
Shows how the global market regime filter would have affected trading
over the past 30 days (DAILY) and 60 days (SWING)
"""
import sys
sys.path.insert(0, '/home/ubuntu/trading')

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from scripts.db_connection import get_db_cursor

print("=" * 80)
print("📊 MARKET REGIME BACKTEST")
print("=" * 80)
print(f"Analysis Date: {datetime.now().strftime('%d %b %Y, %H:%M IST')}")
print("=" * 80)

def calculate_regime_for_date(date):
    """Calculate market regime for a specific historical date"""
    # Fetch data as of that date
    try:
        # S&P 500
        spy = yf.Ticker("^GSPC")
        spy_data = spy.history(start=date - timedelta(days=30), end=date)

        if len(spy_data) < 2:
            return None

        spy_current = spy_data['Close'].iloc[-1]
        spy_prev = spy_data['Close'].iloc[-2]
        spy_change_pct = ((spy_current - spy_prev) / spy_prev) * 100
        spy_sma20 = spy_data['Close'].rolling(20).mean().iloc[-1]
        spy_trend = "ABOVE" if spy_current > spy_sma20 else "BELOW"

        # VIX
        vix = yf.Ticker("^VIX")
        vix_data = vix.history(start=date - timedelta(days=5), end=date)
        vix_current = vix_data['Close'].iloc[-1] if not vix_data.empty else 20

        if vix_current < 15:
            vix_level = "LOW"
        elif vix_current < 20:
            vix_level = "NORMAL"
        elif vix_current < 30:
            vix_level = "ELEVATED"
        else:
            vix_level = "HIGH"

        # India VIX
        india_vix = yf.Ticker("^INDIAVIX")
        ivix_data = india_vix.history(start=date - timedelta(days=5), end=date)
        india_vix_current = ivix_data['Close'].iloc[-1] if not ivix_data.empty else 15

        if india_vix_current < 12:
            ivix_level = "LOW"
        elif india_vix_current < 15:
            ivix_level = "NORMAL"
        elif india_vix_current < 20:
            ivix_level = "ELEVATED"
        else:
            ivix_level = "HIGH"

        # Nifty 50
        nifty = yf.Ticker("^NSEI")
        nifty_data = nifty.history(start=date - timedelta(days=60), end=date)

        if len(nifty_data) < 2:
            nifty_trend = "UNKNOWN"
        else:
            nifty_current = nifty_data['Close'].iloc[-1]
            nifty_sma50 = nifty_data['Close'].rolling(50).mean().iloc[-1]
            nifty_trend = "ABOVE" if nifty_current > nifty_sma50 else "BELOW"

        # Calculate score (same logic as global_market_filter.py)
        score = 0

        # S&P 500 (40% weight)
        if spy_change_pct > 1:
            score += 2
        elif spy_change_pct > 0:
            score += 1
        elif spy_change_pct > -1:
            score -= 1
        else:
            score -= 2

        if spy_trend == "ABOVE":
            score += 1
        else:
            score -= 1

        # VIX (30% weight)
        if vix_level == "LOW":
            score += 2
        elif vix_level == "NORMAL":
            score += 1
        elif vix_level == "ELEVATED":
            score -= 1
        else:
            score -= 3

        # India VIX (20% weight)
        if ivix_level == "LOW":
            score += 1
        elif ivix_level == "NORMAL":
            score += 0.5
        elif ivix_level == "ELEVATED":
            score -= 1
        else:
            score -= 2

        # Nifty Trend (10% weight)
        if nifty_trend == "ABOVE":
            score += 1
        else:
            score -= 1

        # Determine regime
        if score >= 4:
            regime = "BULL"
            multiplier = 1.0
            allow_entries = True
        elif score >= 1:
            regime = "NEUTRAL"
            multiplier = 0.75
            allow_entries = True
        elif score >= -2:
            regime = "CAUTION"
            multiplier = 0.5
            allow_entries = True
        else:
            regime = "BEAR"
            multiplier = 0.0
            allow_entries = False

        return {
            'date': date,
            'regime': regime,
            'score': score,
            'multiplier': multiplier,
            'allow_entries': allow_entries,
            'spy_change': spy_change_pct,
            'vix': vix_current,
            'india_vix': india_vix_current
        }

    except Exception as e:
        print(f"⚠️  Error calculating regime for {date.date()}: {e}")
        return None

print("\n📅 Calculating historical regime data...")
print("-" * 80)

# Calculate regime for past 60 days (covers both DAILY and SWING)
end_date = datetime.now()
start_date = end_date - timedelta(days=70)  # Extra days for market holidays

regime_history = []
current_date = start_date

while current_date <= end_date:
    # Only calculate for weekdays
    if current_date.weekday() < 5:  # Monday=0, Friday=4
        regime_data = calculate_regime_for_date(current_date)
        if regime_data:
            regime_history.append(regime_data)
            emoji = {'BULL': '🟢', 'NEUTRAL': '🟡', 'CAUTION': '🟠', 'BEAR': '🔴'}.get(regime_data['regime'], '⚪')
            print(f"{current_date.strftime('%Y-%m-%d')} {emoji} {regime_data['regime']:8} (score: {regime_data['score']:+.1f})")

    current_date += timedelta(days=1)

print(f"\n✅ Calculated regime for {len(regime_history)} trading days")

# Analyze regime distribution
regime_counts = {}
for r in regime_history:
    regime_counts[r['regime']] = regime_counts.get(r['regime'], 0) + 1

print("\n📊 Regime Distribution:")
print("-" * 80)
for regime in ['BULL', 'NEUTRAL', 'CAUTION', 'BEAR']:
    count = regime_counts.get(regime, 0)
    pct = (count / len(regime_history) * 100) if regime_history else 0
    emoji = {'BULL': '🟢', 'NEUTRAL': '🟡', 'CAUTION': '🟠', 'BEAR': '🔴'}.get(regime, '⚪')
    bar = '█' * int(pct / 2)
    print(f"{emoji} {regime:8} {count:3} days ({pct:5.1f}%) {bar}")

# Get actual trades from database
print("\n💼 Analyzing actual trades from database...")
print("-" * 80)

# Last 30 days for DAILY
daily_start = datetime.now() - timedelta(days=30)
# Last 60 days for SWING
swing_start = datetime.now() - timedelta(days=60)

with get_db_cursor() as cur:
    # DAILY trades
    cur.execute("""
        SELECT
            DATE(trade_date) as trade_date,
            COUNT(*) as num_trades,
            SUM(pnl) as total_pnl
        FROM trades
        WHERE strategy = 'DAILY'
        AND trade_date >= %s
        GROUP BY DATE(trade_date)
        ORDER BY trade_date
    """, (daily_start,))

    daily_trades = cur.fetchall()

    # SWING trades
    cur.execute("""
        SELECT
            DATE(trade_date) as trade_date,
            COUNT(*) as num_trades,
            SUM(pnl) as total_pnl
        FROM trades
        WHERE strategy = 'SWING'
        AND trade_date >= %s
        GROUP BY DATE(trade_date)
        ORDER BY trade_date
    """, (swing_start,))

    swing_trades = cur.fetchall()

# Match trades with regime
print("\n🔍 DAILY Strategy Analysis (Last 30 Days):")
print("-" * 80)
print(f"{'Date':<12} {'Regime':^8} {'Multiplier':^11} {'Trades':^7} {'Would Take':^11} {'Actual P&L':>12}")
print("-" * 80)

daily_total_pnl = 0
daily_regime_pnl = 0
daily_trades_taken = 0
daily_trades_filtered = 0

for trade in daily_trades:
    trade_date = trade['trade_date']
    num_trades = trade['num_trades']
    pnl = float(trade['total_pnl']) if trade['total_pnl'] else 0

    # Find regime for this date
    regime_data = next((r for r in regime_history if r['date'].date() == trade_date), None)

    if regime_data:
        emoji = {'BULL': '🟢', 'NEUTRAL': '🟡', 'CAUTION': '🟠', 'BEAR': '🔴'}.get(regime_data['regime'], '⚪')
        multiplier = regime_data['multiplier']
        would_trade = num_trades if regime_data['allow_entries'] else 0
        regime_adjusted_pnl = pnl * multiplier if regime_data['allow_entries'] else 0

        print(f"{trade_date} {emoji} {regime_data['regime']:8} {multiplier:>5.0%}      {num_trades:3}        {would_trade:3}      ₹{pnl:>10,.0f}")

        daily_total_pnl += pnl
        daily_regime_pnl += regime_adjusted_pnl
        daily_trades_taken += num_trades
        if not regime_data['allow_entries']:
            daily_trades_filtered += num_trades

print("-" * 80)
print(f"Total:                                     {daily_trades_taken:3}                     ₹{daily_total_pnl:>10,.0f}")
print(f"\n📊 DAILY Impact:")
print(f"  Trades Filtered (BEAR days): {daily_trades_filtered}")
print(f"  Without Regime Filter: ₹{daily_total_pnl:,.0f}")
print(f"  With Regime Filter:    ₹{daily_regime_pnl:,.0f}")
print(f"  Difference:            ₹{daily_regime_pnl - daily_total_pnl:+,.0f}")

# SWING Analysis
print("\n" + "=" * 80)
print("🔍 SWING Strategy Analysis (Last 60 Days):")
print("-" * 80)
print(f"{'Date':<12} {'Regime':^8} {'Multiplier':^11} {'Trades':^7} {'Would Take':^11} {'Actual P&L':>12}")
print("-" * 80)

swing_total_pnl = 0
swing_regime_pnl = 0
swing_trades_taken = 0
swing_trades_filtered = 0

for trade in swing_trades:
    trade_date = trade['trade_date']
    num_trades = trade['num_trades']
    pnl = float(trade['total_pnl']) if trade['total_pnl'] else 0

    # Find regime for this date
    regime_data = next((r for r in regime_history if r['date'].date() == trade_date), None)

    if regime_data:
        emoji = {'BULL': '🟢', 'NEUTRAL': '🟡', 'CAUTION': '🟠', 'BEAR': '🔴'}.get(regime_data['regime'], '⚪')
        multiplier = regime_data['multiplier']
        would_trade = num_trades if regime_data['allow_entries'] else 0
        regime_adjusted_pnl = pnl * multiplier if regime_data['allow_entries'] else 0

        print(f"{trade_date} {emoji} {regime_data['regime']:8} {multiplier:>5.0%}      {num_trades:3}        {would_trade:3}      ₹{pnl:>10,.0f}")

        swing_total_pnl += pnl
        swing_regime_pnl += regime_adjusted_pnl
        swing_trades_taken += num_trades
        if not regime_data['allow_entries']:
            swing_trades_filtered += num_trades

print("-" * 80)
print(f"Total:                                     {swing_trades_taken:3}                     ₹{swing_total_pnl:>10,.0f}")
print(f"\n📊 SWING Impact:")
print(f"  Trades Filtered (BEAR days): {swing_trades_filtered}")
print(f"  Without Regime Filter: ₹{swing_total_pnl:,.0f}")
print(f"  With Regime Filter:    ₹{swing_regime_pnl:,.0f}")
print(f"  Difference:            ₹{swing_regime_pnl - swing_total_pnl:+,.0f}")

# Summary
print("\n" + "=" * 80)
print("📈 SUMMARY - Market Regime Impact")
print("=" * 80)

print(f"\nDAILY Strategy (30 days):")
print(f"  Total P&L without filter: ₹{daily_total_pnl:>12,.0f}")
print(f"  Total P&L with filter:    ₹{daily_regime_pnl:>12,.0f}")
print(f"  Impact:                   ₹{daily_regime_pnl - daily_total_pnl:>+12,.0f}")
if daily_total_pnl != 0:
    impact_pct = ((daily_regime_pnl - daily_total_pnl) / abs(daily_total_pnl)) * 100
    print(f"  Impact %:                  {impact_pct:>11.1f}%")

print(f"\nSWING Strategy (60 days):")
print(f"  Total P&L without filter: ₹{swing_total_pnl:>12,.0f}")
print(f"  Total P&L with filter:    ₹{swing_regime_pnl:>12,.0f}")
print(f"  Impact:                   ₹{swing_regime_pnl - swing_total_pnl:>+12,.0f}")
if swing_total_pnl != 0:
    impact_pct = ((swing_regime_pnl - swing_total_pnl) / abs(swing_total_pnl)) * 100
    print(f"  Impact %:                  {impact_pct:>11.1f}%")

print(f"\nCOMBINED:")
combined_without = daily_total_pnl + swing_total_pnl
combined_with = daily_regime_pnl + swing_regime_pnl
print(f"  Total P&L without filter: ₹{combined_without:>12,.0f}")
print(f"  Total P&L with filter:    ₹{combined_with:>12,.0f}")
print(f"  Impact:                   ₹{combined_with - combined_without:>+12,.0f}")
if combined_without != 0:
    impact_pct = ((combined_with - combined_without) / abs(combined_without)) * 100
    print(f"  Impact %:                  {impact_pct:>11.1f}%")

print("\n💡 Key Insights:")
if daily_trades_filtered > 0 or swing_trades_filtered > 0:
    print(f"  • Regime filter would have blocked {daily_trades_filtered + swing_trades_filtered} trades on BEAR days")
    print(f"  • Position sizing would have been reduced on CAUTION/NEUTRAL days")
else:
    print(f"  • No BEAR days in the analysis period - regime filter would not have blocked trades")

print(f"  • The regime filter aims to protect capital during unfavorable market conditions")
print(f"  • Reduced position sizing helps preserve capital for better opportunities")

print("\n" + "=" * 80)
