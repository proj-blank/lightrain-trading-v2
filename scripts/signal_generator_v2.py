# scripts/signal_generator_v2.py
"""
Enhanced signal generator with multiple technical indicators:
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- Volume analysis
- Trend strength
"""

import pandas as pd
import numpy as np


def calculate_rsi(df, period=14):
    """Calculate RSI indicator."""
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(df, fast=12, slow=26, signal=9):
    """Calculate MACD indicator."""
    ema_fast = df['Close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['Close'].ewm(span=slow, adjust=False).mean()

    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    macd_histogram = macd - macd_signal

    return macd, macd_signal, macd_histogram


def calculate_bollinger_bands(df, period=20, std_dev=2):
    """Calculate Bollinger Bands."""
    sma = df['Close'].rolling(window=period).mean()
    std = df['Close'].rolling(window=period).std()

    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)

    return upper_band, sma, lower_band


def analyze_volume(df, period=20):
    """Analyze volume trends."""
    avg_volume = df['Volume'].rolling(window=period).mean()

    # Safely extract scalar values
    current_vol = df['Volume'].iloc[-1]
    current_volume = float(current_vol.item() if hasattr(current_vol, 'item') else current_vol)

    avg_vol = avg_volume.iloc[-1]
    avg_vol_value = float(avg_vol.item() if hasattr(avg_vol, 'item') else avg_vol) if not pd.isna(avg_vol).any() else 1

    volume_ratio = current_volume / avg_vol_value if avg_vol_value > 0 else 1

    return {
        'avg_volume': avg_vol_value,
        'current_volume': current_volume,
        'volume_ratio': volume_ratio,
        'is_high_volume': volume_ratio > 1.5
    }


def calculate_trend_strength(df, short_period=20, long_period=50):
    """Calculate trend strength using multiple moving averages."""
    sma_short = df['Close'].rolling(window=short_period).mean()
    sma_long = df['Close'].rolling(window=long_period).mean()

    # Safely extract scalar values
    curr_price = df['Close'].iloc[-1]
    current_price = float(curr_price.item() if hasattr(curr_price, 'item') else curr_price)

    short = sma_short.iloc[-1]
    short_ma = float(short.item() if hasattr(short, 'item') else short)

    long = sma_long.iloc[-1]
    long_ma = float(long.item() if hasattr(long, 'item') else long)

    # Calculate trend strength (0-100)
    if pd.isna(short_ma) or pd.isna(long_ma):
        return 50  # Neutral

    # Distance from moving averages
    distance_short = ((current_price - short_ma) / short_ma) * 100
    distance_long = ((current_price - long_ma) / long_ma) * 100

    # MA alignment
    ma_alignment = 100 if short_ma > long_ma else 0

    # Combine factors
    trend_strength = (distance_short + distance_long + ma_alignment) / 3

    # Normalize to 0-100
    trend_strength = max(0, min(100, 50 + trend_strength))

    return trend_strength


def calculate_atr(df, period=14):
    """
    Calculate Average True Range (ATR) - volatility indicator.

    ATR measures market volatility by decomposing the entire range of price movement.
    Higher ATR = higher volatility, Lower ATR = lower volatility.

    Returns:
        pandas.Series: ATR values
    """
    high_low = df['High'] - df['Low']
    high_close = abs(df['High'] - df['Close'].shift())
    low_close = abs(df['Low'] - df['Close'].shift())

    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(period).mean()

    return atr


def calculate_adx(df, period=14):
    """
    Calculate ADX (Average Directional Index) - trend strength indicator.

    ADX > 25 = Strong trend
    ADX < 20 = Weak/ranging market

    Returns:
        tuple: (adx, plus_di, minus_di)
    """
    # Calculate +DM and -DM
    high_diff = df['High'].diff()
    low_diff = -df['Low'].diff()

    plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
    minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)

    # Calculate ATR for smoothing
    atr = calculate_atr(df, period)

    # Calculate directional indicators
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)

    # Calculate DX and ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(period).mean()

    return adx, plus_di, minus_di


def calculate_stochastic(df, k_period=14, d_period=3):
    """
    Calculate Stochastic Oscillator - momentum indicator.

    %K < 20 = Oversold
    %K > 80 = Overbought
    %K crosses %D = Buy/Sell signal

    Returns:
        tuple: (k, d)
    """
    lowest_low = df['Low'].rolling(k_period).min()
    highest_high = df['High'].rolling(k_period).max()

    k = 100 * ((df['Close'] - lowest_low) / (highest_high - lowest_low))
    d = k.rolling(d_period).mean()

    return k, d


