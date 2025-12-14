#!/usr/bin/env python3
"""
THUNDER Strategy Pipeline
Scans universe → Finds earnings → Runs Dexter → Picks top candidates
"""
import sys
sys.path.insert(0, '/home/ubuntu/trading')

from datetime import datetime
from earnings_calendar import update_earnings_calendar, get_earnings_in_target_window
from thunder_dexter_analyzer import analyze_thunder_candidate
from thunder_entry import enter_thunder_position
from scripts.db_connection import get_db_cursor
from scripts.telegram_bot import send_telegram_message
import pandas as pd
import yfinance as yf

# Stock universe (from your existing screening)
LARGE_CAPS = ['TCS.NS', 'INFY.NS', 'HCLTECH.NS', 'WIPRO.NS', 'TECHM.NS',
              'RELIANCE.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'SBIN.NS',
              'BHARTIARTL.NS', 'LT.NS', 'ASIANPAINT.NS', 'MARUTI.NS']

MID_CAPS = ['MPHASIS.NS', 'PERSISTENT.NS', 'COFORGE.NS', 'LTTS.NS',
            'BANKBARODA.NS', 'PNB.NS', 'INDUSINDBK.NS']


# Market hours check (moved to function call)

def check_and_exit_profitable_positions():
    """Check ACTIVE positions with 5%+ profit and exit them"""
    print("\n" + "="*70)
    print("💰 CHECKING ACTIVE POSITIONS FOR PROFIT TARGETS")
    print("="*70)

    MIN_PROFIT_PCT = 5.0  # Exit if profit >= 5%

    try:
        with get_db_cursor() as cur:
            # Get all ACTIVE THUNDER positions from positions table
            cur.execute("""
                SELECT ticker, entry_date, entry_price, quantity
                FROM positions
                WHERE status = 'HOLD' AND strategy = 'THUNDER'
                ORDER BY entry_date DESC
            """)
            positions = cur.fetchall()

            if not positions:
                print("✅ No active positions to check\n")
                return 0

            print(f"📊 Found {len(positions)} active position(s)\n")

            exited = 0
            for pos in positions:
                ticker = pos['ticker']
                entry_price = float(pos['entry_price'])
                quantity = int(pos['quantity'])
                entry_date = pos['entry_date']

                # Get current price
                try:
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period='1d')
                    if hist.empty:
                        print(f"⚠️ {ticker}: Could not fetch price, skipping")
                        continue

                    current_price = float(hist['Close'].iloc[-1])
                    pnl = (current_price - entry_price) * quantity
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100

                    print(f"📈 {ticker}: Entry ₹{entry_price:.2f} → Current ₹{current_price:.2f} ({pnl_pct:+.2f}%)")

                    # Check if profit target hit
                    if pnl_pct >= MIN_PROFIT_PCT:
                        print(f"   ✅ PROFIT TARGET HIT! Exiting position...")

                        # Update positions table (same as DAILY/SWING strategies)
                        cur.execute("""
                            UPDATE positions
                            SET status = 'CLOSED',
                                exit_date = CURRENT_DATE,
                                current_price = %s,
                                realized_pnl = %s
                            WHERE ticker = %s
                              AND strategy = 'THUNDER'
                              AND entry_date = %s
                              AND status = 'HOLD'
                        """, (current_price, pnl, ticker, entry_date))

                        # Send Telegram alert
                        emoji = "📈" if pnl > 0 else "📉"
                        send_telegram_message(f"""⚡ <b>THUNDER POSITION CLOSED</b>

{emoji} <b>{ticker}</b>
💰 Entry: ₹{entry_price:.2f} → Exit: ₹{current_price:.2f}
📦 Quantity: {quantity} shares
💵 PnL: ₹{pnl:,.0f} ({pnl_pct:+.2f}%)

📅 Entry: {entry_date}
📅 Exit: {datetime.now().date()}

💭 <b>Reason:</b> Profit target hit ({pnl_pct:.1f}% >= {MIN_PROFIT_PCT}%)
""", parse_mode='HTML')

                        print(f"   📱 Telegram alert sent")
                        print(f"   ✅ Position closed! PnL: ₹{pnl:,.0f}\n")
                        exited += 1
                    else:
                        print(f"   ⏰ Holding (target {MIN_PROFIT_PCT}% not reached)\n")

                except Exception as e:
                    print(f"⚠️ {ticker}: Error checking position: {e}\n")
                    continue

            if exited > 0:
                print(f"✅ Exited {exited} profitable position(s)\n")
            else:
                print(f"ℹ️ No positions met profit target\n")

            return exited

    except Exception as e:
        print(f"❌ Error checking positions: {e}\n")
        return 0

