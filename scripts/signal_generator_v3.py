"""
signal_generator_v3.py - Configurable multi-indicator signal generator

Features:
- Load indicator config from JSON
- Enable/disable indicators dynamically
- Telegram command integration
- Backtest different indicator combinations
"""

import pandas as pd
import numpy as np
import json
import os
from .signal_generator_v2 import (
    calculate_rsi, calculate_macd, calculate_bollinger_bands,
    analyze_volume, calculate_trend_strength, analyze_volatility,
    calculate_adx, calculate_stochastic
)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'indicators_config.json')


def load_indicator_config():
    """Load indicator configuration from JSON file."""
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Return default config if file doesn't exist
        return get_default_config()


def save_indicator_config(config):
    """Save indicator configuration to JSON file."""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)


def get_default_config():
    """Get default indicator configuration."""
    return {
        "indicators": {
            "rsi": {"enabled": True, "weight": 0.15},
            "macd": {"enabled": True, "weight": 0.20},
            "bollinger": {"enabled": True, "weight": 0.15},
            "volume": {"enabled": True, "weight": 0.15},
            "trend": {"enabled": True, "weight": 0.15},
            "atr": {"enabled": True, "weight": 0.20},
            "adx": {"enabled": False, "weight": 0.10},
            "stochastic": {"enabled": False, "weight": 0.10}
        },
        "min_score": 60
    }


def set_indicators_from_list(indicator_list):
    """
    Enable specific indicators from a list.

    Args:
        indicator_list: List of indicator numbers or names
                       Examples: [1,2,3], ['rsi','macd'], 'all'
    """
    config = load_indicator_config()

    # Disable all first
    for ind in config['indicators']:
        config['indicators'][ind]['enabled'] = False

    # Enable selected
    if indicator_list == 'all':
        for ind in config['indicators']:
            config['indicators'][ind]['enabled'] = True
    else:
        indicator_names = list(config['indicators'].keys())

        for item in indicator_list:
            if isinstance(item, int):
                # Number-based selection (1-indexed)
                if 1 <= item <= len(indicator_names):
                    ind_name = indicator_names[item - 1]
                    config['indicators'][ind_name]['enabled'] = True
            elif isinstance(item, str):
                # Name-based selection
                if item.lower() in config['indicators']:
                    config['indicators'][item.lower()]['enabled'] = True

    # Normalize weights for enabled indicators
    enabled_weights = sum(
        ind['weight'] for ind in config['indicators'].values() if ind['enabled']
    )

    if enabled_weights > 0:
        for ind in config['indicators'].values():
            if ind['enabled']:
                ind['weight'] = ind['weight'] / enabled_weights

    save_indicator_config(config)
    return config


def get_enabled_indicators():
    """Get list of currently enabled indicators."""
    config = load_indicator_config()
    return [name for name, ind in config['indicators'].items() if ind['enabled']]


