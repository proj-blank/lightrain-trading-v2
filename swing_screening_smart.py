#!/usr/bin/env python3
"""
Smart Swing Trading Screener with 60/20/20 Allocation

This script:
1. Scans ALL liquid stocks (NSE + BSE)
2. Scores each using technical indicators
3. Filters for BUY signals (score >= 60)
4. Applies smart 60/20/20 allocation (Large/Mid/Micro)
5. Selects positions for today

Run this to see what positions would be selected based on today's data.
"""

import sys
sys.path.append('/Users/brosshack/project_blank/Microcap-India')

import yfinance as yf
import pandas as pd
from datetime import datetime
from scripts.signal_generator_v2 import generate_signal_v2
from scripts.smart_allocation import calculate_smart_allocation, select_positions

# Stock universe (liquid stocks only)
STOCK_UNIVERSE = {
    'large_caps': [
        'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
        'BHARTIARTL.NS', 'SBIN.NS', 'BAJFINANCE.NS', 'HINDUNILVR.NS', 'KOTAKBANK.NS',
        'LT.NS', 'ITC.NS', 'ASIANPAINT.NS', 'AXISBANK.NS', 'MARUTI.NS',
        'SUNPHARMA.NS', 'TITAN.NS', 'ULTRACEMCO.NS', 'TATAMOTORS.NS',
        'WIPRO.NS', 'HCLTECH.NS', 'TECHM.NS', 'POWERGRID.NS', 'NTPC.NS',
        'COALINDIA.NS', 'TATASTEEL.NS', 'ONGC.NS', 'HINDALCO.NS',
        'JSWSTEEL.NS', 'BAJAJFINSV.NS', 'HEROMOTOCO.NS', 'INDUSINDBK.NS', 'BRITANNIA.NS',
        'APOLLOHOSP.NS', 'DIVISLAB.NS', 'DRREDDY.NS', 'CIPLA.NS',
        'TATACONSUM.NS', 'GRASIM.NS', 'SBILIFE.NS', 'HDFCLIFE.NS', 'BAJAJ-AUTO.NS',
        'ADANIPORTS.NS', 'BPCL.NS', 'M&M.NS', 'SHRIRAMFIN.NS', 'LTIM.NS'
    ],

    'mid_caps': [
        'PERSISTENT.NS', 'COFORGE.NS', 'MPHASIS.NS', 'LTTS.NS', 'CYIENT.NS',
        'ZYDUSLIFE.NS', 'TORNTPHARM.NS', 'AUROPHARMA.NS', 'LUPIN.NS',
        'LALPATHLAB.NS', 'METROPOLIS.NS', 'CROMPTON.NS', 'HAVELLS.NS', 'VGUARD.NS',
        'RELAXO.NS', 'BATAINDIA.NS', 'TRENT.NS', 'PIDILITIND.NS',
        'APLAPOLLO.NS', 'CENTURYPLY.NS', 'BLUEDART.NS',
        'KAJARIACER.NS', 'JKCEMENT.NS', 'RAMCOCEM.NS', 'ORIENTCEM.NS',
        'CHAMBLFERT.NS', 'DEEPAKNTR.NS', 'AARTI.NS', 'NAVINFLUOR.NS', 'SRF.NS',
        # BSE mid-caps
        'TATAELXSI.BO', 'IPCALAB.BO', 'HONAUT.BO', 'ABBOTINDIA.BO'
    ],

    'micro_caps': [
        # Chemicals
        'FLUOROCHEM.NS', 'FINEORG.NS', 'GALAXYSURF.NS', 'ROSSARI.NS', 'ALKYLAMINE.NS',
        'SHARDACROP.NS', 'DCMSHRIRAM.NS',
        # IT/Tech
        'TANLA.NS', 'KELLTONTEC.NS', 'MASTEK.NS',
        # Engineering
        'ASTRAMICRO.NS', 'ELECON.NS', 'GREAVESCOT.NS', 'WHEELS.NS', 'RATNAMANI.NS',
        # Consumer
        'GOCOLORS.NS', 'SMSLIFE.NS',
        # Pharma
        'SUVEN.NS', 'AARTIDRUGS.NS', 'THYROCARE.NS',
        # Others
        'DIGISPICE.NS', 'RPPINFRA.NS', 'RAJRATAN.NS', 'APLLTD.NS', 'GRINDWELL.NS',
        # BSE micro-caps
        'SYMPHONY.BO', 'SONATSOFTW.BO'
    ]
}

CAPITAL = 1000000  # ₹10 Lakh
MAX_POSITIONS = 7
MIN_SIGNAL_SCORE = 60

def screen_stock(ticker, category):
    """Screen a single stock for BUY signal."""
    try:
        # Download data
        df = yf.download(ticker, period='3mo', interval='1d', progress=False)

        if df.empty or len(df) < 50:
            return None

        # Generate signal
        signal, score, details = generate_signal_v2(df, min_score=MIN_SIGNAL_SCORE)

        if signal == "BUY" and score >= MIN_SIGNAL_SCORE:
            return {
                'ticker': ticker,
                'category': category,
                'signal': signal,
                'score': score,
                'current_price': float(df['Close'].iloc[-1]),
                'details': details
            }

        return None

    except Exception as e:
        print(f"      Error: {e}")
        return None

