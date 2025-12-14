#!/usr/bin/env python3
"""
THUNDER Position Entry
Quality-based position sizing and entry execution
"""
import sys
sys.path.insert(0, '/home/ubuntu/trading')

from datetime import datetime
import yfinance as yf
from scripts.db_connection import get_db_cursor
from scripts.telegram_bot import send_telegram_message

# THUNDER Strategy Parameters
THUNDER_CAPITAL = 500000  # ₹5L allocated
MAX_POSITIONS = 6
MIN_DEXTER_SCORE = 75
MIN_POSITION_SIZE = 50000  # ₹50K minimum
MAX_POSITION_SIZE = 120000  # ₹120K maximum
MAX_SECTOR_ALLOCATION_PCT = 50  # Max 50% of capital per sector

def calculate_position_size(dexter_score, confidence, available_capital):
    """
    Calculate position size based on quality

    Higher score = larger position
    """
    # Base allocation
    base_size = available_capital / (MAX_POSITIONS - get_active_position_count())

    # Quality multiplier (75-100 score → 0.8-1.2x)
    score_multiplier = 0.8 + ((dexter_score - 75) / 100)

    # Confidence multiplier
    conf_multiplier = {'HIGH': 1.2, 'MEDIUM': 1.0, 'LOW': 0.8}.get(confidence, 1.0)

    # Final size
    position_size = base_size * score_multiplier * conf_multiplier

    # Clamp to limits
    return max(MIN_POSITION_SIZE, min(MAX_POSITION_SIZE, position_size))

def get_active_position_count():
    """Get current active THUNDER positions"""
    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM positions WHERE status='HOLD' AND strategy='THUNDER'")
            return cur.fetchone()['cnt']
    except:
        return 0

def get_available_capital():
    """Get available THUNDER capital"""
    try:
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT COALESCE(SUM(entry_price * quantity), 0) as invested
                FROM positions WHERE status='HOLD' AND strategy='THUNDER'
            """)
            invested = float(cur.fetchone()['invested'] or 0)
            return THUNDER_CAPITAL - invested
    except:
        return THUNDER_CAPITAL

def enter_thunder_position(analysis):
    """
    Enter THUNDER position based on Dexter analysis

    Args:
        analysis: Dict from thunder_dexter_analyzer
    """
    ticker = analysis['ticker']
    dexter_score = analysis['dexter_score']
    recommendation = analysis['recommendation']
    confidence = analysis['confidence']

    print(f"\n⚡ THUNDER ENTRY: {ticker}")
    print(f"   Score: {dexter_score}/100 | {recommendation} ({confidence})")

    # Check if should enter
    if dexter_score < MIN_DEXTER_SCORE:
        print(f"   ❌ Score too low (min {MIN_DEXTER_SCORE})")
        return False

    if recommendation not in ['BUY', 'STRONG_BUY']:
        print(f"   ❌ Not a BUY recommendation")
        return False

    # Check capacity
    active_count = get_active_position_count()
    if active_count >= MAX_POSITIONS:
        print(f"   ❌ Max positions reached ({MAX_POSITIONS})")
        return False

    # Get capital
    available = get_available_capital()
    if available < MIN_POSITION_SIZE:
        print(f"   ❌ Insufficient capital (₹{available:,.0f})")
        return False

    # Calculate position size
    position_value = calculate_position_size(dexter_score, confidence, available)

    # Get current price
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='1d')
        if hist.empty:
            print(f"   ❌ Cannot fetch price")
            return False

        entry_price = float(hist['Close'].iloc[-1])
        quantity = int(position_value / entry_price)
        actual_value = quantity * entry_price

        print(f"   💰 Entry: ₹{entry_price:.2f} × {quantity} = ₹{actual_value:,.0f}")

        # Save to positions table (same as DAILY/SWING strategies)
        with get_db_cursor() as cur:
            # Insert into positions table - THUNDER uses same table as DAILY/SWING
            # Note: category must be 'Large-cap', 'Mid-cap', or 'Microcap' per DB constraint
            cur.execute("""
                INSERT INTO positions
                (ticker, strategy, entry_date, entry_price, quantity, current_price,
                 unrealized_pnl, stop_loss, take_profit, status, category)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                ticker, 'THUNDER', datetime.now().date(), entry_price, quantity,
                entry_price,  # current_price = entry_price initially
                0,  # unrealized_pnl = 0 initially
                0,  # THUNDER doesn't use stop_loss
                0,  # THUNDER doesn't use take_profit
                'HOLD',  # status = HOLD
                'Large-cap'  # Default to Large-cap (THUNDER focuses on quality large-caps)
            ))

        # Send Telegram alert
        send_telegram_message(f"""⚡ <b>THUNDER POSITION ENTERED</b>

📊 <b>{ticker}</b>
💰 Entry: ₹{entry_price:.2f}
📦 Quantity: {quantity} shares
💵 Investment: ₹{actual_value:,.0f}

🎯 <b>Dexter Analysis:</b>
Score: {dexter_score}/100
Recommendation: {recommendation} ({confidence})
Earnings Prediction: {analysis.get('earnings_prediction', 'N/A')}

📅 Earnings: {analysis.get('earnings_date')} ({analysis.get('days_to_earnings')} days)

💭 <b>Reasoning:</b>
{analysis.get('reasoning', 'N/A')[:200]}...

⏰ Hold through earnings, reassess after results.
""", parse_mode='HTML')

        print(f"   ✅ Position entered!")
        return True

    except Exception as e:
        print(f"   ❌ Entry failed: {e}")
        return False

if __name__ == "__main__":
    # Test with TCS analysis
    test_analysis = {
        'ticker': 'TCS.NS',
        'dexter_score': 80,
        'recommendation': 'BUY',
        'confidence': 'HIGH',
        'earnings_prediction': 'BEAT',
        'earnings_date': '2025-12-08',
        'days_to_earnings': 18,
        'reasoning': 'Strong fundamentals across all metrics',
        'sector': 'Technology'
    }

    enter_thunder_position(test_analysis)
