#!/usr/bin/env python3
"""
Full Backtesting Simulation with Market Regime Filter
Simulates actual trading over past 30 days (DAILY) and 60 days (SWING)
comparing performance WITH and WITHOUT market regime filter
"""
import sys
sys.path.insert(0, '/home/ubuntu/trading')

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from scripts.db_connection import get_db_cursor

# Timezone for comparison
IST = pytz.timezone('Asia/Kolkata')

print("=" * 80)
print("📊 FULL BACKTESTING SIMULATION")
print("=" * 80)
print(f"Analysis Date: {datetime.now().strftime('%d %b %Y, %H:%M IST')}")
print("=" * 80)

# ==================== MARKET REGIME CALCULATION ====================

def calculate_regime_for_date(date):
    """Calculate market regime for a specific historical date"""
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

        # Calculate score
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
            'allow_entries': allow_entries
        }

    except Exception as e:
        return None

# ==================== GET STOCK UNIVERSE ====================

def get_stock_universe():
    """Get list of stocks to backtest from database"""
    # Use common NSE stocks for backtest
    stocks = [
        'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
        'HINDUNILVR.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'ITC.NS', 'KOTAKBANK.NS',
        'LT.NS', 'AXISBANK.NS', 'ASIANPAINT.NS', 'MARUTI.NS', 'HCLTECH.NS',
        'WIPRO.NS', 'ULTRACEMCO.NS', 'TITAN.NS', 'BAJFINANCE.NS', 'NESTLEIND.NS',
        'SUNPHARMA.NS', 'TECHM.NS', 'POWERGRID.NS', 'NTPC.NS', 'TATASTEEL.NS',
        'BAJAJFINSV.NS', 'HDFCLIFE.NS', 'ADANIPORTS.NS', 'M&M.NS', 'INDUSINDBK.NS',
        'TATAMOTORS.NS', 'JSWSTEEL.NS', 'DIVISLAB.NS', 'DRREDDY.NS', 'BRITANNIA.NS',
        'EICHERMOT.NS', 'HEROMOTOCO.NS', 'CIPLA.NS', 'ONGC.NS', 'GRASIM.NS',
        'SHREECEM.NS', 'VEDL.NS', 'BPCL.NS', 'COALINDIA.NS', 'IOC.NS',
        'TATACONSUM.NS', 'UPL.NS', 'HINDALCO.NS', 'ADANIENT.NS', 'APOLLOHOSP.NS'
    ]

    return stocks

# ==================== SCREENING LOGIC ====================

def calculate_rs_rating(ticker, data, market_data):
    """Calculate RS Rating (simplified version)"""
    try:
        if data is None or len(data) < 60:
            return 0

        # 3-month price change
        price_change_3m = ((data['Close'].iloc[-1] - data['Close'].iloc[-60]) / data['Close'].iloc[-60]) * 100

        # Relative to market
        market_change_3m = ((market_data['Close'].iloc[-1] - market_data['Close'].iloc[-60]) / market_data['Close'].iloc[-60]) * 100

        relative_strength = price_change_3m - market_change_3m

        # Normalize to 0-100 scale (simplified)
        rs_rating = min(100, max(0, 50 + relative_strength))

        return rs_rating
    except:
        return 0

def check_daily_signals(data):
    """Check if stock meets DAILY strategy criteria"""
    try:
        if data is None or len(data) < 20:
            return False, None

        close = data['Close'].iloc[-1]
        sma20 = data['Close'].rolling(20).mean().iloc[-1]
        volume = data['Volume'].iloc[-1]
        avg_volume = data['Volume'].rolling(20).mean().iloc[-1]

        # Price above 20 SMA
        if close <= sma20:
            return False, None

        # Volume above average
        if volume <= avg_volume * 1.2:
            return False, None

        # Price momentum
        price_change = ((close - data['Close'].iloc[-2]) / data['Close'].iloc[-2]) * 100
        if price_change <= 0:
            return False, None

        return True, close

    except:
        return False, None