def screen_all_stocks():
    """Screen all stocks and return BUY candidates by category."""
    print("=" * 80)
    print("🔍 SWING TRADING SCREENER - SMART ALLOCATION")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Capital: ₹{CAPITAL:,.0f}")
    print(f"Max Positions: {MAX_POSITIONS}")
    print(f"Allocation: 60% Large / 20% Mid / 20% Micro (with fallback)")
    print()

    candidates = {
        'large_caps': [],
        'mid_caps': [],
        'micro_caps': []
    }

    total_stocks = sum(len(stocks) for stocks in STOCK_UNIVERSE.values())
    current = 0

    for category, tickers in STOCK_UNIVERSE.items():
        print(f"\n{category.upper().replace('_', ' ')} ({len(tickers)} stocks):")
        print("-" * 80)

        for ticker in tickers:
            current += 1
            print(f"  [{current}/{total_stocks}] {ticker:20s} ", end="", flush=True)

            result = screen_stock(ticker, category)

            if result:
                candidates[category].append(result)
                print(f"✅ BUY | Score: {result['score']:.0f} | ₹{result['current_price']:.2f}")
            else:
                print("⏭️")

    return candidates

def main():
    """Main screening workflow."""
    # 1. Screen all stocks
    print("\n" + "=" * 80)
    print("PHASE 1: SCREENING ALL STOCKS")
    print("=" * 80)

    candidates = screen_all_stocks()

    # 2. Show candidates
    print("\n" + "=" * 80)
    print("BUY CANDIDATES FOUND")
    print("=" * 80)

    for category, stocks in candidates.items():
        cat_name = category.replace('_caps', '').capitalize() + '-caps'
        print(f"\n{cat_name}: {len(stocks)}")
        for stock in sorted(stocks, key=lambda x: x['score'], reverse=True):
            print(f"  {stock['ticker']:20s} Score: {stock['score']:3.0f} | ₹{stock['current_price']:8.2f}")

    total_candidates = sum(len(stocks) for stocks in candidates.values())
    print(f"\nTotal Candidates: {total_candidates}")

    if total_candidates == 0:
        print("\n❌ No BUY signals found. Market may be overbought or trending down.")
        print("   Try again tomorrow!")
        return

    # 3. Apply smart allocation
    print("\n" + "=" * 80)
    print("PHASE 2: SMART ALLOCATION (60/20/20)")
    print("=" * 80)

    allocation_plan = calculate_smart_allocation(
        candidates,
        total_capital=CAPITAL,
        max_positions=MAX_POSITIONS
    )

    # 4. Select positions
    selected = select_positions(candidates, allocation_plan)

    # 5. Show final positions
    print("\n" + "=" * 80)
    print("FINAL POSITIONS FOR TODAY")
    print("=" * 80)
    print()

    if not selected:
        print("❌ No positions selected")
        return

    print(f"{'Ticker':<20s} {'Category':<12s} {'Score':<6s} {'Price':<10s} {'Capital':<12s} {'Qty':<6s}")
    print("-" * 80)

    total_invested = 0
    for pos in sorted(selected, key=lambda x: x['category']):
        # Find the stock details
        for category in candidates.values():
            stock = next((s for s in category if s['ticker'] == pos['ticker']), None)
            if stock:
                qty = int(pos['allocated_capital'] / stock['current_price'])
                actual_investment = qty * stock['current_price']
                total_invested += actual_investment

                print(f"{stock['ticker']:<20s} {pos['category']:<12s} {stock['score']:<6.0f} "
                      f"₹{stock['current_price']:<9.2f} ₹{pos['allocated_capital']:<11,.0f} {qty:<6d}")
                break

    print("-" * 80)
    print(f"Total Positions: {len(selected)}")
    print(f"Total Invested:  ₹{total_invested:,.0f}")
    print(f"Cash Remaining:  ₹{CAPITAL - total_invested:,.0f}")
    print()

    # 6. Allocation breakdown
    print("=" * 80)
    print("ALLOCATION BREAKDOWN")
    print("=" * 80)

    by_category = {}
    for pos in selected:
        cat = pos['category']
        if cat not in by_category:
            by_category[cat] = {'count': 0, 'capital': 0}
        by_category[cat]['count'] += 1
        by_category[cat]['capital'] += pos['allocated_capital']

    for cat in ['Large-cap', 'Mid-cap', 'Micro-cap']:
        if cat in by_category:
            count = by_category[cat]['count']
            capital = by_category[cat]['capital']
            pct = (capital / CAPITAL) * 100
            print(f"{cat:12s}: {count} positions | ₹{capital:,>12.0f} ({pct:>5.1f}%)")

    print("=" * 80)
    print()
    print("✅ Screening complete!")
    print("   These positions would be entered in swing_portfolio.json")
    print("   Run swing_trading.py to execute them.")

if __name__ == "__main__":
    main()
