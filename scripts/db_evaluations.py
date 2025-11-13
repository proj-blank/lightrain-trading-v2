#!/usr/bin/env python3
"""
Database operations for stock evaluations table
Tracks all decision factors for each stock analyzed
"""
from scripts.db_connection import get_db_cursor

def log_stock_evaluation(
    ticker, strategy, current_price, signal, decision_reason,
    technical_score=None, rs_rating=None, sentiment_score=None,
    market_regime=None, nifty_trend=None, vix_level=None,
    was_executed=False, recommended_quantity=None, recommended_allocation=None,
    sentiment_boost=None, category=None, **kwargs
):
    """
    Log a stock evaluation with all decision factors

    Args:
        ticker: Stock ticker
        strategy: 'DAILY' or 'SWING'
        current_price: Current stock price
        signal: 'BUY', 'SKIP', 'HOLD'
        decision_reason: Why this decision was made
        technical_score: Combined indicator score
        rs_rating: Relative strength rating
        sentiment_score: -1 to +1
        market_regime: NORMAL, HIGH_VOL, BEAR
        was_executed: Whether trade was executed
        **kwargs: Additional fields (rsi, macd, volume, etc.)
    """
    with get_db_cursor() as cur:
        cur.execute("""
            INSERT INTO stock_evaluations (
                evaluation_date, ticker, strategy, current_price,
                rsi_14, macd, macd_signal, bb_position, atr,
                rs_rating, rs_3m, rs_6m, rs_12m,
                technical_score, sentiment_score, final_score,
                market_regime, nifty_trend, vix_level, nifty_5d_change,
                has_negative_news, has_positive_news, news_summary,
                signal, decision_reason, was_executed,
                recommended_quantity, recommended_allocation, sentiment_boost_applied,
                category, volume, avg_volume_20d
            ) VALUES (
                CURRENT_DATE, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s
            )
            ON CONFLICT (evaluation_date, ticker, strategy)
            DO UPDATE SET
                current_price = EXCLUDED.current_price,
                technical_score = EXCLUDED.technical_score,
                rs_rating = EXCLUDED.rs_rating,
                sentiment_score = EXCLUDED.sentiment_score,
                signal = EXCLUDED.signal,
                decision_reason = EXCLUDED.decision_reason,
                was_executed = EXCLUDED.was_executed,
                recommended_quantity = EXCLUDED.recommended_quantity,
                recommended_allocation = EXCLUDED.recommended_allocation
        """, (
            ticker, strategy, float(current_price),
            kwargs.get('rsi'), kwargs.get('macd'), kwargs.get('macd_signal'),
            kwargs.get('bb_position'), kwargs.get('atr'),
            rs_rating, kwargs.get('rs_3m'), kwargs.get('rs_6m'), kwargs.get('rs_12m'),
            technical_score, sentiment_score, kwargs.get('final_score', technical_score),
            market_regime, nifty_trend, vix_level, kwargs.get('nifty_5d_change'),
            kwargs.get('has_negative_news', False),
            kwargs.get('has_positive_news', False),
            kwargs.get('news_summary'),
            signal, decision_reason, was_executed,
            recommended_quantity, recommended_allocation, sentiment_boost,
            category, kwargs.get('volume'), kwargs.get('avg_volume_20d')
        ))

def get_todays_evaluations(strategy=None):
    """Get all stock evaluations from today"""
    with get_db_cursor() as cur:
        if strategy:
            cur.execute("""
                SELECT * FROM stock_evaluations
                WHERE evaluation_date = CURRENT_DATE AND strategy = %s
                ORDER BY final_score DESC
            """, (strategy,))
        else:
            cur.execute("""
                SELECT * FROM stock_evaluations
                WHERE evaluation_date = CURRENT_DATE
                ORDER BY final_score DESC
            """)
        return cur.fetchall()

def get_evaluation_stats(days=30):
    """Get evaluation statistics for last N days"""
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT
                strategy,
                COUNT(*) as total_evaluated,
                SUM(CASE WHEN signal = 'BUY' THEN 1 ELSE 0 END) as buy_signals,
                SUM(CASE WHEN was_executed THEN 1 ELSE 0 END) as executed,
                AVG(technical_score) as avg_tech_score,
                AVG(sentiment_score) as avg_sentiment,
                AVG(rs_rating) as avg_rs
            FROM stock_evaluations
            WHERE evaluation_date >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY strategy
        """, (days,))
        return cur.fetchall()