def calculate_roc(df, period=12):
    """
    Calculate Rate of Change (ROC) - momentum indicator.

    ROC measures the percentage change in price over N periods.
    ROC > 0 = Bullish momentum
    ROC < 0 = Bearish momentum

    Returns:
        pandas.Series: ROC values
    """
    roc = ((df['Close'] - df['Close'].shift(period)) / df['Close'].shift(period)) * 100
    return roc


def calculate_cci(df, period=20):
    """
    Calculate Commodity Channel Index (CCI) - overbought/oversold indicator.

    CCI > +100 = Overbought (potential sell)
    CCI < -100 = Oversold (potential buy)
    CCI between -100 and +100 = Neutral

    Returns:
        pandas.Series: CCI values
    """
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    sma = typical_price.rolling(period).mean()
    mean_deviation = typical_price.rolling(period).apply(lambda x: abs(x - x.mean()).mean())

    cci = (typical_price - sma) / (0.015 * mean_deviation)
    return cci


def calculate_donchian(df, period=20):
    """
    Calculate Donchian Channels - breakout indicator.

    Breakout above upper channel = Buy signal
    Breakout below lower channel = Sell signal

    Returns:
        tuple: (upper_channel, middle_channel, lower_channel)
    """
    upper_channel = df['High'].rolling(period).max()
    lower_channel = df['Low'].rolling(period).min()
    middle_channel = (upper_channel + lower_channel) / 2

    return upper_channel, middle_channel, lower_channel


def analyze_volatility(df, atr_period=14, lookback=50):
    """
    Analyze current volatility vs historical average.

    Returns:
        dict: Volatility metrics including ratio and signal
    """
    atr = calculate_atr(df, atr_period)

    # Calculate ATR as percentage of price
    atr_pct = (atr / df['Close']) * 100

    # Safely extract scalars
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

    current_atr_pct = safe_float(atr_pct.iloc[-1], 1.0)
    avg_atr_pct = safe_float(atr_pct.rolling(lookback).mean().iloc[-1], 1.0)

    # Volatility ratio: current vs average
    volatility_ratio = current_atr_pct / avg_atr_pct if avg_atr_pct > 0 else 1.0

    # Categorize volatility
    if volatility_ratio > 2.0:
        category = "EXTREME"
        signal = "AVOID"
        score = 20
    elif volatility_ratio > 1.5:
        category = "HIGH"
        signal = "CAUTION"
        score = 40
    elif volatility_ratio > 1.2:
        category = "ELEVATED"
        signal = "REDUCE"
        score = 60
    elif volatility_ratio < 0.7:
        category = "LOW"
        signal = "FAVORABLE"
        score = 85
    else:
        category = "NORMAL"
        signal = "OK"
        score = 75

    return {
        'atr_pct': round(current_atr_pct, 2),
        'avg_atr_pct': round(avg_atr_pct, 2),
        'volatility_ratio': round(volatility_ratio, 2),
        'category': category,
        'signal': signal,
        'score': score
    }


