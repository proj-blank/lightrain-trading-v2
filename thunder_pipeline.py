#!/usr/bin/env python3
"""
THUNDER Strategy Pipeline - v2 with Phase 1 Improvements + Enhanced Telegram Reporting

UNIVERSE: Uses screened_stocks (Large-cap + Mid-cap) for quality/liquidity
Earnings-based fundamental strategy needs reliable earnings data and analyst coverage
"""
import sys
sys.path.insert(0, '/home/ubuntu/trading')

from datetime import datetime, date, timedelta
from earnings_calendar import update_earnings_calendar, get_earnings_in_target_window
from thunder_dexter_analyzer import analyze_thunder_candidate
from thunder_entry import enter_thunder_position, MIN_DEXTER_SCORE, MIN_DAYS_TO_EARNINGS, MAX_DAYS_TO_EARNINGS, MAX_POSITIONS
from scripts.db_connection import get_db_cursor
from scripts.telegram_bot import send_telegram_message
import pandas as pd
import yfinance as yf
import pytz


def is_market_open():
    """Check if Indian stock market (NSE) is currently open"""

    # Check market hours (9:15 AM - 3:30 PM IST)
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    hour, minute = now.hour, now.minute

    # Time check
    market_hours_open = (hour == 9 and minute >= 15) or (9 < hour < 15) or (hour == 15 and minute <= 30)

    if not market_hours_open:
        return False, f"Outside market hours: {now.strftime('%I:%M %p IST')} (Market: 9:15 AM - 3:30 PM)"

    # Holiday check
    try:
        nifty = yf.Ticker("^NSEI")
        hist = nifty.history(period="2d")

        if hist.empty:
            return False, "No market data available (likely holiday)"

        today_str = now.strftime('%Y-%m-%d')
        dates_in_data = hist.index.strftime('%Y-%m-%d').tolist()

        if today_str not in dates_in_data:
            last_day = dates_in_data[-1] if dates_in_data else 'unknown'
            return False, f"Market holiday detected (last trading day: {last_day})"

        return True, f"Market open - {now.strftime('%I:%M %p IST')}"

    except Exception as e:
        print(f"⚠️ Warning: Could not verify holiday status ({e}). Proceeding with caution.")
        return True, f"Market hours OK (holiday check failed)"


