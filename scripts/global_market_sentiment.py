#!/usr/bin/env python3
"""
Global Market Sentiment Analyzer
Checks overnight moves in US/Asia to predict India market opening
Run at 8:45 AM IST before market opens
"""
import yfinance as yf
from datetime import datetime, timedelta
from scripts.db_connection import get_db_cursor

def get_global_sentiment():
    """
    Fetch global market data and calculate sentiment
    Returns: dict with sentiment analysis and expected gap
    """

    # Fetch US markets (previous session)
    sp500 = yf.Ticker("^GSPC")
    nasdaq = yf.Ticker("^IXIC")
    vix = yf.Ticker("^VIX")

    # Fetch Asian markets (today's session if available)
    nikkei = yf.Ticker("^N225")
    hangseng = yf.Ticker("^HSI")

    # Fetch SGX Nifty (Singapore Nifty futures - CRITICAL)
    # Note: SGX Nifty symbol might need adjustment based on data provider
    # Alternative: Use NIFTY futures or rely on US/Asia correlation

    # Fetch India VIX
    india_vix = yf.Ticker("^INDIAVIX")
    nifty = yf.Ticker("^NSEI")

    # Get latest data
    sp500_hist = sp500.history(period='5d')
    nasdaq_hist = nasdaq.history(period='5d')
    vix_hist = vix.history(period='5d')
    nikkei_hist = nikkei.history(period='2d')
    hangseng_hist = hangseng.history(period='2d')
    india_vix_hist = india_vix.history(period='2d')
    nifty_hist = nifty.history(period='2d')

    # Calculate changes
    sp500_change = ((sp500_hist['Close'][-1] / sp500_hist['Close'][-2]) - 1) * 100 if len(sp500_hist) >= 2 else 0
    nasdaq_change = ((nasdaq_hist['Close'][-1] / nasdaq_hist['Close'][-2]) - 1) * 100 if len(nasdaq_hist) >= 2 else 0
    vix_change = ((vix_hist['Close'][-1] / vix_hist['Close'][-2]) - 1) * 100 if len(vix_hist) >= 2 else 0
    nikkei_change = ((nikkei_hist['Close'][-1] / nikkei_hist['Close'][-2]) - 1) * 100 if len(nikkei_hist) >= 2 else 0
    hangseng_change = ((hangseng_hist['Close'][-1] / hangseng_hist['Close'][-2]) - 1) * 100 if len(hangseng_hist) >= 2 else 0
    nifty_prev_close = float(nifty_hist['Close'][-1]) if not nifty_hist.empty else 0

    # Determine global sentiment
    # Weight: US 40%, Asia 40%, VIX 20%
    us_score = (sp500_change + nasdaq_change) / 2
    asia_score = (nikkei_change + hangseng_change) / 2
    vix_score = -vix_change  # Inverse: VIX up = bad

    global_score = (us_score * 0.4) + (asia_score * 0.4) + (vix_score * 0.2)

    # Sentiment classification
    if global_score > 0.5:
        sentiment = 'BULLISH'
    elif global_score < -0.5:
        sentiment = 'BEARISH'
    else:
        sentiment = 'NEUTRAL'

    # Expected NIFTY gap (simplified correlation)
    # Historically, NIFTY ~0.6x correlated with S&P500 overnight moves
    expected_gap = (us_score * 0.6) + (asia_score * 0.3)

    # Risk On/Off indicator
    if vix_hist['Close'][-1] > 25 if not vix_hist.empty else False:
        risk_mode = 'RISK_OFF'
    elif vix_hist['Close'][-1] < 15 if not vix_hist.empty else False:
        risk_mode = 'RISK_ON'
    else:
        risk_mode = 'NEUTRAL'

    # Check for divergence
    us_asia_divergence = (us_score > 0.5 and asia_score < -0.5) or (us_score < -0.5 and asia_score > 0.5)

    # Is it Monday? (weekend effect)
    is_monday = datetime.now().weekday() == 0

    return {
        'snapshot_date': datetime.now().date(),
        'snapshot_time': datetime.now().time(),

        # US Data
        'sp500_close': float(sp500_hist['Close'][-1]) if not sp500_hist.empty else None,
        'sp500_change_pct': sp500_change,
        'nasdaq_close': float(nasdaq_hist['Close'][-1]) if not nasdaq_hist.empty else None,
        'nasdaq_change_pct': nasdaq_change,
        'vix_close': float(vix_hist['Close'][-1]) if not vix_hist.empty else None,
        'vix_change_pct': vix_change,

        # Asian Data
        'nikkei_close': float(nikkei_hist['Close'][-1]) if not nikkei_hist.empty else None,
        'nikkei_change_pct': nikkei_change,
        'hang_seng_close': float(hangseng_hist['Close'][-1]) if not hangseng_hist.empty else None,
        'hang_seng_change_pct': hangseng_change,

        # India Data
        'nifty_prev_close': nifty_prev_close,
        'india_vix': float(india_vix_hist['Close'][-1]) if not india_vix_hist.empty else None,

        # Derived
        'global_sentiment': sentiment,
        'overnight_gap_expected': round(expected_gap, 2),
        'us_asia_divergence': us_asia_divergence,
        'risk_on_off': risk_mode,
        'is_monday': is_monday,
        'global_score': round(global_score, 2)
    }

