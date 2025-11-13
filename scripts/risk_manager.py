# scripts/risk_manager.py
import pandas as pd
import numpy as np

def calculate_atr(df, period=14):
    """
    Calculate Average True Range (ATR) for volatility-based position sizing.
    ATR = average of True Range over period.
    """
    high = df['High']
    low = df['Low']
    close = df['Close']

    # True Range = max of (high-low, abs(high-prev_close), abs(low-prev_close))
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()

    return atr.iloc[-1] if not atr.empty else 0


def calculate_position_size(price, atr, account_size=500000, risk_per_trade=0.02,
                            category='Unknown', category_allocation=None,
                            kelly_fraction=0.05, avg_category_atr=None):
    """
    Calculate position size using Kelly Criterion + Risk Parity (Volatility-adjusted).

    Formula: position_size = (kelly_fraction) × (category_allocation / n_positions) × (atr_adjustment)

    Logic:
    - Base size from Kelly Criterion (win rate optimization)
    - Adjusted by volatility (Risk Parity)
    - High ATR stocks get smaller positions
    - Low ATR stocks get larger positions

    Args:
        price: Current stock price
        atr: Average True Range (volatility measure)
        account_size: Total account size
        risk_per_trade: % of account to risk per trade (default 2%)
        category: Stock category (Large-cap/Mid-cap/Microcap)
        category_allocation: Total allocation for this category
        kelly_fraction: Kelly fraction (from backtesting, default 5%)
        avg_category_atr: Average ATR for this category (for normalization)

    Returns:
        tuple: (quantity, allocation_amount)
    """
    # Category-specific settings
    category_config = {
        'Large-cap': {
            'allocation': 300000,
            'max_positions': 6,
            'volatility_factor': 0.8
        },
        'Mid-cap': {
            'allocation': 100000,
            'max_positions': 5,
            'volatility_factor': 1.0
        },
        'Microcap': {
            'allocation': 100000,
            'max_positions': 8,
            'volatility_factor': 1.3
        }
    }

    # Get category config
    config = category_config.get(category, category_config['Mid-cap'])
    cat_allocation = category_allocation or config['allocation']
    max_positions = config['max_positions']
    vol_factor = config['volatility_factor']

    # Base position size from Kelly
    base_size = cat_allocation / max_positions

    # Risk Parity adjustment based on volatility
    if atr > 0 and avg_category_atr and avg_category_atr > 0:
        # Normalize ATR: if stock is more volatile than average, reduce position
        atr_ratio = atr / avg_category_atr
        volatility_adjustment = 1.0 / (atr_ratio * vol_factor)
    else:
        # Fallback to category volatility factor
        volatility_adjustment = 1.0 / vol_factor

    # Calculate final position size
    position_value = base_size * volatility_adjustment * kelly_fraction * 20  # Scale Kelly (5% → 100%)

    # Cap position size
    max_position = cat_allocation * 0.30  # No single position > 30% of category
    position_value = min(position_value, max_position)

    # Ensure minimum viable position
    min_position = price * 10  # At least 10 shares
    position_value = max(position_value, min_position)

    # Calculate shares
    shares = int(position_value / price)
    shares = max(1, shares)

    allocation = shares * price

    return shares, allocation


def calculate_dynamic_stops(price, atr, atr_multiplier_sl=2.0, atr_multiplier_tp=3.0, strategy='daily'):
    """
    Calculate stop-loss and take-profit based on ATR.

    Args:
        price: Current price
        atr: Average True Range
        atr_multiplier_sl: ATR multiplier for stop-loss (default 2.0)
        atr_multiplier_tp: ATR multiplier for take-profit (default 3.0)
        strategy: 'daily' or 'swing' (default 'daily')

    Returns:
        tuple: (stop_loss_price, take_profit_price)
    """
    if atr <= 0:
        # Fallback to percentage-based if ATR unavailable
        # Daily: 2% TP for faster exits, Swing: 10% TP for longer holds
        tp_pct = 1.02 if strategy == 'daily' else 1.10
        return price * 0.95, price * tp_pct

    stop_loss = round(price - (atr * atr_multiplier_sl), 2)

    # For daily trading, use tighter take profit (based on 2%)
    # For swing trading, use ATR-based take profit
    if strategy == 'daily':
        take_profit = round(price * 1.02, 2)  # Fixed 2% TP for daily
    else:
        take_profit = round(price + (atr * atr_multiplier_tp), 2)  # ATR-based for swing

    return stop_loss, take_profit