# Exit logic moved to thunder_exit.py - keeping for reference
# def check_and_exit_positions():
    """Check ACTIVE positions for exit conditions:
    
    BEFORE EARNINGS:
    - Stop loss: -10%
    
    AFTER EARNINGS:
    - Stop loss: -5%
    - OR max hold: 10 days after earnings date
    
    ALWAYS:
    - Take profit: +5%
    """
    print("\n" + "="*70)
    print("💰 CHECKING ACTIVE POSITIONS FOR EXIT CONDITIONS")
    print("="*70)

    TAKE_PROFIT_PCT = 5.0
    SL_BEFORE_EARNINGS = -10.0
    SL_AFTER_EARNINGS = -5.0
    MAX_DAYS_AFTER_EARNINGS = 10

    try:
        with get_db_cursor() as cur:
            # Join with earnings_calendar to get earnings_date
            cur.execute("""
                SELECT p.ticker, p.entry_date, p.entry_price, p.quantity,
                       ec.earnings_date
                FROM positions p
                LEFT JOIN earnings_calendar ec ON p.ticker = ec.ticker
                WHERE p.status = 'HOLD' AND p.strategy = 'THUNDER'
                ORDER BY p.entry_date DESC
            """)
            positions = cur.fetchall()

            if not positions:
                print("✅ No active positions to check\n")
                return 0

            print(f"📊 Found {len(positions)} active position(s)\n")

            exited = 0
            holding_positions = []  # Track positions still held for telegram summary
            
            for pos in positions:
                ticker = pos['ticker']
                entry_price = float(pos['entry_price'])
                quantity = int(pos['quantity'])
                entry_date = pos['entry_date']
                earnings_date = pos['earnings_date']

                try:
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period='1d')
                    if hist.empty:
                        print(f"⚠️ {ticker}: Could not fetch price, skipping")
                        continue

                    current_price = float(hist['Close'].iloc[-1])
                    pnl = (current_price - entry_price) * quantity
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100

                    # Parse earnings date
                    if earnings_date:
                        if isinstance(earnings_date, str):
                            earnings_date = datetime.strptime(earnings_date, '%Y-%m-%d').date()
                    
                    # Determine if earnings has passed
                    earnings_passed = earnings_date and date.today() > earnings_date
                    days_since_earnings = (date.today() - earnings_date).days if earnings_passed else None
                    days_to_earnings = (earnings_date - date.today()).days if earnings_date and not earnings_passed else None

                    # Display status
                    print(f"📊 {ticker}: Entry ₹{entry_price:.2f} → Current ₹{current_price:.2f} ({pnl_pct:+.2f}%)")
                    if earnings_date:
                        if earnings_passed:
                            print(f"   Earnings: {earnings_date} (PASSED - {days_since_earnings} days ago)")
                            print(f"   Rules: SL={SL_AFTER_EARNINGS}% or MaxHold={MAX_DAYS_AFTER_EARNINGS}d")
                        else:
                            print(f"   Earnings: {earnings_date} ({days_to_earnings} days away)")
                            print(f"   Rules: SL={SL_BEFORE_EARNINGS}% (pre-earnings)")

                    exit_reason = None

                    # 1. Take profit (always applies)
                    if pnl_pct >= TAKE_PROFIT_PCT:
                        exit_reason = f"Profit target hit ({pnl_pct:.1f}% >= {TAKE_PROFIT_PCT}%)"

                    # 2. Check stop loss based on earnings status
                    elif earnings_passed:
                        # AFTER EARNINGS: tighter stop loss or max hold
                        if pnl_pct <= SL_AFTER_EARNINGS:
                            exit_reason = f"Post-earnings stop loss ({pnl_pct:.1f}% <= {SL_AFTER_EARNINGS}%)"
                        elif days_since_earnings >= MAX_DAYS_AFTER_EARNINGS:
                            exit_reason = f"Max hold exceeded ({days_since_earnings} days after earnings)"
                    else:
                        # BEFORE EARNINGS: wider stop loss
                        if pnl_pct <= SL_BEFORE_EARNINGS:
                            exit_reason = f"Pre-earnings stop loss ({pnl_pct:.1f}% <= {SL_BEFORE_EARNINGS}%)"

                    if exit_reason:
                        print(f"   ✅ EXIT TRIGGERED: {exit_reason}")

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

                        emoji = "📈" if pnl > 0 else "📉"
                        earnings_status = "PASSED" if earnings_passed else f"{days_to_earnings}d away"
                        send_telegram_message(f"""⚡ <b>THUNDER POSITION CLOSED</b>

{emoji} <b>{ticker}</b>
💰 Entry: ₹{entry_price:.2f} → Exit: ₹{current_price:.2f}
📦 Quantity: {quantity} shares
💵 PnL: ₹{pnl:,.0f} ({pnl_pct:+.2f}%)

📅 Entry: {entry_date}
📅 Exit: {date.today()}
📅 Earnings: {earnings_date} ({earnings_status})

💭 <b>Reason:</b> {exit_reason}
""", parse_mode='HTML')

                        print(f"   📱 Telegram alert sent")
                        print(f"   ✅ Position closed! PnL: ₹{pnl:,.0f}\n")
                        exited += 1
                    else:
                        print(f"   ⏰ Holding - no exit condition met\n")
                        # Track for summary
                        holding_positions.append({
                            'ticker': ticker,
                            'pnl_pct': pnl_pct,
                            'days_to_earnings': days_to_earnings,
                            'days_since_earnings': days_since_earnings,
                            'earnings_passed': earnings_passed,
                            'earnings_date': earnings_date
                        })

                except Exception as e:
                    print(f"⚠️ {ticker}: Error checking position: {e}\n")
                    continue

            if exited > 0:
                print(f"✅ Exited {exited} position(s)\n")
            else:
                print(f"ℹ️ No positions met exit conditions\n")

            # Send telegram summary of open positions
            if holding_positions:
                pos_lines = []
                for hp in holding_positions:
                    emoji = "📈" if hp['pnl_pct'] > 0 else "📉" if hp['pnl_pct'] < 0 else "➡️"
                    if hp['earnings_passed']:
                        earnings_info = f"{hp['days_since_earnings']}d after earnings"
                    else:
                        earnings_info = f"{hp['days_to_earnings']}d to earnings"
                    pos_lines.append(f"{emoji} <b>{hp['ticker']}</b>: {hp['pnl_pct']:+.1f}% | {earnings_info}")
                
                send_telegram_message(f"""⚡ <b>THUNDER POSITIONS STATUS</b>

📊 <b>Open Positions: {len(holding_positions)}</b>

{chr(10).join(pos_lines)}

<i>Exit rules:</i>
• Pre-earnings: SL {SL_BEFORE_EARNINGS}%
• Post-earnings: SL {SL_AFTER_EARNINGS}% or {MAX_DAYS_AFTER_EARNINGS}d max hold
• Always: TP +{TAKE_PROFIT_PCT}%
""", parse_mode='HTML')

            return exited

    except Exception as e:
        print(f"❌ Error checking positions: {e}\n")
        import traceback
        traceback.print_exc()
        return 0