def save_global_sentiment(data):
    """Save global sentiment snapshot to database"""
    with get_db_cursor() as cur:
        cur.execute("""
            INSERT INTO global_market_indicators (
                snapshot_date, snapshot_time,
                sp500_close, sp500_change_pct,
                nasdaq_close, nasdaq_change_pct,
                vix_close, vix_change_pct,
                nikkei_close, nikkei_change_pct,
                hang_seng_close, hang_seng_change_pct,
                nifty_prev_close, india_vix,
                global_sentiment, overnight_gap_expected,
                us_asia_divergence, risk_on_off, is_monday
            ) VALUES (
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s, %s
            )
            ON CONFLICT (snapshot_date, snapshot_time) DO NOTHING
        """, (
            data['snapshot_date'], data['snapshot_time'],
            data['sp500_close'], data['sp500_change_pct'],
            data['nasdaq_close'], data['nasdaq_change_pct'],
            data['vix_close'], data['vix_change_pct'],
            data['nikkei_close'], data['nikkei_change_pct'],
            data['hang_seng_close'], data['hang_seng_change_pct'],
            data['nifty_prev_close'], data['india_vix'],
            data['global_sentiment'], data['overnight_gap_expected'],
            data['us_asia_divergence'], data['risk_on_off'], data['is_monday']
        ))

def get_latest_global_sentiment():
    """Retrieve latest global sentiment from database"""
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT * FROM global_market_indicators
            WHERE snapshot_date = CURRENT_DATE
            ORDER BY snapshot_time DESC
            LIMIT 1
        """)
        result = cur.fetchone()
        return dict(result) if result else None

def should_adjust_strategy():
    """
    Determine if strategy should be adjusted based on global cues

    Returns:
        dict: {
            'action': 'BOOST', 'REDUCE', 'NORMAL',
            'reason': str,
            'position_adjustment': float (multiplier)
        }
    """
    sentiment = get_latest_global_sentiment()

    if not sentiment:
        # No data, run normal
        return {'action': 'NORMAL', 'reason': 'No global data', 'position_adjustment': 1.0}

    gap = sentiment.get('overnight_gap_expected', 0)
    global_sent = sentiment.get('global_sentiment', 'NEUTRAL')
    risk_mode = sentiment.get('risk_on_off', 'NEUTRAL')

    # Strong bullish overnight move
    if gap > 1.0 and global_sent == 'BULLISH' and risk_mode == 'RISK_ON':
        return {
            'action': 'BOOST',
            'reason': f'Strong global rally (+{gap:.1f}% expected gap)',
            'position_adjustment': 1.3  # Increase position sizes by 30%
        }

    # Moderate bullish
    elif gap > 0.5 and global_sent == 'BULLISH':
        return {
            'action': 'BOOST',
            'reason': f'Positive global sentiment (+{gap:.1f}% expected gap)',
            'position_adjustment': 1.15  # Increase by 15%
        }

    # Strong bearish overnight move
    elif gap < -1.0 and global_sent == 'BEARISH':
        return {
            'action': 'REDUCE',
            'reason': f'Weak global markets ({gap:.1f}% expected gap)',
            'position_adjustment': 0.5  # Reduce position sizes by 50%
        }

    # Moderate bearish
    elif gap < -0.5 and global_sent == 'BEARISH':
        return {
            'action': 'REDUCE',
            'reason': f'Cautious global sentiment ({gap:.1f}% expected gap)',
            'position_adjustment': 0.7  # Reduce by 30%
        }

    # Risk-off environment
    elif risk_mode == 'RISK_OFF':
        return {
            'action': 'REDUCE',
            'reason': 'Risk-off environment (high VIX)',
            'position_adjustment': 0.6
        }

    else:
        return {
            'action': 'NORMAL',
            'reason': 'Neutral global conditions',
            'position_adjustment': 1.0
        }

if __name__ == "__main__":
    # Test
    print("Fetching global market sentiment...")
    data = get_global_sentiment()
    print(f"\nGlobal Sentiment: {data['global_sentiment']}")
    print(f"Expected NIFTY Gap: {data['overnight_gap_expected']:.2f}%")
    print(f"Risk Mode: {data['risk_on_off']}")
    print(f"US: S&P {data['sp500_change_pct']:+.2f}%, Nasdaq {data['nasdaq_change_pct']:+.2f}%")
    print(f"Asia: Nikkei {data['nikkei_change_pct']:+.2f}%, Hang Seng {data['hang_seng_change_pct']:+.2f}%")

    adjustment = should_adjust_strategy()
    print(f"\nStrategy Adjustment: {adjustment['action']}")
    print(f"Reason: {adjustment['reason']}")
    print(f"Position Multiplier: {adjustment['position_adjustment']:.2f}x")