def generate_signal_v3(df, min_score=None):
    """
    Generate trading signal using configured indicators.

    Args:
        df: DataFrame with OHLCV data
        min_score: Minimum score threshold (uses config if None)

    Returns:
        tuple: (signal, score, details)
    """
    if df is None or df.empty or len(df) < 40:  # Reduced from 60 to 40
        return "HOLD", 0, {"error": "Insufficient data"}

    config = load_indicator_config()
    if min_score is None:
        min_score = config.get('min_score', 60)

    signals = []
    scores = []
    weights = []
    details = {}

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

    # 1. RSI
    if config['indicators']['rsi']['enabled']:
        rsi = calculate_rsi(df)
        current_rsi = safe_float(rsi.iloc[-1], 50)
        details['rsi'] = round(current_rsi, 2)

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

        weights.append(config['indicators']['rsi']['weight'])

    # 2. MACD
    if config['indicators']['macd']['enabled']:
        macd, macd_signal, macd_hist = calculate_macd(df)
        current_macd = safe_float(macd.iloc[-1], 0)
        current_macd_signal = safe_float(macd_signal.iloc[-1], 0)
        prev_macd = safe_float(macd.iloc[-2], 0)
        prev_macd_signal = safe_float(macd_signal.iloc[-2], 0)

        details['macd'] = round(current_macd, 4)
        details['macd_signal'] = round(current_macd_signal, 4)

        macd_bullish_cross = prev_macd < prev_macd_signal and current_macd > current_macd_signal
        macd_bearish_cross = prev_macd > prev_macd_signal and current_macd < current_macd_signal

        if macd_bullish_cross:
            signals.append("BUY")
            scores.append(85)
        elif current_macd > current_macd_signal:
            signals.append("BUY")
            scores.append(65)
        elif macd_bearish_cross:
            signals.append("SELL")
            scores.append(85)
        elif current_macd < current_macd_signal:
            signals.append("SELL")
            scores.append(65)
        else:
            signals.append("HOLD")
            scores.append(50)

        weights.append(config['indicators']['macd']['weight'])

    # 3. Bollinger Bands
    if config['indicators']['bollinger']['enabled']:
        bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(df)
        current_price = safe_float(df['Close'].iloc[-1])
        bb_upper_val = safe_float(bb_upper.iloc[-1])
        bb_lower_val = safe_float(bb_lower.iloc[-1])

        bb_position = (current_price - bb_lower_val) / (bb_upper_val - bb_lower_val) if bb_upper_val != bb_lower_val else 0.5
        details['bb_position'] = round(bb_position * 100, 2)

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

        weights.append(config['indicators']['bollinger']['weight'])

    # 4. Volume
    if config['indicators']['volume']['enabled']:
        volume_data = analyze_volume(df)
        details['volume_ratio'] = round(volume_data['volume_ratio'], 2)

        if volume_data['is_high_volume']:
            prev_price = safe_float(df['Close'].iloc[-2])
            current_price = safe_float(df['Close'].iloc[-1])
            if current_price > prev_price:
                signals.append("BUY")
                scores.append(70)
            else:
                signals.append("SELL")
                scores.append(70)
        else:
            signals.append("HOLD")
            scores.append(45)

        weights.append(config['indicators']['volume']['weight'])

    # 5. Trend Strength
    if config['indicators']['trend']['enabled']:
        trend_strength = calculate_trend_strength(df)
        details['trend_strength'] = round(trend_strength, 2)

        if trend_strength > 65:
            signals.append("BUY")
            scores.append(int(trend_strength))
        elif trend_strength < 35:
            signals.append("SELL")
            scores.append(int(100 - trend_strength))
        else:
            signals.append("HOLD")
            scores.append(50)

        weights.append(config['indicators']['trend']['weight'])

    # 6. ATR (Volatility)
    if config['indicators']['atr']['enabled']:
        volatility_data = analyze_volatility(df)
        details['volatility_ratio'] = volatility_data['volatility_ratio']
        details['volatility_category'] = volatility_data['category']
        details['atr_pct'] = volatility_data['atr_pct']

        volatility_score = volatility_data['score']
        volatility_signal = volatility_data['signal']

        if volatility_signal in ["AVOID", "CAUTION"]:
            signals.append("HOLD")
        else:
            signals.append("NEUTRAL")

        scores.append(volatility_score)
        weights.append(config['indicators']['atr']['weight'])

    # 7. ADX (Trend Strength Confirmation)
    if config['indicators']['adx']['enabled']:
        adx, plus_di, minus_di = calculate_adx(df)
        current_adx = safe_float(adx.iloc[-1], 20)
        current_plus_di = safe_float(plus_di.iloc[-1], 0)
        current_minus_di = safe_float(minus_di.iloc[-1], 0)

        details['adx'] = round(current_adx, 2)
        details['plus_di'] = round(current_plus_di, 2)
        details['minus_di'] = round(current_minus_di, 2)

        if current_adx > 25:  # Strong trend
            if current_plus_di > current_minus_di:
                signals.append("BUY")
                scores.append(75)
            else:
                signals.append("SELL")
                scores.append(75)
        elif current_adx < 20:  # Weak trend - favor mean reversion
            signals.append("HOLD")
            scores.append(45)
        else:
            signals.append("HOLD")
            scores.append(55)

        weights.append(config['indicators']['adx']['weight'])

    # 8. Stochastic
    if config['indicators']['stochastic']['enabled']:
        k, d = calculate_stochastic(df)
        current_k = safe_float(k.iloc[-1], 50)
        current_d = safe_float(d.iloc[-1], 50)
        prev_k = safe_float(k.iloc[-2], 50)
        prev_d = safe_float(d.iloc[-2], 50)

        details['stochastic_k'] = round(current_k, 2)
        details['stochastic_d'] = round(current_d, 2)

        # Bullish/Bearish crossovers
        bullish_cross = prev_k < prev_d and current_k > current_d and current_k < 20
        bearish_cross = prev_k > prev_d and current_k < current_d and current_k > 80

        if bullish_cross:
            signals.append("BUY")
            scores.append(80)
        elif current_k < 20:
            signals.append("BUY")
            scores.append(65)
        elif bearish_cross:
            signals.append("SELL")
            scores.append(80)
        elif current_k > 80:
            signals.append("SELL")
            scores.append(65)
        else:
            signals.append("HOLD")
            scores.append(50)

        weights.append(config['indicators']['stochastic']['weight'])

    # Calculate weighted score
    if not weights:
        return "HOLD", 0, {"error": "No indicators enabled"}

    total_score = sum(score * weight for score, weight in zip(scores, weights))

    # Determine final signal
    buy_count = signals.count("BUY")
    sell_count = signals.count("SELL")

    if buy_count > sell_count and total_score >= min_score:
        final_signal = "BUY"
    elif sell_count > buy_count and total_score >= min_score:
        final_signal = "SELL"
    else:
        final_signal = "HOLD"

    details['component_signals'] = signals
    details['component_scores'] = [round(s, 2) for s in scores]
    details['enabled_indicators'] = get_enabled_indicators()

    return final_signal, round(total_score, 2), details