def run_thunder_pipeline():
    """Complete THUNDER strategy pipeline"""

    print("⚡" * 35)
    print("⚡ THUNDER STRATEGY PIPELINE v2 ⚡")
    print("⚡" * 35)

    is_open, reason = is_market_open()

    if is_open:
        print(f"✅ {reason}")
    else:
        print(f"❌ Market Closed - {reason}")
        print("⚠️ Will only check for exits, skipping new entries")

    # Exit logic moved to thunder_exit.py (runs at 11 AM)

    if not is_open:
        print("\n❌ Skipping new entries - market closed")
        return

    # Load QUALITY universe: Large-cap + Mid-cap from screened_stocks
    print(f"\n📊 Loading THUNDER universe (ALL screened stocks (Dexter will filter quality))...")

    try:
        with get_db_cursor() as cur:
            # Get all screened stocks from morning run (last 7 days)
            cur.execute("""
                SELECT ticker, category
                FROM screened_stocks
                WHERE 1=1
                  AND last_updated >= CURRENT_DATE - INTERVAL '7 days'
                ORDER BY category, ticker
            """)
            results = cur.fetchall()

            if not results:
                error_msg = "❌ No screened stocks in screened_stocks. Run stocks_screening.py first."
                print(error_msg)
                send_telegram_message(error_msg)
                return

            universe = [row['ticker'] for row in results]
            large_cap_count = sum(1 for r in results if r['category'] == 'Large-cap')
            mid_cap_count = sum(1 for r in results if r['category'] == 'Mid-cap')

            print(f"✅ Loaded {len(universe)} quality stocks:")
            print(f"   Large-cap: {large_cap_count} stocks")
            print(f"   Mid-cap: {mid_cap_count} stocks")

            # Send initial scan telegram message
            send_telegram_message(f"""⚡ <b>THUNDER SCAN STARTED</b>

📊 <b>Universe:</b> {len(universe)} stocks
   • Large-cap: {large_cap_count}
   • Mid-cap: {mid_cap_count}

⏳ Scanning for earnings opportunities...
""", parse_mode='HTML')

    except Exception as e:
        error_msg = f"❌ Error loading universe: {e}"
        print(error_msg)
        send_telegram_message(error_msg)
        return

    print(f"\n📅 Updating earnings calendar for {len(universe)} stocks...")
    update_earnings_calendar(universe)

    print(f"\n🎯 Finding earnings in {MIN_DAYS_TO_EARNINGS}-{MAX_DAYS_TO_EARNINGS} day window...")
    opportunities = get_earnings_in_target_window(min_days=MIN_DAYS_TO_EARNINGS, max_days=MAX_DAYS_TO_EARNINGS)

    if opportunities.empty:
        msg = f"""⚡ <b>THUNDER SCAN COMPLETE</b>

❌ <b>No Opportunities Found</b>

Scanned {len(universe)} stocks
No earnings in {MIN_DAYS_TO_EARNINGS}-{MAX_DAYS_TO_EARNINGS} day window

<i>Check back tomorrow for new opportunities</i>
"""
        print("\n❌ No earnings in target window")
        send_telegram_message(msg, parse_mode='HTML')
        return

    print(f"\n✅ Found {len(opportunities)} earnings opportunities")

    # Send earnings window results
    earnings_tickers = opportunities['ticker'].tolist()
    send_telegram_message(f"""⚡ <b>THUNDER - Earnings Window Filter</b>

✅ Found {len(opportunities)} stocks with earnings in {MIN_DAYS_TO_EARNINGS}-{MAX_DAYS_TO_EARNINGS} days:

{', '.join(earnings_tickers[:10])}{'...' if len(earnings_tickers) > 10 else ''}

⏳ Running Dexter analysis on candidates...
""", parse_mode='HTML')

    # Run Dexter analysis
    results = []
    failed_analyses = []

    for _, opp in opportunities.iterrows():
        ticker = opp['ticker']
        earnings_date = opp['earnings_date']

        print(f"\n{'='*70}")
        print(f"Analyzing: {ticker}")

        analysis = analyze_thunder_candidate(ticker, earnings_date)
        if analysis:
            results.append(analysis)
        else:
            failed_analyses.append(ticker)

    if not results:
        msg = f"""⚡ <b>THUNDER SCAN COMPLETE</b>

📊 Scanned: {len(universe)} stocks
📅 Earnings window: {len(opportunities)} candidates
❌ Dexter analysis: 0 passed

<b>All candidates failed analysis</b>
Failed: {', '.join(failed_analyses[:5])}{'...' if len(failed_analyses) > 5 else ''}

<i>No positions entered today</i>
"""
        print("\n❌ No successful analyses")
        send_telegram_message(msg, parse_mode='HTML')
        return

    df = pd.DataFrame(results)
    df = df.sort_values('dexter_score', ascending=False)

    print(f"\n{'='*70}")
    print("⚡ TOP THUNDER CANDIDATES (v2 Scoring) ⚡")
    print(f"{'='*70}\n")

    # Show top candidates
    top_candidates_msg = ""
    for i, row in df.head(5).iterrows():
        accel = "✅" if row.get('is_accelerating') else "❌"
        print(f"{row['dexter_score']}/100  {row['ticker']:15}  {row['recommendation']:12}  "
              f"Accel:{accel}  Earnings: {row['earnings_date']}  ({row['days_to_earnings']} days)")
        print(f"         {row['reasoning'][:80]}...")
        print()

        top_candidates_msg += f"\n{row['ticker']:10} | Score: {row['dexter_score']}/100 | {row['recommendation']} | Accel:{accel}"

    # Send Dexter results summary
    send_telegram_message(f"""⚡ <b>THUNDER - Dexter Analysis Results</b>

✅ <b>Passed Analysis: {len(results)}/{len(opportunities)}</b>

<b>Top 5 Candidates:</b>{top_candidates_msg}

⏳ Attempting position entries...
""", parse_mode='HTML')

    # Get current positions count
    active_count = 0
    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM positions WHERE status='HOLD' AND strategy='THUNDER'")
            active_count = cur.fetchone()['cnt']
    except:
        pass

    # Select and enter positions
    print(f"\n{'='*70}")
    print("⚡ POSITION SELECTION ⚡")
    print(f"{'='*70}\n")
    print(f"Current THUNDER positions: {active_count}/{MAX_POSITIONS}")

    entered = 0
    rejected = []

    # Simple approach: Take top 4 candidates that pass all filters
    for _, row in df.head(10).iterrows():  # Check top 10
        if entered >= 4:  # Target 4 positions
            break

        ticker = row['ticker']
        score = row['dexter_score']

        if enter_thunder_position(row.to_dict()):
            entered += 1
        else:
            rejected.append({'ticker': ticker, 'score': score})

    # Final summary telegram message
    summary_msg = f"""⚡ <b>THUNDER SCAN COMPLETE</b>

📊 <b>Scan Results:</b>
   • Total universe: {len(universe)} stocks
   • Earnings window: {len(opportunities)} candidates
   • Dexter passed: {len(results)} stocks

💼 <b>Position Entry:</b>
   • Entered: {entered} positions
   • Rejected: {len(rejected)} (filters/limits)
   • Active positions: {active_count + entered}/{MAX_POSITIONS}
"""

    if rejected:
        summary_msg += "\n<b>Rejected candidates:</b>\n"
        for r in rejected[:5]:
            summary_msg += f"   • {r['ticker']} (Score: {r['score']})\n"

    if entered == 0:
        summary_msg += "\n<i>Possible reasons:</i>\n"
        summary_msg += f"   • Max positions reached ({MAX_POSITIONS})\n"
        summary_msg += f"   • Scores below {MIN_DEXTER_SCORE}\n"
        summary_msg += f"   • Outside {MIN_DAYS_TO_EARNINGS}-{MAX_DAYS_TO_EARNINGS} day window\n"
        summary_msg += "   • Weak sector performance\n"
        summary_msg += "   • Insufficient capital\n"

    send_telegram_message(summary_msg, parse_mode='HTML')

    print(f"\n✅ Entered {entered} THUNDER positions")
    return df

if __name__ == "__main__":
    run_thunder_pipeline()