def calculate_smart_stops_swing(entry_price, current_price, highest_price, atr,
                                days_held, recent_low=None, strategy_config=None):
    """
    Calculate smart hybrid stop-loss for swing trading.
    Uses multiple stop methods and returns the tightest (most protective).

    Args:
        entry_price: Entry price
        current_price: Current market price
        highest_price: Highest price since entry
        atr: Average True Range (volatility measure)
        days_held: Number of days position has been held
        recent_low: Recent 5-day low price (optional)
        strategy_config: Dict with custom parameters (optional)

    Returns:
        dict: {
            'stop_loss': float (final stop price - highest of all methods),
            'take_profit': float,
            'method': str (which stop method is active),
            'all_stops': dict (all calculated stops for transparency)
        }
    """
    # Default configuration
    config = {
        'fixed_stop_pct': 0.04,        # 4% fixed stop (allows circuit breaker at 3% to take precedence)
        'atr_multiplier_sl': 2.0,      # ATR-based stop
        'chandelier_multiplier': 2.5,  # Chandelier trailing stop
        'support_buffer_pct': 0.02,    # 2% below support
        'max_days_no_progress': 10,    # Time-based exit
        'target_profit_pct': 0.04,     # 4% take profit
        'use_fixed': True,
        'use_atr': True,
        'use_chandelier': True,
        'use_support': True,
        'use_time_based': True
    }

    # Override with custom config if provided
    if strategy_config:
        config.update(strategy_config)

    all_stops = {}

    # Layer 1: Fixed Percentage Stop (Capital Protection)
    if config['use_fixed']:
        stop_fixed = round(entry_price * (1 - config['fixed_stop_pct']), 2)
        all_stops['fixed'] = stop_fixed

    # Layer 2: ATR-Based Dynamic Stop (Volatility-Adaptive)
    if config['use_atr'] and atr > 0:
        stop_atr = round(entry_price - (atr * config['atr_multiplier_sl']), 2)
        all_stops['atr'] = stop_atr

    # Layer 3: Chandelier Stop (Trailing from Highest)
    # This is the key professional stop - trails below highest price
    if config['use_chandelier'] and atr > 0:
        chandelier = round(highest_price - (atr * config['chandelier_multiplier']), 2)
        all_stops['chandelier'] = chandelier

    # Layer 4: Support-Based Stop (Technical Structure)
    if config['use_support'] and recent_low is not None:
        support_stop = round(recent_low * (1 - config['support_buffer_pct']), 2)
        all_stops['support'] = support_stop

    # Layer 5: Time-Based Exit Signal (Opportunity Cost)
    # If no profit after X days, flag for exit
    time_based_exit = False
    if config['use_time_based']:
        if days_held >= config['max_days_no_progress'] and current_price <= entry_price:
            time_based_exit = True
            all_stops['time_based'] = current_price  # Exit at market

    # Determine final stop: Use the HIGHEST (tightest/most protective) stop
    if all_stops:
        # Convert any Series to float before max()
        clean_stops = {k: float(v) if hasattr(v, 'item') else v for k, v in all_stops.items()}
        final_stop = max(clean_stops.values())
        # Find which method is active
        active_method = [k for k, v in clean_stops.items() if v == final_stop][0]
        all_stops = clean_stops
    else:
        # Fallback if no stops calculated
        final_stop = round(entry_price * 0.98, 2)
        active_method = 'fallback'
        all_stops['fallback'] = final_stop

    # Calculate Take Profit (fixed 4%)
    take_profit = round(entry_price * (1 + config['target_profit_pct']), 2)

    return {
        'stop_loss': final_stop,
        'take_profit': take_profit,
        'method': active_method,
        'all_stops': all_stops,
        'time_based_exit': time_based_exit,
        'days_held': days_held
    }


