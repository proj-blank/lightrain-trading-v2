#!/usr/bin/env python3
"""
Script to enter the 5 micro-cap positions that failed today due to category constraint.
"""
import sys
sys.path.insert(0, '/home/ubuntu/trading')

from scripts.database import add_position, get_active_positions, log_trade
from scripts.telegram_bot import send_telegram_message
import yfinance as yf
from datetime import datetime
import pandas as pd

# The 5 positions that failed today (all had excellent scores!)
FAILED_POSITIONS = [
    {'ticker': 'NATIONALUM.NS', 'score': 79.59, 'rs_rating': 100, 'capital': 20000},
    {'ticker': 'SAIL.NS', 'score': 74.13, 'rs_rating': 100, 'capital': 20000},
    {'ticker': 'AARTIDRUGS.NS', 'score': 71.5, 'rs_rating': 90, 'capital': 20000},
    {'ticker': 'GRSE.NS', 'score': 71.5, 'rs_rating': 100, 'capital': 20000},
    {'ticker': 'KAJARIACER.NS', 'score': 70.42, 'rs_rating': 70, 'capital': 20000},
]

STRATEGY = 'DAILY'

# Check which ones are already in database
existing_positions = get_active_positions(STRATEGY)
existing_tickers = [p['ticker'] for p in existing_positions]

print(f"📊 Existing {STRATEGY} positions: {len(existing_tickers)}")
print(f"   {existing_tickers}")

entered_count = 0
skipped_count = 0

for pos in FAILED_POSITIONS:
    ticker = pos['ticker']
    
    if ticker in existing_tickers:
        print(f"⏭️  Skipping {ticker} (already exists)")
        skipped_count += 1
        continue
    
    print(f"\n📈 Processing {ticker}...")
    
    # Download current price
    try:
        df = yf.download(ticker, period='5d', interval='1d', progress=False)
        if df.empty:
            print(f"   ❌ No data for {ticker}")
            continue
        
        price = float(df['Close'].iloc[-1])
        qty = int(pos['capital'] // price)
        
        if qty == 0:
            print(f"   ⚠️  Quantity is 0, skipping")
            continue
        
        # Calculate ATR for stops
        df['tr'] = pd.concat([
            df['High'] - df['Low'],
            abs(df['High'] - df['Close'].shift()),
            abs(df['Low'] - df['Close'].shift())
        ], axis=1).max(axis=1)
        atr = df['tr'].rolling(14).mean().iloc[-1]
        
        stop_loss = price - (2 * atr) if pd.notna(atr) and atr > 0 else price * 0.98
        take_profit = price + (3 * atr) if pd.notna(atr) and atr > 0 else price * 1.04
        
        # Add to database with correct category name
        add_position(
            ticker=ticker,
            strategy=STRATEGY,
            entry_price=price,
            quantity=qty,
            stop_loss=stop_loss,
            take_profit=take_profit,
            category='Microcap',  # Fixed category name!
            entry_date=datetime.now().strftime('%Y-%m-%d')
        )
        
        # Log trade
        log_trade(
            ticker=ticker,
            strategy=STRATEGY,
            signal='BUY',
            price=price,
            quantity=qty,
            pnl=0,
            notes=f"Manual entry - Score: {pos['score']:.1f} | RS: {pos['rs_rating']}"
        )
        
        print(f"   ✅ ENTERED {ticker} @ ₹{price:.2f} | Qty: {qty} | Microcap")
        
        # Send Telegram
        msg = f"✅ MANUAL ENTRY ({STRATEGY})\n"
        msg += f"{ticker} @ ₹{price:.2f}\n"
        msg += f"Qty: {qty} | Capital: ₹{pos['capital']:,}\n"
        msg += f"Score: {pos['score']:.1f} | RS: {pos['rs_rating']}\n"
        msg += f"SL: ₹{stop_loss:.2f} | TP: ₹{take_profit:.2f}"
        send_telegram_message(msg)
        
        entered_count += 1
        
    except Exception as e:
        print(f"   ❌ Failed: {e}")

print(f"\n" + "="*60)
print(f"Summary: {entered_count} entered, {skipped_count} skipped")
print("="*60)