def check_swing_signals(data):
    """Check if stock meets SWING strategy criteria"""
    try:
        if data is None or len(data) < 50:
            return False, None

        close = data['Close'].iloc[-1]
        sma20 = data['Close'].rolling(20).mean().iloc[-1]
        sma50 = data['Close'].rolling(50).mean().iloc[-1]

        # Price above both SMAs
        if close <= sma20 or close <= sma50:
            return False, None

        # SMAs in uptrend
        if sma20 <= sma50:
            return False, None

        # Check for pullback and bounce
        lowest_10d = data['Close'].iloc[-10:].min()
        if close < lowest_10d * 1.02:  # Not bouncing yet
            return False, None

        return True, close

    except:
        return False, None

# ==================== BACKTESTING ENGINE ====================

def simulate_trade(entry_price, data_after_entry, strategy, regime_multiplier):
    """Simulate a trade from entry to exit"""

    # Position sizing based on regime
    base_position_size = 10000  # ₹10,000 per trade
    position_size = base_position_size * regime_multiplier

    if position_size == 0:
        return 0, 0, "NO_ENTRY"

    quantity = int(position_size / entry_price)
    if quantity == 0:
        return 0, 0, "NO_ENTRY"

    # Stop loss and targets
    if strategy == "DAILY":
        stop_loss = entry_price * 0.98  # 2% stop
        target = entry_price * 1.04      # 4% target
        max_hold_days = 3
    else:  # SWING
        stop_loss = entry_price * 0.95  # 5% stop
        target = entry_price * 1.10      # 10% target
        max_hold_days = 10

    # Simulate holding period
    for i, (date, row) in enumerate(data_after_entry.iterrows()):
        if i >= max_hold_days:
            # Exit at max hold period
            exit_price = row['Close']
            pnl = (exit_price - entry_price) * quantity
            return pnl, i + 1, "TIME_EXIT"

        # Check stop loss
        if row['Low'] <= stop_loss:
            pnl = (stop_loss - entry_price) * quantity
            return pnl, i + 1, "STOP_LOSS"

        # Check target
        if row['High'] >= target:
            pnl = (target - entry_price) * quantity
            return pnl, i + 1, "TARGET"

    # Exit at end of available data
    if len(data_after_entry) > 0:
        exit_price = data_after_entry['Close'].iloc[-1]
        pnl = (exit_price - entry_price) * quantity
        return pnl, len(data_after_entry), "END_OF_DATA"

    return 0, 0, "NO_EXIT"

# ==================== MAIN BACKTEST ====================

print("\n📥 Loading stock universe...")
stock_universe = get_stock_universe()
print(f"   ✅ Loaded {len(stock_universe)} stocks")

print("\n📥 Downloading market data (Nifty 50)...")
nifty = yf.Ticker("^NSEI")
nifty_data = nifty.history(start=datetime.now(IST) - timedelta(days=120), end=datetime.now(IST))
print(f"   ✅ {len(nifty_data)} days of market data")

print("\n📥 Downloading stock data...")
all_stock_data = {}
for ticker in stock_universe[:50]:  # Limit to 50 stocks for reasonable runtime
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(start=datetime.now(IST) - timedelta(days=120), end=datetime.now(IST))
        if len(data) >= 60:
            all_stock_data[ticker] = data
    except:
        continue
print(f"   ✅ Downloaded data for {len(all_stock_data)} stocks")

# ==================== DAILY STRATEGY BACKTEST (30 days) ====================

print("\n" + "=" * 80)
print("📈 DAILY STRATEGY BACKTEST (30 days)")
print("=" * 80)

daily_start = datetime.now(IST) - timedelta(days=40)
daily_end = datetime.now(IST)

trades_without_regime = []
trades_with_regime = []

