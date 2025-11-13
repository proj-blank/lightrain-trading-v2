# scripts/signal_generator_swing.py
"""
Swing trading signal generator with BOOSTED AlphaSuite indicators.
Optimized for daily timeframe with emphasis on ROC, CCI, and Donchian Channels.
"""

import pandas as pd
import numpy as np

# Import all indicator functions from v2
from scripts.signal_generator_v2 import (
    calculate_rsi, calculate_macd, calculate_bollinger_bands,
    analyze_volume, calculate_trend_strength, analyze_volatility,
    calculate_roc, calculate_cci, calculate_donchian
)


def generate_signal_swing(df, min_score=65):
    """
    Generate swing trading signals with BALANCED weights + Entry Filters.

    Weight Distribution (REBALANCED):
    - RSI: 15% (increased for mean reversion)
    - MACD: 12% (reduced from 15%)
    - Bollinger Bands: 12% (increased for volatility awareness)
    - Volume: 10% (increased)
    - Trend: 10% (increased)
    - ATR/Volatility: 9% (slightly reduced)
    - ROC: 10% (reduced from 15%)
    - CCI: 10% (reduced from 15%)
    - Donchian: 12% (reduced from 18%)

    New Entry Filters:
    1. RSI Overbought Filter: Reject if RSI > 70
    2. Pullback Filter: Prefer entries 0.5-3% below 5-day high
    3. Minimum score raised to 65 (from 60)
    """
    if df is None or df.empty or len(df) < 60:
        return "HOLD", 0, {"error": "Insufficient data"}

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

    # === NEW ENTRY FILTERS ===

    # Filter 1: RSI Overbought Filter
    if current_rsi > 70:
        return "HOLD", 0, {
            "filter_rejection": "RSI Overbought",
            "rsi": round(current_rsi, 2),
            "message": f"RSI too high ({current_rsi:.1f}) - likely overbought, rejecting entry"
        }

    # Filter 2: Pullback Filter
    high_5d = safe_float(df['High'].tail(5).max())
    pullback_pct = ((high_5d - current_price) / high_5d) * 100 if high_5d > 0 else 0

    # Penalize if at or near all-time highs (no pullback)
    pullback_penalty = 0
    if pullback_pct < 0.5:  # At or above 5-day high
        pullback_penalty = 15  # -15 points penalty
    elif pullback_pct > 4.0:  # Too far from highs
        pullback_penalty = 10  # -10 points penalty
    # Sweet spot: 0.5-4% pullback gets no penalty

    # Filter 3: Market Regime Filter (check Nifty 50 trend)
    market_regime_penalty = 0
    try:
        import yfinance as yf
        nifty = yf.download('^NSEI', period='1mo', progress=False)
        if not nifty.empty and len(nifty) >= 20:
            nifty_sma20 = nifty['Close'].rolling(20).mean().iloc[-1]
            nifty_current = safe_float(nifty['Close'].iloc[-1])
            nifty_trend = "BULLISH" if nifty_current > nifty_sma20 else "BEARISH"

            # In bearish market, increase selectivity
            if nifty_trend == "BEARISH":
                market_regime_penalty = 10  # -10 points in bearish market
        else:
            nifty_trend = "UNKNOWN"
    except:
        nifty_trend = "UNKNOWN"
        market_regime_penalty = 0

    signals = []
    scores = []

    # 1. RSI (10%)
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

    # 2. MACD (15%)
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

    # 3. Bollinger Bands (8%)
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

    # 4. Volume (8%)
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

    # 5. Trend (8%)
    if trend_strength > 65:
        signals.append("BUY")
        scores.append(int(trend_strength))
    elif trend_strength < 35:
        signals.append("SELL")
        scores.append(int(100 - trend_strength))
    else:
        signals.append("HOLD")
        scores.append(50)

    # 6. Volatility (10%)
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

    # 7. ROC (15% - BOOSTED)
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

    # 8. CCI (15% - BOOSTED)
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

    # 9. Donchian (18% - BOOSTED)
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

    # REBALANCED WEIGHTS for swing trading (momentum reduced, mean reversion increased)
    weights = [0.15, 0.12, 0.12, 0.10, 0.10, 0.09, 0.10, 0.10, 0.12]
    # RSI 15%, MACD 12%, BB 12%, Volume 10%, Trend 10%, ATR 9%, ROC 10%, CCI 10%, Donchian 12%

    total_score = sum(score * weight for score, weight in zip(scores, weights))

    # Apply penalties
    total_score = max(0, total_score - pullback_penalty - market_regime_penalty)

    # Final signal
    buy_count = signals.count("BUY")
    sell_count = signals.count("SELL")

    if buy_count > sell_count and total_score >= min_score:
        final_signal = "BUY"
    elif sell_count > buy_count and total_score >= min_score:
        final_signal = "SELL"
    else:
        final_signal = "HOLD"

    # Details
    details = {
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
        'component_scores': [round(s, 2) for s in scores],
        # New filter details
        'pullback_from_5d_high': round(pullback_pct, 2),
        'pullback_penalty': round(pullback_penalty, 2),
        'market_regime': nifty_trend,
        'market_regime_penalty': round(market_regime_penalty, 2),
        'raw_score_before_penalties': round(total_score + pullback_penalty + market_regime_penalty, 2)
    }

    return final_signal, round(total_score, 2), details
