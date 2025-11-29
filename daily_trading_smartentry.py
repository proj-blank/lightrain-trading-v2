#!/usr/bin/env python3
import sys, time
from datetime import datetime, date
sys.path.insert(0, '/home/ubuntu/trading')

from scripts.smart_entry_validator import validate_nifty_at_open, analyze_nifty_strength_930, analyze_opening_candle, calculate_limit_price
from scripts.db_connection import get_db_cursor, get_available_cash, get_db_connection
from scripts.telegram_bot import send_telegram_message

STRATEGY = 'DAILY'

def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}")

def load_screened_stocks():
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT ticker, score, category, rs_rating
            FROM screened_stocks
            WHERE last_updated = CURRENT_DATE
            ORDER BY score DESC NULLS LAST
        """)
        return cur.fetchall()

def wait_until(time_str):
    target = datetime.strptime(time_str, '%H:%M').time()
    while datetime.now().time() < target:
        time.sleep(10)

log("="*60)
log("PAPER TRADING: DAILY Strategy")
log("="*60)

available_cap = get_available_cash(STRATEGY)
log(f"Available Capital: Rs {available_cap:,.0f}")

if available_cap < 50000:
    log("Insufficient capital, exiting")
    sys.exit(0)

wait_until("09:15")

log("\n9:15 AM - Nifty Validation")
status, regime, multiplier, reason, nifty_data = validate_nifty_at_open()
log(f"Status: {status} | Regime: {regime} | Mult: {multiplier*100}%")
log(f"Gap: {nifty_data.get('gap',0):+.2f}% | Move: {nifty_data.get('move',0):+.2f}%")

send_telegram_message(
    f"📄 PAPER DAILY 9:15\n{status} | {regime}\n"
    f"Gap: {nifty_data.get('gap',0):+.2f}%\nSizing: {multiplier*100}%"
)

if status == 'ABORT':
    log("ABORT")
    sys.exit(0)

wait_until("09:30")

log("\n9:30 AM - Candle Analysis")
strength, slice_pct, notes, candle = analyze_nifty_strength_930()
log(f"Pattern: {candle.get('pattern','N/A')} | Slice: {slice_pct*100}%")

send_telegram_message(
    f"📄 PAPER DAILY 9:30\n{candle.get('pattern','N/A')}\n"
    f"Deploy: {slice_pct*100}%"
)

if slice_pct == 0:
    log("SKIP")
    sys.exit(0)

wait_until("09:32")

log("\n9:32 AM - Deployment")
candidates = load_screened_stocks()
final_mult = multiplier * slice_pct
num_deploy = int(len(candidates) * slice_pct)

log(f"Deploy {num_deploy}/{len(candidates)} @ {final_mult*100}%")

entered = 0
skipped = 0

with get_db_connection() as conn:
    cur = conn.cursor()
    
    for cand in candidates[:num_deploy]:
        ticker = cand['ticker']
        pattern, strength, supp, res, sent, cdata = analyze_opening_candle(ticker)
        
        if pattern is None:
            skipped += 1
            continue
        
        limit, reason_txt, pdata = calculate_limit_price(ticker, cdata, pattern)
        
        would_enter = limit > 0
        
        cur.execute("""
            INSERT INTO paper_trades (
                trade_date, strategy, ticker,
                nifty_gap_pct, nifty_move_pct, regime_915, position_multiplier,
                nifty_pattern, nifty_strength, slice_pct,
                stock_pattern, stock_strength, current_price, limit_price,
                would_enter, reason
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            date.today(), STRATEGY, ticker,
            nifty_data.get('gap',0), nifty_data.get('move',0), regime, multiplier,
            candle.get('pattern'), candle.get('strength',0), slice_pct,
            pattern, strength, pdata['current'], limit,
            would_enter, reason_txt
        ))
        
        if would_enter:
            entered += 1
            log(f"  ✅ {ticker}: {pattern} @ Rs {limit:.2f}")
        else:
            skipped += 1
            log(f"  ❌ {ticker}: Skip")
    
    conn.commit()

log(f"\nWould enter: {entered} | Skip: {skipped}")

send_telegram_message(
    f"📄 PAPER DAILY Complete\n\n"
    f"Would enter: {entered}\nSkipped: {skipped}\n"
    f"Final sizing: {final_mult*100}%"
)