def generate_signal_v2(df, min_score=60):
    """
    Generate trading signals using multiple technical indicators.

    Returns:
        tuple: (signal, score, details)
        - signal: "BUY", "SELL", or "HOLD"
        - score: 0-100 confidence score
        - details: dict with indicator values
    """
    if df is None or df.empty or len(df) < 60:
        return "HOLD", 0, {"error": "Insufficient data"}

    # Calculate all indicators
    rsi = calculate_rsi(df)
    macd, macd_signal, macd_hist = calculate_macd(df)
    bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(df)
    volume_data = analyze_volume(df)
    trend_strength = calculate_trend_strength(df)
    volatility_data = analyze_volatility(df)  # ATR-based volatility filter

    # NEW: AlphaSuite-inspired indicators
    roc = calculate_roc(df, period=12)
    cci = calculate_cci(df, period=20)
    donchian_upper, donchian_middle, donchian_lower = calculate_donchian(df, period=20)

    # Helper function to safely extract scalar
    def safe_float(val, default=0):
        try:
            # Check if it's a Series or has multiple values
            if hasattr(val, '__len__') and len(val) > 1:
                val = val.iloc[0] if hasattr(val, 'iloc') else val[0]

            # Extract scalar value
            if hasattr(val, 'item'):
                val = val.item()

            # Check if NaN
            if pd.isna(val):
                return default

            return float(val)
        except:
            return default

    # Get latest values - safely extract scalars
    current_price = safe_float(df['Close'].iloc[-1])
    current_rsi = safe_float(rsi.iloc[-1], 50)
    current_macd = safe_float(macd.iloc[-1], 0)
    current_macd_signal = safe_float(macd_signal.iloc[-1], 0)
    current_macd_hist = safe_float(macd_hist.iloc[-1], 0)

    # Previous values for crossover detection
    prev_macd = safe_float(macd.iloc[-2], 0) if len(macd) > 1 else 0
    prev_macd_signal = safe_float(macd_signal.iloc[-2], 0) if len(macd_signal) > 1 else 0

    # Initialize score components
    signals = []
    scores = []

    # 1. RSI Analysis (Weight: 20%)
    if current_rsi < 30:
        signals.append("BUY")
        scores.append(80)  # Oversold - strong buy
    elif current_rsi < 40:
        signals.append("BUY")
        scores.append(60)  # Mildly oversold
    elif current_rsi > 70:
        signals.append("SELL")
        scores.append(80)  # Overbought - strong sell
    elif current_rsi > 60:
        signals.append("SELL")
        scores.append(60)  # Mildly overbought
    else:
        signals.append("HOLD")
        scores.append(50)  # Neutral

    # 2. MACD Analysis (Weight: 25%)
    macd_bullish_cross = prev_macd < prev_macd_signal and current_macd > current_macd_signal
    macd_bearish_cross = prev_macd > prev_macd_signal and current_macd < current_macd_signal

    if macd_bullish_cross:
        signals.append("BUY")
        scores.append(85)  # Strong buy signal
    elif current_macd > current_macd_signal and current_macd_hist > 0:
        signals.append("BUY")
        scores.append(65)  # Bullish momentum
    elif macd_bearish_cross:
        signals.append("SELL")
        scores.append(85)  # Strong sell signal
    elif current_macd < current_macd_signal and current_macd_hist < 0:
        signals.append("SELL")
        scores.append(65)  # Bearish momentum
    else:
        signals.append("HOLD")
        scores.append(50)

    # 3. Bollinger Bands Analysis (Weight: 20%)
    bb_upper_val = safe_float(bb_upper.iloc[-1])
    bb_lower_val = safe_float(bb_lower.iloc[-1])
    bb_position = (current_price - bb_lower_val) / (bb_upper_val - bb_lower_val) if bb_upper_val != bb_lower_val else 0.5

    if bb_position < 0.2:
        signals.append("BUY")
        scores.append(75)  # Near lower band - buy opportunity
    elif bb_position < 0.4:
        signals.append("BUY")
        scores.append(60)
    elif bb_position > 0.8:
        signals.append("SELL")
        scores.append(75)  # Near upper band - sell opportunity
    elif bb_position > 0.6:
        signals.append("SELL")
        scores.append(60)
    else:
        signals.append("HOLD")
        scores.append(50)

    # 4. Volume Confirmation (Weight: 15%)
    if volume_data['is_high_volume']:
        # High volume confirms the trend
        prev_price = safe_float(df['Close'].iloc[-2]) if len(df) > 1 else current_price
        if current_price > prev_price:
            signals.append("BUY")
            scores.append(70)
        else:
            signals.append("SELL")
            scores.append(70)
    else:
        signals.append("HOLD")
        scores.append(45)  # Low volume - less confidence

    # 5. Trend Strength (Weight: 15%)
    if trend_strength > 65:
        signals.append("BUY")
        scores.append(int(trend_strength))
    elif trend_strength < 35:
        signals.append("SELL")
        scores.append(int(100 - trend_strength))
    else:
        signals.append("HOLD")
        scores.append(50)

    # 6. Volatility Filter (Weight: 10%)
    volatility_score = volatility_data['score']
    volatility_signal = volatility_data['signal']

    if volatility_signal == "AVOID":
        # Extreme volatility - force HOLD
        signals.append("HOLD")
        scores.append(volatility_score)
    elif volatility_signal == "CAUTION":
        # High volatility - reduce confidence in other signals
        signals.append("HOLD")
        scores.append(volatility_score)
    elif volatility_signal == "FAVORABLE":
        # Low volatility - good for trading
        signals.append("NEUTRAL")
        scores.append(volatility_score)
    else:
        # Normal volatility
        signals.append("NEUTRAL")
        scores.append(volatility_score)

    # 7. ROC - Rate of Change (Weight: 10%)
    current_roc = safe_float(roc.iloc[-1], 0)
    if current_roc > 5:
        signals.append("BUY")
        scores.append(min(100, 60 + current_roc))  # Strong upward momentum
    elif current_roc > 2:
        signals.append("BUY")
        scores.append(65)
    elif current_roc < -5:
        signals.append("SELL")
        scores.append(min(100, 60 + abs(current_roc)))  # Strong downward momentum
    elif current_roc < -2:
        signals.append("SELL")
        scores.append(65)
    else:
        signals.append("HOLD")
        scores.append(50)

    # 8. CCI - Commodity Channel Index (Weight: 10%)
    current_cci = safe_float(cci.iloc[-1], 0)
    if current_cci < -100:
        signals.append("BUY")
        scores.append(80)  # Oversold
    elif current_cci < -50:
        signals.append("BUY")
        scores.append(65)
    elif current_cci > 100:
        signals.append("SELL")
        scores.append(80)  # Overbought
    elif current_cci > 50:
        signals.append("SELL")
        scores.append(65)
    else:
        signals.append("HOLD")
        scores.append(50)

    # 9. Donchian Channels - Breakout (Weight: 10%)
    donchian_upper_val = safe_float(donchian_upper.iloc[-1])
    donchian_lower_val = safe_float(donchian_lower.iloc[-1])
    prev_price = safe_float(df['Close'].iloc[-2]) if len(df) > 1 else current_price

    # Breakout detection
    if current_price >= donchian_upper_val and prev_price < donchian_upper_val:
        signals.append("BUY")
        scores.append(85)  # Bullish breakout
    elif current_price > donchian_upper_val * 0.98:
        signals.append("BUY")
        scores.append(70)  # Near upper channel
    elif current_price <= donchian_lower_val and prev_price > donchian_lower_val:
        signals.append("SELL")
        scores.append(85)  # Bearish breakdown
    elif current_price < donchian_lower_val * 1.02:
        signals.append("SELL")
        scores.append(70)  # Near lower channel
    else:
        signals.append("HOLD")
        scores.append(50)

    # Calculate weighted average score
    # BOOSTED WEIGHTS: Emphasize new AlphaSuite indicators (ROC, CCI, Donchian)
    # RSI 10%, MACD 15%, BB 8%, Volume 8%, Trend 8%, ATR 10%, ROC 15%, CCI 15%, Donchian 18%
    weights = [0.10, 0.15, 0.08, 0.08, 0.08, 0.10, 0.15, 0.15, 0.18]
    total_score = sum(score * weight for score, weight in zip(scores, weights))

    # Determine final signal based on majority and score
    buy_count = signals.count("BUY")
    sell_count = signals.count("SELL")

    if buy_count > sell_count and total_score >= min_score:
        final_signal = "BUY"
    elif sell_count > buy_count and total_score >= min_score:
        final_signal = "SELL"
    else:
        final_signal = "HOLD"

    # Compile details
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
        'component_scores': [round(s, 2) for s in scores]
    }

    return final_signal, round(total_score, 2), details