current_date = daily_start
while current_date <= daily_end:
    if current_date.weekday() < 5:  # Trading days only
        # Calculate regime
        regime_data = calculate_regime_for_date(current_date)

        if regime_data:
            regime = regime_data['regime']
            multiplier = regime_data['multiplier']
            allow_entries = regime_data['allow_entries']

            # Screen stocks
            for ticker, data in all_stock_data.items():
                # Get data up to current_date
                data_until_now = data[data.index < current_date]

                if len(data_until_now) < 20:
                    continue

                # Check RS Rating
                rs_rating = calculate_rs_rating(ticker, data_until_now, nifty_data[nifty_data.index < current_date])

                if rs_rating < 70:  # RS threshold
                    continue

                # Check technical signals
                signal, entry_price = check_daily_signals(data_until_now)

                if signal:
                    # Get future data for exit simulation
                    data_after = data[data.index >= current_date]

                    # WITHOUT REGIME - full position
                    pnl_no_regime, days_held, exit_reason = simulate_trade(
                        entry_price, data_after, "DAILY", 1.0
                    )

                    if pnl_no_regime != 0:
                        trades_without_regime.append({
                            'date': current_date,
                            'ticker': ticker,
                            'entry': entry_price,
                            'pnl': pnl_no_regime,
                            'days': days_held,
                            'exit': exit_reason
                        })

                    # WITH REGIME - adjusted position
                    if allow_entries:
                        pnl_with_regime, days_held, exit_reason = simulate_trade(
                            entry_price, data_after, "DAILY", multiplier
                        )

                        if pnl_with_regime != 0:
                            trades_with_regime.append({
                                'date': current_date,
                                'ticker': ticker,
                                'entry': entry_price,
                                'pnl': pnl_with_regime,
                                'days': days_held,
                                'exit': exit_reason,
                                'regime': regime,
                                'multiplier': multiplier
                            })

    current_date += timedelta(days=1)

# Results
total_pnl_no_regime = sum(t['pnl'] for t in trades_without_regime)
total_pnl_with_regime = sum(t['pnl'] for t in trades_with_regime)
num_trades_no_regime = len(trades_without_regime)
num_trades_with_regime = len(trades_with_regime)

wins_no_regime = len([t for t in trades_without_regime if t['pnl'] > 0])
wins_with_regime = len([t for t in trades_with_regime if t['pnl'] > 0])

print(f"\n📊 DAILY Strategy Results:")
print(f"\n   WITHOUT Regime Filter:")
print(f"      Trades: {num_trades_no_regime}")
print(f"      Total P&L: ₹{total_pnl_no_regime:,.0f}")
print(f"      Win Rate: {(wins_no_regime/num_trades_no_regime*100) if num_trades_no_regime > 0 else 0:.1f}%")
print(f"      Avg P&L per trade: ₹{(total_pnl_no_regime/num_trades_no_regime) if num_trades_no_regime > 0 else 0:,.0f}")

print(f"\n   WITH Regime Filter:")
print(f"      Trades: {num_trades_with_regime}")
print(f"      Total P&L: ₹{total_pnl_with_regime:,.0f}")
print(f"      Win Rate: {(wins_with_regime/num_trades_with_regime*100) if num_trades_with_regime > 0 else 0:.1f}%")
print(f"      Avg P&L per trade: ₹{(total_pnl_with_regime/num_trades_with_regime) if num_trades_with_regime > 0 else 0:,.0f}")

print(f"\n   IMPACT:")
print(f"      P&L Difference: ₹{total_pnl_with_regime - total_pnl_no_regime:+,.0f}")
print(f"      Trades Filtered: {num_trades_no_regime - num_trades_with_regime}")

# ==================== SWING STRATEGY BACKTEST (60 days) ====================

print("\n" + "=" * 80)
print("📈 SWING STRATEGY BACKTEST (60 days)")
print("=" * 80)

swing_start = datetime.now(IST) - timedelta(days=70)
swing_end = datetime.now(IST)

swing_trades_without = []
swing_trades_with = []

