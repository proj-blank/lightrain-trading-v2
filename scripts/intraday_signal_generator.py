# scripts/intraday_signal_generator.py
"""
Intraday signal generator for scalping and momentum trading.
Optimized for 1-minute to 15-minute timeframes.

Strategies:
1. Momentum Scalping: Quick moves based on price action
2. VWAP Strategy: Buy below VWAP, sell above
3. Breakout Trading: Volume + price breakouts
4. Mean Reversion: Quick bounces from support/resistance
"""

import pandas as pd
import numpy as np


def calculate_vwap(df):
    """Calculate Volume Weighted Average Price (VWAP)."""
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    return (typical_price * df['Volume']).cumsum() / df['Volume'].cumsum()


def calculate_ema(df, period):
    """Calculate Exponential Moving Average."""
    return df['Close'].ewm(span=period, adjust=False).mean()


def detect_momentum(df, lookback=5):
    """
    Detect strong momentum moves.

    Returns:
        dict: Momentum metrics
    """
    if len(df) < lookback:
        return {' type': 'NEUTRAL', 'strength': 0, 'change_pct': 0}

    # Price change over lookback period
    price_change = float(df['Close'].iloc[-1]) - float(df['Close'].iloc[-lookback])
    price_change_pct = (price_change / float(df['Close'].iloc[-lookback])) * 100

    # Volume confirmation
    avg_volume = float(df['Volume'].iloc[-lookback:-1].mean())
    current_volume = float(df['Volume'].iloc[-1])
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

    # Determine momentum type
    if price_change_pct > 0.5 and volume_ratio > 1.2:
        momentum_type = 'STRONG_BULLISH'
        strength = min(100, abs(price_change_pct) * 10 * volume_ratio)
    elif price_change_pct < -0.5 and volume_ratio > 1.2:
        momentum_type = 'STRONG_BEARISH'
        strength = min(100, abs(price_change_pct) * 10 * volume_ratio)
    elif price_change_pct > 0.2:
        momentum_type = 'BULLISH'
        strength = min(100, abs(price_change_pct) * 15)
    elif price_change_pct < -0.2:
        momentum_type = 'BEARISH'
        strength = min(100, abs(price_change_pct) * 15)
    else:
        momentum_type = 'NEUTRAL'
        strength = 50

    return {
        'type': momentum_type,
        'strength': strength,
        'change_pct': round(price_change_pct, 2),
        'volume_ratio': round(volume_ratio, 2)
    }


def vwap_strategy(df):
    """
    VWAP-based strategy.
    Buy when price < VWAP and moving up
    Sell when price > VWAP and moving down
    """
    if len(df) < 10:
        return {'signal': 'HOLD', 'score': 50, 'reason': 'Insufficient data'}

    vwap = calculate_vwap(df)
    current_price = float(df['Close'].iloc[-1])
    current_vwap = float(vwap.iloc[-1])

    # Price relative to VWAP
    vwap_distance = ((current_price - current_vwap) / current_vwap) * 100

    # Recent price movement
    price_momentum = ((float(df['Close'].iloc[-1]) - float(df['Close'].iloc[-3])) / float(df['Close'].iloc[-3])) * 100

    if current_price < current_vwap and price_momentum > 0.1:
        # Below VWAP and moving up - BUY
        score = 70 + min(abs(vwap_distance) * 5, 20)
        return {'signal': 'BUY', 'score': score, 'reason': f'Below VWAP ({vwap_distance:.2f}%), upward momentum'}
    elif current_price > current_vwap and price_momentum < -0.1:
        # Above VWAP and moving down - SELL
        score = 70 + min(abs(vwap_distance) * 5, 20)
        return {'signal': 'SELL', 'score': score, 'reason': f'Above VWAP ({vwap_distance:.2f}%), downward momentum'}
    else:
        return {'signal': 'HOLD', 'score': 50, 'reason': 'No clear VWAP signal'}


def breakout_strategy(df):
    """
    Breakout strategy based on support/resistance levels.
    """
    if len(df) < 20:
        return {'signal': 'HOLD', 'score': 50, 'reason': 'Insufficient data'}

    # Calculate recent high/low (resistance/support)
    recent_high = float(df['High'].iloc[-20:-1].max())
    recent_low = float(df['Low'].iloc[-20:-1].min())
    current_price = float(df['Close'].iloc[-1])
    current_volume = float(df['Volume'].iloc[-1])
    avg_volume = float(df['Volume'].iloc[-20:-1].mean())

    volume_surge = current_volume > (avg_volume * 1.5)

    # Breakout above resistance
    if current_price > recent_high and volume_surge:
        breakout_strength = ((current_price - recent_high) / recent_high) * 100
        score = 75 + min(breakout_strength * 10, 20)
        return {'signal': 'BUY', 'score': score, 'reason': f'Breakout above {recent_high:.2f} with volume'}

    # Breakdown below support
    if current_price < recent_low and volume_surge:
        breakdown_strength = ((recent_low - current_price) / recent_low) * 100
        score = 75 + min(breakdown_strength * 10, 20)
        return {'signal': 'SELL', 'score': score, 'reason': f'Breakdown below {recent_low:.2f} with volume'}

    return {'signal': 'HOLD', 'score': 50, 'reason': 'No breakout detected'}