def check_portfolio_limits(portfolio, ticker, new_allocation, max_positions=19,
                           max_position_pct=0.30, total_capital=500000,
                           stock_category=None):
    """
    Check if adding a new position violates portfolio risk limits.

    Allocation Rules:
    - Large-cap: Max 60% of capital (₹300k), max 6 positions
    - Mid-cap: Max 20% of capital (₹100k), max 5 positions
    - Micro-cap: Max 20% of capital (₹100k), max 8 positions
    - Total: Max 19 positions across all categories

    Returns:
        tuple: (is_allowed: bool, reason: str)
    """
    # Category-specific position limits
    category_limits = {
        'Large-cap': {'max_positions': 6, 'allocation': 300000},
        'Mid-cap': {'max_positions': 5, 'allocation': 100000},
        'Microcap': {'max_positions': 8, 'allocation': 100000}
    }

    # Check total positions
    active_positions = len(portfolio[portfolio['Status'] == 'HOLD'])
    if active_positions >= max_positions and ticker not in portfolio['Ticker'].values:
        return False, f"Max total positions ({max_positions}) reached"

    # Check category-specific position limits
    if stock_category and stock_category in category_limits:
        category_positions = len(portfolio[
            (portfolio['Status'] == 'HOLD') &
            (portfolio['Category'] == stock_category)
        ])
        max_cat_positions = category_limits[stock_category]['max_positions']

        if category_positions >= max_cat_positions and ticker not in portfolio['Ticker'].values:
            return False, f"{stock_category} max positions ({max_cat_positions}) reached"

    # Check position concentration
    if new_allocation > (total_capital * max_position_pct):
        return False, f"Position exceeds {max_position_pct*100}% of capital"

    # Calculate total exposure by category
    current_exposure = 0
    category_exposure = {'Large-cap': 0, 'Mid-cap': 0, 'Microcap': 0}

    for _, row in portfolio.iterrows():
        if row['Status'] == 'HOLD':
            qty = float(row.get('Quantity', 0))
            entry = float(row.get('EntryPrice', 0))
            exposure = qty * entry
            current_exposure += exposure

            # Track by category if available
            row_category = row.get('Category', 'Unknown')
            if row_category in category_exposure:
                category_exposure[row_category] += exposure

    # Check category allocation limits (60/20/20 rule)
    if stock_category:
        category_limits = {
            'Large-cap': total_capital * 0.60,  # 60%
            'Mid-cap': total_capital * 0.20,    # 20%
            'Microcap': total_capital * 0.20    # 20%
        }

        if stock_category in category_limits:
            new_category_exposure = category_exposure[stock_category] + new_allocation
            limit = category_limits[stock_category]

            if new_category_exposure > limit:
                return False, f"{stock_category} allocation ({new_category_exposure:.0f}) exceeds {stock_category} limit ({limit:.0f})"

    total_exposure = current_exposure + new_allocation

    # Check total exposure limit (e.g., max 95% deployed)
    max_exposure = total_capital * 0.95
    if total_exposure > max_exposure:
        return False, f"Total exposure ({total_exposure:.0f}) exceeds limit ({max_exposure:.0f})"

    return True, "OK"


def calculate_position_metrics(portfolio, stock_data):
    """
    Calculate portfolio-level metrics for risk monitoring.

    Returns:
        dict: Portfolio metrics (total_value, exposure, position_count, etc.)
    """
    metrics = {
        'total_positions': 0,
        'total_exposure': 0,
        'total_unrealized_pnl': 0,
        'positions': []
    }

    for _, row in portfolio.iterrows():
        if row['Status'] != 'HOLD':
            continue

        ticker = row['Ticker']
        entry_price = float(row.get('EntryPrice', 0))
        qty = int(row.get('Quantity', 0))
        category = row.get('Category', 'Unknown')

        if ticker in stock_data and not stock_data[ticker].empty:
            price_value = stock_data[ticker]['Close'].iloc[-1]
            current_price = float(price_value.item() if hasattr(price_value, 'item') else price_value)
            exposure = qty * entry_price
            unrealized_pnl = (current_price - entry_price) * qty
            pnl_pct = (unrealized_pnl / exposure) * 100 if exposure > 0 else 0

            metrics['total_positions'] += 1
            metrics['total_exposure'] += exposure
            metrics['total_unrealized_pnl'] += unrealized_pnl

            metrics['positions'].append({
                'ticker': ticker,
                'entry': entry_price,
                'current': current_price,
                'qty': qty,
                'exposure': exposure,
                'pnl': unrealized_pnl,
                'pnl_pct': pnl_pct,
                'category': category
            })

    return metrics


