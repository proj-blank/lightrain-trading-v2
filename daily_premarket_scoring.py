#!/usr/bin/env python3
"""
DAILY Pre-Market Scoring - Run BEFORE market opens (8:45 AM)
Scores all screened stocks using previous day's close prices
This allows instant entry decisions when market opens at 9:35 AM

Note: SWING strategy will have its own swing_premarket_scoring.py with different weights
"""
import sys
sys.path.insert(0, '/home/ubuntu/trading')

from datetime import datetime
from scripts.db_connection import get_db_connection
from scripts.rs_rating import RelativeStrengthAnalyzer
from scripts.signal_generator_daily import generate_signal_daily
import yfinance as yf
import psycopg2.extras

def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}")

# Initialize RS analyzer once (reused for all stocks)
rs_analyzer = RelativeStrengthAnalyzer()

# Minimum RS rating filter (same as daily_trading_pg.py)
MIN_RS_RATING = 60

def score_stock_daily(ticker):
    """
    Score a stock for DAILY strategy using previous day's close data
    Uses the same scoring logic as daily_trading_pg.py:
    1. RS Rating filter (>= 60)
    2. Technical indicators via generate_signal_daily()
    """
    try:
        # Get 6 months of data for indicators
        stock = yf.Ticker(ticker)
        df = stock.history(period='6mo')

        if df.empty or len(df) < 60:
            return None

        # Use latest close (previous day if before market opens)
        current_price = float(df['Close'].iloc[-1])

        # RS Rating filter (pre-filter before expensive calculations)
        rs_rating = rs_analyzer.calculate_rs_rating(ticker, period='6mo')
        if rs_rating < MIN_RS_RATING:
            return None  # Filtered out by RS rating

        # Generate technical signal and score
        signal, score, details = generate_signal_daily(df, min_score=60)

        return {
            'score': score,
            'rs_rating': rs_rating,
            'price': current_price
        }

    except Exception as e:
        log(f"  ❌ {ticker}: {e}")
        return None

def main():
    log("=" * 60)
    log("DAILY PRE-MARKET SCORING - Using Previous Day's Close")
    log("=" * 60)
    
    # Get all stocks from today's screening
    with get_db_connection() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("""
            SELECT ticker, category
            FROM screened_stocks
            WHERE DATE(screen_date) = CURRENT_DATE
            ORDER BY ticker
        """)
        stocks = cur.fetchall()
        cur.close()
    
    if not stocks:
        log("❌ No stocks to score (run stocks_screening.py first)")
        return
    
    log(f"📊 Scoring {len(stocks)} stocks for DAILY strategy...")
    
    scored = 0
    failed = 0
    
    for i, stock in enumerate(stocks, 1):
        ticker = stock['ticker']
        category = stock['category']
        
        if i % 50 == 0:
            log(f"  Progress: {i}/{len(stocks)} ({scored} scored, {failed} failed)")
        
        result = score_stock_daily(ticker)
        
        if result:
            # Update database with score
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE screened_stocks
                    SET score = %s,
                        rs_rating = %s
                    WHERE ticker = %s
                      AND DATE(screen_date) = CURRENT_DATE
                """, (result['score'], result['rs_rating'], ticker))
                conn.commit()
                cur.close()
            scored += 1
        else:
            failed += 1
    
    log("=" * 60)
    log(f"✅ Scoring Complete!")
    log(f"   Scored: {scored}")
    log(f"   Failed: {failed}")
    
    # Show distribution
    with get_db_connection() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("""
            SELECT
                COUNT(CASE WHEN score >= 80 THEN 1 END) as excellent,
                COUNT(CASE WHEN score >= 60 AND score < 80 THEN 1 END) as good,
                COUNT(CASE WHEN score >= 40 AND score < 60 THEN 1 END) as average,
                COUNT(CASE WHEN score < 40 THEN 1 END) as poor
            FROM screened_stocks
            WHERE DATE(screen_date) = CURRENT_DATE
              AND score IS NOT NULL
        """)
        dist = cur.fetchone()
        cur.close()
    
    log(f"   Distribution:")
    log(f"     80+: {dist['excellent']} (Excellent)")
    log(f"     60-79: {dist['good']} (Good - Entry candidates)")
    log(f"     40-59: {dist['average']} (Average)")
    log(f"     <40: {dist['poor']} (Poor)")
    log("=" * 60)

if __name__ == '__main__':
    main()