def scalping_strategy(df):
    """
    Quick scalping strategy using EMAs and momentum.
    Fast: 5 EMA, Slow: 20 EMA
    """
    if len(df) < 25:
        return {'signal': 'HOLD', 'score': 50, 'reason': 'Insufficient data'}

    ema5 = calculate_ema(df, 5)
    ema20 = calculate_ema(df, 20)

    current_price = float(df['Close'].iloc[-1])
    prev_price = float(df['Close'].iloc[-2])

    # EMA crossover
    current_ema5 = float(ema5.iloc[-1])
    current_ema20 = float(ema20.iloc[-1])
    prev_ema5 = float(ema5.iloc[-2])
    prev_ema20 = float(ema20.iloc[-2])

    # Bullish crossover
    if prev_ema5 <= prev_ema20 and current_ema5 > current_ema20:
        return {'signal': 'BUY', 'score': 80, 'reason': 'Bullish EMA crossover (5/20)'}

    # Bearish crossover
    if prev_ema5 >= prev_ema20 and current_ema5 < current_ema20:
        return {'signal': 'SELL', 'score': 80, 'reason': 'Bearish EMA crossover (5/20)'}

    # Trending with EMAs
    if current_price > current_ema5 > current_ema20 and (current_price - prev_price) > 0:
        return {'signal': 'BUY', 'score': 65, 'reason': 'Strong uptrend'}

    if current_price < current_ema5 < current_ema20 and (current_price - prev_price) < 0:
        return {'signal': 'SELL', 'score': 65, 'reason': 'Strong downtrend'}

    return {'signal': 'HOLD', 'score': 50, 'reason': 'No clear trend'}


def generate_intraday_signal(df, strategy='combined', min_score=65):
    """
    Generate intraday trading signals.

    Args:
        df: DataFrame with OHLCV data
        strategy: 'vwap', 'breakout', 'scalping', or 'combined'
        min_score: Minimum score to generate BUY/SELL (default 65)

    Returns:
        tuple: (signal, score, details)
    """
    if df is None or df.empty or len(df) < 25:
        return "HOLD", 0, {"error": "Insufficient data"}

    # Run all strategies
    vwap_result = vwap_strategy(df)
    breakout_result = breakout_strategy(df)
    scalping_result = scalping_strategy(df)
    momentum_data = detect_momentum(df, lookback=5)

    if strategy == 'vwap':
        result = vwap_result
    elif strategy == 'breakout':
        result = breakout_result
    elif strategy == 'scalping':
        result = scalping_result
    elif strategy == 'combined':
        # Combine all strategies with voting
        signals = [vwap_result, breakout_result, scalping_result]
        buy_votes = sum(1 for s in signals if s['signal'] == 'BUY')
        sell_votes = sum(1 for s in signals if s['signal'] == 'SELL')

        # Average score
        avg_score = sum(s['score'] for s in signals) / len(signals)

        # Apply momentum boost
        if momentum_data['type'] == 'STRONG_BULLISH':
            avg_score += 10
        elif momentum_data['type'] == 'STRONG_BEARISH':
            avg_score += 10

        # Determine final signal
        if buy_votes >= 2 and avg_score >= min_score:
            result = {'signal': 'BUY', 'score': avg_score, 'reason': f'{buy_votes}/3 strategies agree (BUY)'}
        elif sell_votes >= 2 and avg_score >= min_score:
            result = {'signal': 'SELL', 'score': avg_score, 'reason': f'{sell_votes}/3 strategies agree (SELL)'}
        else:
            result = {'signal': 'HOLD', 'score': avg_score, 'reason': 'No consensus or low score'}
    else:
        result = {'signal': 'HOLD', 'score': 50, 'reason': 'Invalid strategy'}

    # Compile detailed info
    details = {
        'vwap': vwap_result,
        'breakout': breakout_result,
        'scalping': scalping_result,
        'momentum': momentum_data,
        'current_price': float(df['Close'].iloc[-1]),
        'current_volume': int(df['Volume'].iloc[-1])
    }

    return result['signal'], round(result['score'], 2), details


def calculate_intraday_targets(entry_price, atr=None, target_pct=0.005, stop_pct=0.003):
    """
    Calculate quick profit targets and stop-loss for intraday trading.

    Default: 0.5% profit target, 0.3% stop-loss (conservative scalping)

    Args:
        entry_price: Entry price
        atr: Optional ATR for dynamic targets
        target_pct: Target profit percentage (default 0.5%)
        stop_pct: Stop-loss percentage (default 0.3%)

    Returns:
        tuple: (target_price, stop_loss_price)
    """
    if atr and atr > 0:
        # Use ATR-based targets for volatile stocks
        target = entry_price + (atr * 0.5)
        stop_loss = entry_price - (atr * 0.3)
    else:
        # Use percentage-based targets
        target = entry_price * (1 + target_pct)
        stop_loss = entry_price * (1 - stop_pct)

    return round(target, 2), round(stop_loss, 2)


if __name__ == "__main__":
    # Test with sample data
    print("Testing intraday signal generator...")

    # Create sample intraday data
    dates = pd.date_range(end=pd.Timestamp.now(), periods=50, freq='1min')
    sample_data = pd.DataFrame({
        'Open': np.random.uniform(1000, 1010, 50),
        'High': np.random.uniform(1005, 1015, 50),
        'Low': np.random.uniform(995, 1005, 50),
        'Close': np.random.uniform(1000, 1010, 50),
        'Volume': np.random.randint(100000, 500000, 50)
    }, index=dates)

    signal, score, details = generate_intraday_signal(sample_data, strategy='combined')

    print(f"\nSignal: {signal}")
    print(f"Score: {score}")
    print(f"Momentum: {details['momentum']['type']} ({details['momentum']['change_pct']}%)")
    print(f"\nStrategy Breakdown:")
    print(f"  VWAP: {details['vwap']['signal']} (Score: {details['vwap']['score']})")
    print(f"  Breakout: {details['breakout']['signal']} (Score: {details['breakout']['score']})")
    print(f"  Scalping: {details['scalping']['signal']} (Score: {details['scalping']['score']})")