def check_circuit_breaker(ticker, entry_price, current_price, entry_date,
                         alert_threshold=0.04, hard_stop=0.05):
    """
    Check if position triggers circuit breaker alerts

    Args:
        ticker: Stock ticker
        entry_price: Entry price
        current_price: Current price
        entry_date: Entry date
        alert_threshold: % loss to trigger alert (default 4%)
        hard_stop: % loss for hard circuit breaker (default 5%)

    Returns:
        action: 'HOLD', 'ALERT', or 'CIRCUIT_BREAKER'
        loss_pct: Current loss percentage
        analysis: Dictionary with risk analysis
    """
    import pandas as pd
    from datetime import datetime

    loss = (current_price - entry_price) / entry_price

    # Handle missing/invalid entry dates
    try:
        entry_dt = pd.to_datetime(entry_date)
        if pd.isna(entry_dt):
            days_held = 0
        else:
            days_held = (datetime.now().date() - entry_dt.date()).days
    except:
        days_held = 0

    analysis = {
        'ticker': ticker,
        'entry_price': entry_price,
        'current_price': current_price,
        'loss_pct': loss * 100,
        'days_held': days_held
    }

    # Circuit breaker - immediate exit
    if loss <= -hard_stop:
        return 'CIRCUIT_BREAKER', loss, analysis

    # Alert threshold - investigate
    if loss <= -alert_threshold:
        return 'ALERT', loss, analysis

    return 'HOLD', loss, analysis


def analyze_drop_reason(ticker, days_back=5):
    """
    Analyze why a stock is dropping using technical signals

    Returns:
        analysis: Dictionary with findings and recommendation
    """
    import yfinance as yf
    import numpy as np

    try:
        # Download recent data
        df = yf.download(ticker, period='1mo', interval='1d', progress=False)

        if df.empty:
            return {'error': 'No data available'}

        # Calculate metrics - use .item() to extract scalar values
        latest_close = df['Close'].iloc[-1].item() if hasattr(df['Close'].iloc[-1], 'item') else float(df['Close'].iloc[-1])
        prev_close = df['Close'].iloc[-2].item() if len(df) >= 2 and hasattr(df['Close'].iloc[-2], 'item') else latest_close
        week_ago = df['Close'].iloc[-5].item() if len(df) >= 5 and hasattr(df['Close'].iloc[-5], 'item') else df['Close'].iloc[0].item()

        daily_change = ((latest_close - prev_close) / prev_close) * 100
        weekly_change = ((latest_close - week_ago) / week_ago) * 100

        # Volume analysis
        avg_vol_series = df['Volume'].rolling(20).mean().iloc[-1]
        avg_volume = avg_vol_series.item() if hasattr(avg_vol_series, 'item') else float(avg_vol_series)
        recent_vol = df['Volume'].iloc[-1]
        recent_volume = recent_vol.item() if hasattr(recent_vol, 'item') else float(recent_vol)
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0

        # Volatility (ATR)
        atr_val = calculate_atr(df, period=14)
        atr = atr_val.item() if hasattr(atr_val, 'item') else float(atr_val)
        atr_pct = (atr / latest_close) * 100 if latest_close > 0 else 0.0

        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss_vals = (-delta.where(delta < 0, 0)).rolling(window=14).mean()

        # Avoid division by zero
        with np.errstate(divide='ignore', invalid='ignore'):
            rs = gain / loss_vals
            rsi = 100 - (100 / (1 + rs))

        # Extract RSI as scalar
        rsi_val = rsi.iloc[-1]
        # Check if it's a scalar or extract it first
        if hasattr(rsi_val, 'item'):
            rsi_scalar = rsi_val.item()
        else:
            rsi_scalar = float(rsi_val) if not pd.isna(rsi_val) else 50.0
        current_rsi = rsi_scalar if not pd.isna(rsi_scalar) else 50.0

        # Determine issues
        issues = []
        if daily_change < -3:
            issues.append(f"Sharp daily drop: {daily_change:.2f}%")
        if volume_ratio > 2:
            issues.append(f"High volume selloff: {volume_ratio:.1f}x avg")
        if current_rsi < 30:
            issues.append(f"Oversold RSI: {current_rsi:.1f}")
        if atr_pct > 3:
            issues.append(f"High volatility: {atr_pct:.2f}% ATR")

        # Recommendation based on technicals
        if current_rsi < 30 and daily_change < -5:
            recommendation = "POSSIBLE BOUNCE - Oversold, consider holding"
            action = "HOLD"
        elif volume_ratio > 3 and daily_change < -5:
            recommendation = "PANIC SELLING - High risk, consider exit"
            action = "EXIT"
        elif atr_pct > 5:
            recommendation = "EXTREME VOLATILITY - Exit and reassess"
            action = "EXIT"
        else:
            recommendation = "NORMAL CORRECTION - Monitor closely"
            action = "HOLD"

        return {
            'latest_price': latest_close,
            'daily_change_pct': daily_change,
            'weekly_change_pct': weekly_change,
            'volume_ratio': volume_ratio,
            'rsi': current_rsi,
            'atr_pct': atr_pct,
            'issues': issues,
            'recommendation': recommendation,
            'action': action
        }

    except Exception as e:
        import traceback
        return {'error': f"{str(e)}\n{traceback.format_exc()}"}