current_date = swing_start
while current_date <= swing_end:
    if current_date.weekday() < 5:
        regime_data = calculate_regime_for_date(current_date)

        if regime_data:
            regime = regime_data['regime']
            multiplier = regime_data['multiplier']
            allow_entries = regime_data['allow_entries']

            for ticker, data in all_stock_data.items():
                data_until_now = data[data.index < current_date]

                if len(data_until_now) < 50:
                    continue

                rs_rating = calculate_rs_rating(ticker, data_until_now, nifty_data[nifty_data.index < current_date])

                if rs_rating < 80:  # Higher RS threshold for swing
                    continue

                signal, entry_price = check_swing_signals(data_until_now)

                if signal:
                    data_after = data[data.index >= current_date]

                    # WITHOUT REGIME
                    pnl_no_regime, days_held, exit_reason = simulate_trade(
                        entry_price, data_after, "SWING", 1.0
                    )

                    if pnl_no_regime != 0:
                        swing_trades_without.append({
                            'date': current_date,
                            'ticker': ticker,
                            'entry': entry_price,
                            'pnl': pnl_no_regime,
                            'days': days_held,
                            'exit': exit_reason
                        })

                    # WITH REGIME
                    if allow_entries:
                        pnl_with_regime, days_held, exit_reason = simulate_trade(
                            entry_price, data_after, "SWING", multiplier
                        )

                        if pnl_with_regime != 0:
                            swing_trades_with.append({
                                'date': current_date,
                                'ticker': ticker,
                                'entry': entry_price,
                                'pnl': pnl_with_regime,
                                'days': days_held,
                                'exit': exit_reason,
                                'regime': regime,
                                'multiplier': multiplier
                            })

    current_date += timedelta(days=1)

# Results
total_swing_no_regime = sum(t['pnl'] for t in swing_trades_without)
total_swing_with_regime = sum(t['pnl'] for t in swing_trades_with)
num_swing_no_regime = len(swing_trades_without)
num_swing_with_regime = len(swing_trades_with)

wins_swing_no = len([t for t in swing_trades_without if t['pnl'] > 0])
wins_swing_with = len([t for t in swing_trades_with if t['pnl'] > 0])

print(f"\n📊 SWING Strategy Results:")
print(f"\n   WITHOUT Regime Filter:")
print(f"      Trades: {num_swing_no_regime}")
print(f"      Total P&L: ₹{total_swing_no_regime:,.0f}")
print(f"      Win Rate: {(wins_swing_no/num_swing_no_regime*100) if num_swing_no_regime > 0 else 0:.1f}%")
print(f"      Avg P&L per trade: ₹{(total_swing_no_regime/num_swing_no_regime) if num_swing_no_regime > 0 else 0:,.0f}")

print(f"\n   WITH Regime Filter:")
print(f"      Trades: {num_swing_with_regime}")
print(f"      Total P&L: ₹{total_swing_with_regime:,.0f}")
print(f"      Win Rate: {(wins_swing_with/num_swing_with_regime*100) if num_swing_with_regime > 0 else 0:.1f}%")
print(f"      Avg P&L per trade: ₹{(total_swing_with_regime/num_swing_with_regime) if num_swing_with_regime > 0 else 0:,.0f}")

print(f"\n   IMPACT:")
print(f"      P&L Difference: ₹{total_swing_with_regime - total_swing_no_regime:+,.0f}")
print(f"      Trades Filtered: {num_swing_no_regime - num_swing_with_regime}")

# ==================== FINAL SUMMARY ====================

print("\n" + "=" * 80)
print("📊 FINAL SUMMARY - Market Regime Impact")
print("=" * 80)

combined_no_regime = total_pnl_no_regime + total_swing_no_regime
combined_with_regime = total_pnl_with_regime + total_swing_with_regime

print(f"\nCOMBINED RESULTS:")
print(f"   WITHOUT Regime Filter: ₹{combined_no_regime:>12,.0f}")
print(f"   WITH Regime Filter:    ₹{combined_with_regime:>12,.0f}")
print(f"   Total Impact:          ₹{combined_with_regime - combined_no_regime:>+12,.0f}")

if combined_no_regime != 0:
    impact_pct = ((combined_with_regime - combined_no_regime) / abs(combined_no_regime)) * 100
    print(f"   Impact %:               {impact_pct:>11.1f}%")

print(f"\n💡 Key Insights:")
print(f"   • Total trades without filter: {num_trades_no_regime + num_swing_no_regime}")
print(f"   • Total trades with filter: {num_trades_with_regime + num_swing_with_regime}")
print(f"   • Trades filtered out: {(num_trades_no_regime + num_swing_no_regime) - (num_trades_with_regime + num_swing_with_regime)}")
print(f"   • Regime filter adjusts position sizing and blocks trades in BEAR markets")
print(f"   • This helps preserve capital during unfavorable market conditions")

print("\n" + "=" * 80)
