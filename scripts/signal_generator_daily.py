# scripts/signal_generator_daily_with_guards.py
"""
Daily trading signal generator with KNIFE GUARDS + BALANCED weights.
Added pre-filters to avoid catching falling knives.
"""

import pandas as pd
import numpy as np

# Import all indicator functions
from scripts.signal_generator_v2 import (
    calculate_rsi, calculate_macd, calculate_bollinger_bands,
    analyze_volume, calculate_trend_strength, analyze_volatility,
    calculate_roc, calculate_cci, calculate_donchian
)


def check_knife_guards(df):
    """
    KNIFE GUARDS: Pre-filter to avoid catching falling knives
    
    Based on backtest results (2026-01-12):
    - Tested 19 different guard combinations
    - Optimal: 50SMA + Vol20 (1.0x threshold)
    - Results: 33.3% -> 45.8% win rate (+12.5%)
    - Results: Rs 8,468 -> Rs 13,379 P&L (+58%)
    
    Guards:
    1. Price must be ABOVE 50-day SMA (short-term trend filter)
    2. Volume must be ABOVE 20-day average (institutional confirmation)
    
    Returns:
        tuple: (passed: bool, reason: str, guard_details: dict)
    """
    if df is None or df.empty or len(df) < 60:
        return False, 'Insufficient data', {}
    
    try:
        # Calculate indicators
        df['SMA_50'] = df['Close'].rolling(50).mean()
        df['Volume_SMA_20'] = df['Volume'].rolling(20).mean()
        
        # Current values
        current_price = df['Close'].iloc[-1]
        sma_50 = df['SMA_50'].iloc[-1]
        current_volume = df['Volume'].iloc[-1]
        volume_sma_20 = df['Volume_SMA_20'].iloc[-1]
        
        # Check for NaN
        if pd.isna(sma_50) or pd.isna(volume_sma_20):
            return False, 'Insufficient data for guards', {}
        
        guard_details = {
            'current_price': round(float(current_price), 2),
            'sma_50': round(float(sma_50), 2),
            'price_above_sma': current_price > sma_50,
            'current_volume': int(current_volume),
            'volume_sma_20': int(volume_sma_20),
            'volume_above_avg': current_volume > volume_sma_20,
            'price_sma_diff_pct': round(((current_price - sma_50) / sma_50 * 100), 2),
            'volume_ratio': round((current_volume / volume_sma_20), 2)
        }
        
        # Guard 1: Price must be above 50 SMA
        if current_price <= sma_50:
            return False, f'Below 50 SMA (Price: {current_price:.2f} vs SMA: {sma_50:.2f})', guard_details
        
        # Guard 2: Volume must be above time-adjusted 20-day average
        # During market hours, adjust expected volume based on time elapsed
        # Market hours: 9:15 AM to 3:30 PM (375 minutes)
        from datetime import datetime
        import pytz
        
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        # Calculate time-based volume adjustment factor
        if now < market_open:
            volume_factor = 0.1  # Pre-market, expect minimal volume
        elif now > market_close:
            volume_factor = 1.0  # After market, compare full day
        else:
            # During market hours - calculate fraction of day elapsed
            minutes_elapsed = (now - market_open).total_seconds() / 60
            total_minutes = 375  # 9:15 to 3:30
            volume_factor = max(0.1, minutes_elapsed / total_minutes)
        
        # Adjusted volume threshold
        adjusted_volume_threshold = volume_sma_20 * volume_factor
        
        guard_details['volume_factor'] = round(volume_factor, 2)
        guard_details['adjusted_threshold'] = int(adjusted_volume_threshold)
        
        if current_volume < adjusted_volume_threshold:
            return False, f'Weak Volume ({current_volume:,} < {adjusted_volume_threshold:,.0f} [{volume_factor:.0%} of avg])', guard_details
        
        # All guards passed
        return True, 'PASS - All guards cleared', guard_details
        
    except Exception as e:
        return False, f'Error checking guards: {str(e)}', {}