def get_signal_explanation(signal, score, details):
    """Generate human-readable explanation of the signal."""
    explanation = f"Signal: {signal} (Score: {score}/100)\n\n"

    explanation += "Technical Indicators:\n"
    explanation += f"  • RSI: {details['rsi']} - "
    if details['rsi'] < 30:
        explanation += "Oversold (Bullish)\n"
    elif details['rsi'] > 70:
        explanation += "Overbought (Bearish)\n"
    else:
        explanation += "Neutral\n"

    explanation += f"  • MACD: {details['macd']:.4f} vs Signal: {details['macd_signal']:.4f}\n"
    explanation += f"  • Bollinger Band Position: {details['bb_position']:.1f}% "
    if details['bb_position'] < 30:
        explanation += "(Near Lower Band - Bullish)\n"
    elif details['bb_position'] > 70:
        explanation += "(Near Upper Band - Bearish)\n"
    else:
        explanation += "(Mid-range)\n"

    explanation += f"  • Volume Ratio: {details['volume_ratio']:.2f}x average\n"
    explanation += f"  • Trend Strength: {details['trend_strength']:.1f}/100\n"
    explanation += f"  • Volatility: {details['volatility_category']} "
    explanation += f"(ATR: {details['atr_pct']:.2f}%, Ratio: {details['volatility_ratio']:.2f}x)\n"

    # Add volatility warning if needed
    if details['volatility_category'] in ['EXTREME', 'HIGH']:
        explanation += f"\n⚠️ WARNING: {details['volatility_category']} volatility detected!"
        explanation += " Consider reducing position size or avoiding this trade.\n"
    elif details['volatility_category'] == 'LOW':
        explanation += "\n✅ Low volatility - favorable trading conditions.\n"

    return explanation