def run_thunder_pipeline():
    """Complete THUNDER strategy pipeline"""

    # MARKET HOURS CHECK
    from datetime import datetime
    import pytz
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    hour, minute = now.hour, now.minute
    is_market_open = ((hour == 9 and minute >= 15) or (9 < hour < 15) or (hour == 15 and minute <= 30))

    print("⚡" * 35)
    print("⚡ THUNDER STRATEGY PIPELINE ⚡")
    print("⚡" * 35)

    if is_market_open:
        print(f"✅ Market Open - {now.strftime('%I:%M %p IST')}")
    else:
        print(f"⚠️ Market Closed - {now.strftime('%I:%M %p IST')} (Hours: 9:15 AM - 3:30 PM)")
        print("⚠️ Will only check for profit exits, skipping new entries")

    # Step 0: Check and exit profitable positions FIRST (frees up capital)
    # This runs even if market is closed (uses yesterday's closing prices)
    check_and_exit_profitable_positions()

    # Only proceed with new entries if market is open
    if not is_market_open:
        print("\n❌ Skipping new entries - market closed")
        return

    # Step 1: Load universe
    universe = LARGE_CAPS + MID_CAPS
    print(f"\n📊 Stock Universe: {len(universe)} stocks")

    # Step 2: Update earnings calendar
    print(f"\n📅 Updating earnings calendar...")
    update_earnings_calendar(universe)

    # Step 3: Find earnings in target window (14-30 days)
    print(f"\n🎯 Finding earnings in 14-30 day window...")
    opportunities = get_earnings_in_target_window(min_days=14, max_days=30)

    if opportunities.empty:
        print("\n❌ No earnings in target window")
        return

    print(f"\n✅ Found {len(opportunities)} earnings opportunities")

    # Step 4: Run Dexter analysis on each
    results = []

    for _, opp in opportunities.iterrows():
        ticker = opp['ticker']
        earnings_date = opp['earnings_date']

        print(f"\n{'='*70}")
        print(f"Analyzing: {ticker}")

        analysis = analyze_thunder_candidate(ticker, earnings_date)

        if analysis:
            results.append(analysis)

    # Step 5: Rank by Dexter score
    if not results:
        print("\n❌ No successful analyses")
        return

    df = pd.DataFrame(results)
    df = df.sort_values('dexter_score', ascending=False)

    print(f"\n{'='*70}")
    print("⚡ TOP THUNDER CANDIDATES ⚡")
    print(f"{'='*70}\n")

    for i, row in df.head(5).iterrows():
        print(f"{row['dexter_score']}/100  {row['ticker']:15}  {row['recommendation']:12}  "
              f"Earnings: {row['earnings_date']}  ({row['days_to_earnings']} days)")
        print(f"         {row['reasoning'][:80]}...")
        print()

    # Step 6: Select diversified positions (2 from each of top 2 sectors)
    print(f"\n{'='*70}")
    print("⚡ SECTOR-DIVERSIFIED POSITION SELECTION ⚡")
    print(f"{'='*70}\n")

    # Group by sector and get top 2 sectors
    sector_counts = df['sector'].value_counts()
    print(f"📊 Sector Distribution:")
    for sector, count in sector_counts.items():
        print(f"   {sector}: {count} candidate(s)")

    selected = []

    # Strategy: 2 from top sector + 2 from second sector = 4 total
    if len(sector_counts) >= 2:
        top_sectors = sector_counts.index[:2]  # Top 2 sectors

        for sector in top_sectors:
            sector_df = df[df['sector'] == sector].head(2)  # Top 2 from this sector
            selected.extend(sector_df.to_dict('records'))
            print(f"\n✅ Selected 2 from {sector}:")
            for idx, row in sector_df.iterrows():
                print(f"   - {row['ticker']:15} (Score: {row['dexter_score']}/100)")

    elif len(sector_counts) == 1:
        # Only 1 sector available, take top 4 from it
        print(f"\n⚠️ Only 1 sector available, selecting top 4 candidates")
        selected = df.head(4).to_dict('records')

    else:
        print(f"\n❌ No candidates available")
        return

    # Step 7: Enter selected positions
    print(f"\n{'='*70}")
    print("⚡ AUTO-ENTERING DIVERSIFIED POSITIONS ⚡")
    print(f"{'='*70}\n")

    entered = 0
    for position in selected:
        if enter_thunder_position(position):
            entered += 1

    print(f"\n✅ Entered {entered} THUNDER positions (Target: 4)")

    return df

if __name__ == "__main__":
    run_thunder_pipeline()