def generate_signal_daily(df, min_score=60, use_guards=True):
    """
    Generate daily trading signals with KNIFE GUARDS + BALANCED indicator weights.
    
    NEW: Pre-filters with knife guards before technical analysis
    
    Args:
        df: Price/volume dataframe
        min_score: Minimum score threshold for BUY/SELL signals
        use_guards: Whether to apply knife guards (default True)

    Weight Distribution (BALANCED):
    - RSI: 20%
    - MACD: 25%
    - Bollinger Bands: 15%
    - Volume: 10%
    - Trend: 10%
    - ATR/Volatility: 5%
    - ROC: 5%
    - CCI: 5%
    - Donchian: 5%
    """
    if df is None or df.empty or len(df) < 60:
        return "HOLD", 0, {"error": "Insufficient data"}
    
    # ===== NEW: KNIFE GUARDS CHECK =====
    if use_guards:
        guard_passed, guard_reason, guard_details = check_knife_guards(df)
        
        if not guard_passed:
            # Return HOLD with guard failure reason
            return "HOLD", 0, {
                "guard_status": "FAILED",
                "guard_reason": guard_reason,
                "guard_details": guard_details,
                "note": "Filtered by knife guards - avoiding potential falling knife"
            }
        
        # Guards passed - continue with technical analysis
        details_prefix = {
            "guard_status": "PASSED",
            "guard_reason": guard_reason,
            "guard_details": guard_details
        }
    else:
        details_prefix = {"guard_status": "DISABLED"}
    
    # ===== ORIGINAL SIGNAL GENERATION LOGIC =====
    
    # Calculate all indicators
    rsi = calculate_rsi(df)
    macd, macd_signal, macd_hist = calculate_macd(df)
    bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(df)
    volume_data = analyze_volume(df)
    trend_strength = calculate_trend_strength(df)
    volatility_data = analyze_volatility(df)
    roc = calculate_roc(df, period=12)
    cci = calculate_cci(df, period=20)
    donchian_upper, donchian_middle, donchian_lower = calculate_donchian(df, period=20)

    # Helper function
    def safe_float(val, default=0):
        try:
            if hasattr(val, '__len__') and len(val) > 1:
                val = val.iloc[0] if hasattr(val, 'iloc') else val[0]
            if hasattr(val, 'item'):
                val = val.item()
            if pd.isna(val):
                return default
            return float(val)
        except:
            return default

    # Extract values
    current_price = safe_float(df['Close'].iloc[-1])
    current_rsi = safe_float(rsi.iloc[-1], 50)
    current_macd = safe_float(macd.iloc[-1], 0)
    current_macd_signal = safe_float(macd_signal.iloc[-1], 0)
    current_macd_hist = safe_float(macd_hist.iloc[-1], 0)
    prev_macd = safe_float(macd.iloc[-2], 0) if len(macd) > 1 else 0
    prev_macd_signal = safe_float(macd_signal.iloc[-2], 0) if len(macd_signal) > 1 else 0

    signals = []
    scores = []

    # 1. RSI (20%)
    if current_rsi < 30:
        signals.append("BUY")
        scores.append(80)
    elif current_rsi < 40:
        signals.append("BUY")
        scores.append(60)
    elif current_rsi > 70:
        signals.append("SELL")
        scores.append(80)
    elif current_rsi > 60:
        signals.append("SELL")
        scores.append(60)
    else:
        signals.append("HOLD")
        scores.append(50)

    # 2. MACD (25%)
    macd_bullish_cross = prev_macd < prev_macd_signal and current_macd > current_macd_signal
    macd_bearish_cross = prev_macd > prev_macd_signal and current_macd < current_macd_signal

    if macd_bullish_cross:
        signals.append("BUY")
        scores.append(85)
    elif current_macd > current_macd_signal and current_macd_hist > 0:
        signals.append("BUY")
        scores.append(65)
    elif macd_bearish_cross:
        signals.append("SELL")
        scores.append(85)
    elif current_macd < current_macd_signal and current_macd_hist < 0:
        signals.append("SELL")
        scores.append(65)
    else:
        signals.append("HOLD")
        scores.append(50)

    # 3. Bollinger Bands (15%)
    bb_upper_val = safe_float(bb_upper.iloc[-1])
    bb_lower_val = safe_float(bb_lower.iloc[-1])
    bb_position = (current_price - bb_lower_val) / (bb_upper_val - bb_lower_val) if bb_upper_val != bb_lower_val else 0.5

    if bb_position < 0.2:
        signals.append("BUY")
        scores.append(75)
    elif bb_position < 0.4:
        signals.append("BUY")
        scores.append(60)
    elif bb_position > 0.8:
        signals.append("SELL")
        scores.append(75)
    elif bb_position > 0.6:
        signals.append("SELL")
        scores.append(60)
    else:
        signals.append("HOLD")
        scores.append(50)

    # 4. Volume (10%)
    if volume_data['is_high_volume']:
        prev_price = safe_float(df['Close'].iloc[-2]) if len(df) > 1 else current_price
        if current_price > prev_price:
            signals.append("BUY")
            scores.append(70)
        else:
            signals.append("SELL")
            scores.append(70)
    else:
        signals.append("HOLD")
        scores.append(45)

    # 5. Trend (10%)
    if trend_strength > 65:
        signals.append("BUY")
        scores.append(int(trend_strength))
    elif trend_strength < 35:
        signals.append("SELL")
        scores.append(int(100 - trend_strength))
    else:
        signals.append("HOLD")
        scores.append(50)

    # 6. Volatility (5%)
    volatility_score = volatility_data['score']
    volatility_signal = volatility_data['signal']

    if volatility_signal == "AVOID":
        signals.append("HOLD")
        scores.append(volatility_score)
    elif volatility_signal == "CAUTION":
        signals.append("HOLD")
        scores.append(volatility_score)
    elif volatility_signal == "FAVORABLE":
        signals.append("NEUTRAL")
        scores.append(volatility_score)
    else:
        signals.append("NEUTRAL")
        scores.append(volatility_score)

    # 7. ROC (5%)
    current_roc = safe_float(roc.iloc[-1], 0)
    if current_roc > 5:
        signals.append("BUY")
        scores.append(min(100, 60 + current_roc))
    elif current_roc > 2:
        signals.append("BUY")
        scores.append(65)
    elif current_roc < -5:
        signals.append("SELL")
        scores.append(min(100, 60 + abs(current_roc)))
    elif current_roc < -2:
        signals.append("SELL")
        scores.append(65)
    else:
        signals.append("HOLD")
        scores.append(50)

    # 8. CCI (5%)
    current_cci = safe_float(cci.iloc[-1], 0)
    if current_cci < -100:
        signals.append("BUY")
        scores.append(80)
    elif current_cci < -50:
        signals.append("BUY")
        scores.append(65)
    elif current_cci > 100:
        signals.append("SELL")
        scores.append(80)
    elif current_cci > 50:
        signals.append("SELL")
        scores.append(65)
    else:
        signals.append("HOLD")
        scores.append(50)

    # 9. Donchian (5%)
    donchian_upper_val = safe_float(donchian_upper.iloc[-1])
    donchian_lower_val = safe_float(donchian_lower.iloc[-1])
    prev_price = safe_float(df['Close'].iloc[-2]) if len(df) > 1 else current_price

    if current_price >= donchian_upper_val and prev_price < donchian_upper_val:
        signals.append("BUY")
        scores.append(85)
    elif current_price > donchian_upper_val * 0.98:
        signals.append("BUY")
        scores.append(70)
    elif current_price <= donchian_lower_val and prev_price > donchian_lower_val:
        signals.append("SELL")
        scores.append(85)
    elif current_price < donchian_lower_val * 1.02:
        signals.append("SELL")
        scores.append(70)
    else:
        signals.append("HOLD")
        scores.append(50)

    # BALANCED WEIGHTS for daily trading
    weights = [0.20, 0.25, 0.15, 0.10, 0.10, 0.05, 0.05, 0.05, 0.05]
    total_score = sum(score * weight for score, weight in zip(scores, weights))

    # Final signal
    buy_count = signals.count("BUY")
    sell_count = signals.count("SELL")

    if buy_count > sell_count and total_score >= min_score:
        final_signal = "BUY"
    elif sell_count > buy_count and total_score >= min_score:
        final_signal = "SELL"
    else:
        final_signal = "HOLD"

    # Details (merge with guard details if guards were used)
    details = {
        **details_prefix,  # Guard status and details
        'rsi': round(current_rsi, 2),
        'macd': round(current_macd, 4),
        'macd_signal': round(current_macd_signal, 4),
        'macd_histogram': round(current_macd_hist, 4),
        'bb_position': round(bb_position * 100, 2),
        'volume_ratio': round(volume_data['volume_ratio'], 2),
        'trend_strength': round(trend_strength, 2),
        'volatility_ratio': volatility_data['volatility_ratio'],
        'volatility_category': volatility_data['category'],
        'atr_pct': volatility_data['atr_pct'],
        'roc': round(current_roc, 2),
        'cci': round(current_cci, 2),
        'donchian_position': round(((current_price - donchian_lower_val) / (donchian_upper_val - donchian_lower_val) * 100) if donchian_upper_val != donchian_lower_val else 50, 2),
        'component_signals': signals,
        'component_scores': [round(s, 2) for s in scores]
    }

    return final_signal, round(total_score, 2), details