def format_alert_message(ticker, analysis, drop_analysis, ai_analysis=None):
    """Format Telegram alert message for 3% loss threshold with AI analysis"""

    msg = "🚨 *POSITION ALERT - 3% LOSS THRESHOLD*\n\n"
    msg += f"*Ticker:* {ticker}\n"
    msg += f"*Entry:* ₹{analysis['entry_price']:.2f}\n"
    msg += f"*Current:* ₹{analysis['current_price']:.2f}\n"
    msg += f"*Loss:* {analysis['loss_pct']:.2f}%\n"
    msg += f"*Days Held:* {analysis['days_held']}\n\n"

    # AI Analysis (if available)
    if ai_analysis and 'ai_recommendation' in ai_analysis:
        msg += "*🤖 AI ANALYSIS:*\n"
        msg += f"Recommendation: *{ai_analysis['ai_recommendation']}* ({ai_analysis['ai_confidence']} confidence)\n"
        msg += f"Reasoning: {ai_analysis['ai_reasoning']}\n\n"

        if ai_analysis.get('ai_key_factors'):
            msg += "*Key Factors:*\n"
            for factor in ai_analysis['ai_key_factors'][:3]:
                msg += f"• {factor}\n"
            msg += "\n"

        if ai_analysis.get('news_count', 0) > 0:
            msg += f"*📰 Recent News ({ai_analysis['news_count']} articles):*\n"
            for headline in ai_analysis.get('news_headlines', [])[:2]:
                msg += f"• {headline[:60]}...\n"
            msg += "\n"

    msg += "*📊 TECHNICAL ANALYSIS:*\n"

    if 'error' in drop_analysis:
        msg += f"⚠️ Error: {drop_analysis['error']}\n"
    else:
        msg += f"Daily Change: {drop_analysis['daily_change_pct']:.2f}%\n"
        msg += f"Weekly Change: {drop_analysis['weekly_change_pct']:.2f}%\n"
        msg += f"RSI: {drop_analysis['rsi']:.1f}\n"
        msg += f"Volume: {drop_analysis['volume_ratio']:.1f}x avg\n"
        msg += f"ATR: {drop_analysis['atr_pct']:.2f}%\n\n"

        if drop_analysis['issues']:
            msg += "*⚠️ ISSUES DETECTED:*\n"
            for issue in drop_analysis['issues']:
                msg += f"• {issue}\n"
            msg += "\n"

        msg += f"*💡 RECOMMENDATION:*\n{drop_analysis['recommendation']}\n\n"

    msg += "*🎮 YOU HAVE 3 CHOICES:*\n\n"
    msg += f"1️⃣ `/exit {ticker}` - Exit NOW at ~3% loss\n"
    msg += f"2️⃣ `/hold {ticker}` - Hold until 5% hard stop\n"
    msg += f"3️⃣ `/smart-stop {ticker}` - Let smart stops decide (ATR/Chandelier)\n\n"
    msg += "⚠️ *No reply = Circuit breaker at 5% will auto-exit*"

    return msg


def format_circuit_breaker_message(ticker, analysis):
    """Format circuit breaker message for 5% hard stop"""

    msg = "🔴 *CIRCUIT BREAKER TRIGGERED - AUTO EXIT*\n\n"
    msg += f"*Ticker:* {ticker}\n"
    msg += f"*Entry:* ₹{analysis['entry_price']:.2f}\n"
    msg += f"*Exit:* ₹{analysis['current_price']:.2f}\n"
    msg += f"*Loss:* {analysis['loss_pct']:.2f}%\n"
    msg += f"*Days Held:* {analysis['days_held']}\n\n"
    msg += "⛔ Position automatically closed at 5% hard stop.\n"
    msg += "Risk management protocol executed to prevent catastrophic loss."

    return msg
