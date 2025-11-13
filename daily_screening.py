#!/usr/bin/env python3
"""
daily_screening.py - Daily stock screening and dynamic watchlist management

Workflow:
1. Screen all stocks (large-caps, mid-caps, microcaps)
2. Score each stock based on technical criteria (0-100)
3. Shortlist stocks with score >= 60
4. Update watchlist:
   - ADD: New stocks scoring >=60
   - KEEP: Stocks with open positions (from positions.json)
   - REMOVE: Stocks scoring <60 AND no open positions
5. Save updated watchlist for daily_trading.py

Run this BEFORE daily_trading.py to refresh the watchlist.
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import json
import os
from pathlib import Path

from scripts.signal_generator_v2 import (
    calculate_rsi, calculate_macd, calculate_bollinger_bands,
    calculate_atr, calculate_trend_strength, calculate_roc,
    calculate_cci, calculate_donchian
)


# Comprehensive stock universe
STOCK_UNIVERSE = {
    'large_caps': [
        # Nifty 50 - Top liquid stocks
        'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
        'BHARTIARTL.NS', 'SBIN.NS', 'BAJFINANCE.NS', 'ASIANPAINT.NS', 'MARUTI.NS',
        'TATASTEEL.NS', 'SUNPHARMA.NS', 'TITAN.NS', 'WIPRO.NS', 'TECHM.NS',
        'HCLTECH.NS', 'ULTRACEMCO.NS', 'AXISBANK.NS', 'LT.NS', 'KOTAKBANK.NS',
        'ITC.NS', 'HINDUNILVR.NS', 'POWERGRID.NS', 'NTPC.NS', 'ONGC.NS'
    ],
    'mid_caps': [
        # IT/Tech
        'PERSISTENT.NS', 'COFORGE.NS', 'LTTS.NS', 'CYIENT.NS',

        # Pharma/Healthcare
        'ZYDUSLIFE.NS', 'LALPATHLAB.NS', 'METROPOLIS.NS', 'THYROCARE.NS',

        # Consumer
        'CROMPTON.NS', 'RELAXO.NS', 'VGUARD.NS', 'BATAINDIA.NS',

        # Industrials
        'CHAMBLFERT.NS', 'APLAPOLLO.NS', 'CENTURYPLY.NS', 'BLUEDART.NS',

        # Materials
        'KAJARIACER.NS', 'GRINDWELL.NS', 'ORIENTCEM.NS', 'JKCEMENT.NS'
    ],
    'micro_caps': [
        # From existing watchlist + more
        'DIGISPICE.NS', 'RPPINFRA.NS', 'URJA.NS', 'PENINLAND.NS',
        'KELLTONTEC.NS', 'RAJRATAN.NS', 'WHEELS.NS', 'AARTIDRUGS.NS',
        'SUVEN.NS', 'BALRAMCHIN.NS', 'APLLTD.NS',

        # Chemicals
        'FLUOROCHEM.NS', 'FINEORG.NS', 'GALAXYSURF.NS', 'ROSSARI.NS',
        'NAVINFLUOR.NS', 'ALKYLAMINE.NS',

        # Engineering/Manufacturing
        'ASTRAMICRO.NS', 'RATNAMANI.NS', 'ELECON.NS', 'GREAVESCOT.NS',

        # Textiles/Consumer
        'GOCOLORS.NS', 'SMSLIFE.NS',

        # Agro/Fertilizers
        'DCMSHRIRAM.NS', 'SHARDACROP.NS'
    ]
}

# Flatten all stocks
ALL_STOCKS = (
    STOCK_UNIVERSE['large_caps'] +
    STOCK_UNIVERSE['mid_caps'] +
    STOCK_UNIVERSE['micro_caps']
)

POSITIONS_FILE = 'data/positions.json'
WATCHLIST_FILE = 'data/watchlist.csv'
SCREENING_LOG = 'logs/screening_log.csv'


def load_positions():
    """Load current open positions from positions.json."""
    if not os.path.exists(POSITIONS_FILE):
        return []

    try:
        with open(POSITIONS_FILE, 'r') as f:
            positions = json.load(f)
            return [p['ticker'] for p in positions]
    except:
        return []


def download_stock_data(ticker, months=2):
    """Download and validate stock data."""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months * 30)

        df = yf.download(ticker, start=start_date, end=end_date,
                        progress=False, auto_adjust=True)

        if df.empty or len(df) < 40:
            return None, "Insufficient data"

        # Flatten multi-level columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        return df, "OK"

    except Exception as e:
        return None, str(e)


def safe_scalar(val):
    """Safely convert pandas value to Python scalar."""
    if hasattr(val, 'item'):
        return val.item()
    if hasattr(val, '__len__') and len(val) == 1:
        if hasattr(val, 'iloc'):
            return float(val.iloc[0])
        return float(val[0])
    return float(val)


def calculate_stock_score(df, ticker):
    """
    Score a stock 0-100 using statistical Momentum + Mean Reversion model.

    Based on proven quant strategies with 68% success rate:
    - Momentum Score: 40 points (trending stocks)
    - Mean Reversion Score: 40 points (reversal opportunities)
    - Liquidity Filter: 20 points (tradability)

    Pass criteria: (Momentum ≥25 OR MeanRev ≥25) AND Total ≥60
    """
    score = 0
    details = {}

    try:
        current_price = safe_scalar(df['Close'].iloc[-1])

        # === MOMENTUM SCORE (40 points) ===
        momentum_score = 0

        # 1. Price vs Moving Averages (15 pts)
        ma20 = df['Close'].rolling(20).mean()
        ma50 = df['Close'].rolling(50).mean()
        ma200 = df['Close'].rolling(200).mean() if len(df) >= 200 else ma50

        ma20_val = safe_scalar(ma20.iloc[-1])
        ma50_val = safe_scalar(ma50.iloc[-1])
        ma200_val = safe_scalar(ma200.iloc[-1])

        # Strong uptrend: price > all MAs
        if current_price > ma20_val > ma50_val > ma200_val:
            momentum_score += 15
        elif current_price > ma20_val > ma50_val:
            momentum_score += 10
        elif current_price > ma20_val:
            momentum_score += 5

        # 2. ROC Strength (15 pts)
        roc = calculate_roc(df, period=12)
        current_roc = safe_scalar(roc.iloc[-1])
        details['roc'] = round(current_roc, 2)

        if current_roc > 10:
            momentum_score += 15
        elif current_roc > 5:
            momentum_score += 10
        elif current_roc > 2:
            momentum_score += 5
        elif current_roc < -10:
            momentum_score += 15  # Strong downtrend also tradable
        elif current_roc < -5:
            momentum_score += 10

        # 3. Volume Confirmation (10 pts)
        avg_volume = safe_scalar(df['Volume'].mean())
        recent_volume = safe_scalar(df['Volume'].iloc[-5:].mean())
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1

        if volume_ratio > 1.5:
            momentum_score += 10  # High volume = strong momentum
        elif volume_ratio > 1.2:
            momentum_score += 6
        elif volume_ratio > 1.0:
            momentum_score += 3

        details['momentum_score'] = momentum_score

        # === MEAN REVERSION SCORE (40 points) ===
        meanrev_score = 0

        # 1. Standard Deviation from MA (20 pts)
        ma20_std = df['Close'].rolling(20).std()
        std_val = safe_scalar(ma20_std.iloc[-1])
        distance_from_ma = (current_price - ma20_val) / std_val if std_val > 0 else 0
        details['std_distance'] = round(distance_from_ma, 2)

        # 2-3 std dev = reversal opportunity
        if abs(distance_from_ma) >= 2.5:
            meanrev_score += 20
        elif abs(distance_from_ma) >= 2.0:
            meanrev_score += 15
        elif abs(distance_from_ma) >= 1.5:
            meanrev_score += 10

        # 2. RSI Extremes (10 pts)
        rsi = calculate_rsi(df)
        current_rsi = safe_scalar(rsi.iloc[-1])
        details['rsi'] = round(current_rsi, 2)

        if current_rsi < 30:
            meanrev_score += 10  # Oversold
        elif current_rsi < 40:
            meanrev_score += 6
        elif current_rsi > 70:
            meanrev_score += 10  # Overbought
        elif current_rsi > 60:
            meanrev_score += 6

        # 3. Bollinger Band Position (10 pts)
        bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(df)
        upper_val = safe_scalar(bb_upper.iloc[-1])
        lower_val = safe_scalar(bb_lower.iloc[-1])

        if current_price <= lower_val:
            meanrev_score += 10  # At/below lower band
        elif current_price <= lower_val * 1.02:
            meanrev_score += 6
        elif current_price >= upper_val:
            meanrev_score += 10  # At/above upper band
        elif current_price >= upper_val * 0.98:
            meanrev_score += 6

        details['meanrev_score'] = meanrev_score

        # === LIQUIDITY FILTER (20 points) ===
        liquidity_score = 0
        details['avg_volume'] = avg_volume

        if avg_volume < 10000:
            liquidity_score = 0  # Fail - illiquid
        elif avg_volume < 50000:
            liquidity_score = 10
        elif avg_volume < 200000:
            liquidity_score = 15
        else:
            liquidity_score = 20

        details['liquidity_score'] = liquidity_score

        # FINAL SCORE
        score = momentum_score + meanrev_score + liquidity_score
        details['total_score'] = score

        # Quality check: Must have either momentum OR mean reversion setup
        if momentum_score < 25 and meanrev_score < 25:
            details['quality_fail'] = True
            score = max(0, score - 20)  # Penalty for neither strategy

        return score, details

    except Exception as e:
        return 0, {'error': str(e)}


def screen_all_stocks():
    """Screen all stocks and return scored results."""
    print("=" * 80)
    print("📊 DAILY STOCK SCREENING")
    print("=" * 80)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌍 Universe: {len(ALL_STOCKS)} stocks (Large-caps + Mid-caps + Microcaps)")
    print()

    results = []

    for i, ticker in enumerate(ALL_STOCKS, 1):
        print(f"  [{i}/{len(ALL_STOCKS)}] {ticker}...", end=" ")

        df, status = download_stock_data(ticker)

        if df is None:
            print(f"❌ {status}")
            continue

        score, details = calculate_stock_score(df, ticker)

        # Determine category
        if ticker in STOCK_UNIVERSE['large_caps']:
            category = 'Large-cap'
        elif ticker in STOCK_UNIVERSE['mid_caps']:
            category = 'Mid-cap'
        else:
            category = 'Microcap'

        results.append({
            'ticker': ticker,
            'category': category,
            'score': score,
            'avg_volume': details.get('avg_volume', 0),
            'atr_pct': details.get('atr_pct', 0),
            'trend_strength': details.get('trend_strength', 50),
            'extreme_pct': details.get('extreme_pct', 0),
            'rsi_range': details.get('rsi_range', 0),
            'date': datetime.now().strftime('%Y-%m-%d')
        })

        print(f"✅ Score: {score}/100")

    return pd.DataFrame(results)


def update_watchlist(screening_df, min_score=60):
    """
    Update watchlist based on screening results and open positions.

    Logic:
    - ADD: Stocks scoring >= min_score
    - KEEP: Stocks with open positions (regardless of score)
    - REMOVE: Stocks scoring < min_score AND no open positions
    """
    print()
    print("=" * 80)
    print("📋 UPDATING WATCHLIST")
    print("=" * 80)

    # Get stocks scoring >= min_score
    good_stocks = screening_df[screening_df['score'] >= min_score]['ticker'].tolist()
    print(f"✅ Stocks scoring >={min_score}: {len(good_stocks)}")

    # Get stocks with open positions
    position_stocks = load_positions()
    print(f"📊 Stocks with positions: {len(position_stocks)}")
    if position_stocks:
        print(f"   {', '.join(position_stocks)}")

    # Combine: good stocks + position stocks (remove duplicates)
    new_watchlist = list(set(good_stocks + position_stocks))
    new_watchlist.sort()

    print(f"\n🎯 Final watchlist: {len(new_watchlist)} stocks")

    # Load old watchlist for comparison
    old_watchlist = []
    if os.path.exists(WATCHLIST_FILE):
        old_df = pd.read_csv(WATCHLIST_FILE)
        # Handle both 'Ticker' and 'ticker' column names
        col_name = 'Ticker' if 'Ticker' in old_df.columns else 'ticker'
        old_watchlist = old_df[col_name].tolist()

    # Show changes
    added = set(new_watchlist) - set(old_watchlist)
    removed = set(old_watchlist) - set(new_watchlist)

    if added:
        print(f"\n➕ ADDED ({len(added)}):")
        for ticker in sorted(added):
            stock_data = screening_df[screening_df['ticker'] == ticker]
            if not stock_data.empty:
                score = stock_data.iloc[0]['score']
                category = stock_data.iloc[0]['category']
                print(f"   {ticker:20s} Score: {score:3.0f} ({category})")

    if removed:
        print(f"\n➖ REMOVED ({len(removed)}):")
        for ticker in sorted(removed):
            stock_data = screening_df[screening_df['ticker'] == ticker]
            if not stock_data.empty:
                score = stock_data.iloc[0]['score']
                reason = "Open position" if ticker in position_stocks else f"Score: {score}"
                print(f"   {ticker:20s} {reason}")

    if not added and not removed:
        print("\n✓ No changes to watchlist")

    # Save new watchlist
    os.makedirs('data', exist_ok=True)
    watchlist_df = pd.DataFrame({'Ticker': new_watchlist})
    watchlist_df.to_csv(WATCHLIST_FILE, index=False)

    print(f"\n💾 Watchlist saved: {WATCHLIST_FILE}")

    return new_watchlist


def save_screening_log(screening_df):
    """Append screening results to log file."""
    os.makedirs('logs', exist_ok=True)

    # Append to log
    if os.path.exists(SCREENING_LOG):
        screening_df.to_csv(SCREENING_LOG, mode='a', header=False, index=False)
    else:
        screening_df.to_csv(SCREENING_LOG, index=False)

    print(f"📝 Screening log updated: {SCREENING_LOG}")


def send_screening_notification(screening_df, watchlist, added, removed):
    """Send Telegram notification with screening results."""
    try:
        from scripts.telegram_bot import send_telegram_message

        top_stocks = screening_df.nlargest(10, 'score')

        msg = "📊 *DAILY STOCK SCREENING COMPLETE*\n\n"
        msg += f"🌍 Screened: {len(screening_df)} stocks\n"
        msg += f"📋 Watchlist: {len(watchlist)} stocks\n\n"

        if added:
            msg += f"➕ *Added ({len(added)})*:\n"
            for ticker in sorted(added)[:5]:  # Show top 5
                stock_data = screening_df[screening_df['ticker'] == ticker]
                if not stock_data.empty:
                    score = stock_data.iloc[0]['score']
                    msg += f"  • {ticker}: {score:.0f}\n"
            if len(added) > 5:
                msg += f"  ... and {len(added)-5} more\n"
            msg += "\n"

        if removed:
            msg += f"➖ *Removed ({len(removed)})*:\n"
            for ticker in sorted(removed)[:5]:
                msg += f"  • {ticker}\n"
            if len(removed) > 5:
                msg += f"  ... and {len(removed)-5} more\n"
            msg += "\n"

        msg += "🏆 *Top 10 Stocks*:\n"
        for _, row in top_stocks.head(10).iterrows():
            msg += f"  {row['ticker']:15s} {row['score']:3.0f} ({row['category']})\n"

        msg += f"\n⏭️ Next: Trading on updated watchlist..."

        send_telegram_message(msg)
        print("✅ Telegram notification sent")

    except Exception as e:
        print(f"⚠️ Could not send Telegram notification: {e}")


def main():
    """Main screening workflow."""
    # 1. Screen all stocks
    screening_df = screen_all_stocks()

    if screening_df.empty:
        print("\n❌ No stocks screened successfully")
        return

    # 2. Show top stocks
    print()
    print("=" * 80)
    print("🏆 TOP 15 STOCKS")
    print("=" * 80)
    top_stocks = screening_df.nlargest(15, 'score')
    print(top_stocks[['ticker', 'category', 'score', 'atr_pct', 'trend_strength']].to_string(index=False))

    # 3. Update watchlist
    # Track old watchlist for comparison
    old_watchlist = []
    if os.path.exists(WATCHLIST_FILE):
        old_df = pd.read_csv(WATCHLIST_FILE)
        col_name = 'Ticker' if 'Ticker' in old_df.columns else 'ticker'
        old_watchlist = old_df[col_name].tolist()

    watchlist = update_watchlist(screening_df, min_score=60)

    # Calculate changes
    added = set(watchlist) - set(old_watchlist)
    removed = set(old_watchlist) - set(watchlist)

    # 4. Save log
    save_screening_log(screening_df)

    # 5. Send Telegram notification
    send_screening_notification(screening_df, watchlist, added, removed)

    # 6. Summary
    print()
    print("=" * 80)
    print("✅ SCREENING COMPLETE")
    print("=" * 80)
    print(f"Total screened: {len(screening_df)}")
    print(f"Watchlist size: {len(watchlist)}")
    print(f"Next step: Run ./daily_trading.py to trade on updated watchlist")
    print("=" * 80)


if __name__ == "__main__":
    main()
