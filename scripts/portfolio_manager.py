# scripts/portfolio_manager.py
import pandas as pd
from datetime import datetime
import os
from scripts.risk_manager import (
    calculate_atr, calculate_position_size,
    calculate_dynamic_stops, check_portfolio_limits
)
from scripts.performance_learner import (
    should_trade_stock, calculate_adaptive_position_multiplier
)

TRADES_FILE = "data/trades.csv"

# Stock categorization
STOCK_UNIVERSE = {
    'large_caps': [
        'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
        'BHARTIARTL.NS', 'SBIN.NS', 'BAJFINANCE.NS', 'ASIANPAINT.NS', 'MARUTI.NS',
        'TATASTEEL.NS', 'SUNPHARMA.NS', 'TITAN.NS', 'WIPRO.NS', 'TECHM.NS',
        'HCLTECH.NS', 'ULTRACEMCO.NS', 'AXISBANK.NS', 'LT.NS', 'KOTAKBANK.NS',
        'ITC.NS', 'HINDUNILVR.NS', 'POWERGRID.NS', 'NTPC.NS', 'ONGC.NS'
    ],
    'mid_caps': [
        'PERSISTENT.NS', 'COFORGE.NS', 'LTTS.NS', 'CYIENT.NS',
        'ZYDUSLIFE.NS', 'LALPATHLAB.NS', 'METROPOLIS.NS', 'THYROCARE.NS',
        'CROMPTON.NS', 'RELAXO.NS', 'VGUARD.NS', 'BATAINDIA.NS',
        'CHAMBLFERT.NS', 'APLAPOLLO.NS', 'CENTURYPLY.NS', 'BLUEDART.NS',
        'KAJARIACER.NS', 'GRINDWELL.NS', 'ORIENTCEM.NS', 'JKCEMENT.NS'
    ],
    'micro_caps': [
        'DIGISPICE.NS', 'RPPINFRA.NS', 'URJA.NS', 'PENINLAND.NS',
        'KELLTONTEC.NS', 'RAJRATAN.NS', 'WHEELS.NS', 'AARTIDRUGS.NS',
        'SUVEN.NS', 'BALRAMCHIN.NS', 'APLLTD.NS',
        'FLUOROCHEM.NS', 'FINEORG.NS', 'GALAXYSURF.NS', 'ROSSARI.NS',
        'NAVINFLUOR.NS', 'ALKYLAMINE.NS',
        'ASTRAMICRO.NS', 'RATNAMANI.NS', 'ELECON.NS', 'GREAVESCOT.NS',
        'GOCOLORS.NS', 'SMSLIFE.NS',
        'DCMSHRIRAM.NS', 'SHARDACROP.NS'
    ]
}

def get_stock_category(ticker):
    """Determine if ticker is Large-cap, Mid-cap, or Microcap."""
    if ticker in STOCK_UNIVERSE['large_caps']:
        return 'Large-cap'
    elif ticker in STOCK_UNIVERSE['mid_caps']:
        return 'Mid-cap'
    elif ticker in STOCK_UNIVERSE['micro_caps']:
        return 'Microcap'
    else:
        return 'Unknown'

def log_trade(ticker, signal, price, qty, notes="", pnl=None):
    """Append trade details to trades.csv."""
    trade = pd.DataFrame([{
        "Date": datetime.now().strftime("%Y-%m-%d"),
        "Ticker": ticker,
        "Signal": signal,
        "Price": price,
        "Quantity": qty,
        "PnL": pnl if pnl is not None else "",
        "Notes": notes
    }])

    if os.path.exists(TRADES_FILE):
        trade.to_csv(TRADES_FILE, mode="a", header=False, index=False)
    else:
        trade.to_csv(TRADES_FILE, mode="w", header=True, index=False)


def get_trading_capital():
    import json
    try:
        with open('data/capital_tracker.json') as f:
            cap = json.load(f)
        return cap['current_trading_capital']
    except:
        return 200000

def update_portfolio(portfolio, ticker, signal, df=None, account_size=None,
                     use_atr_sizing=True, max_positions=10, max_position_pct=0.20,
                     use_performance_learning=True, performance_lookback_days=90):
    """
    Update portfolio and log trades with advanced risk management.
    - ATR-based position sizing
    - Dynamic stop-loss/take-profit based on volatility
    - Portfolio exposure limits
    - Auto-exit if stop-loss or take-profit hit
    - Performance-based stock filtering and position sizing (NEW)
    """

    # Load current trading capital
    if account_size is None:
        account_size = get_trading_capital()

    # --- Ensure portfolio has correct columns ---
    required_cols = ["Ticker", "Status", "EntryPrice", "Quantity", "StopLoss", "TakeProfit", "Category"]
    for col in required_cols:
        if col not in portfolio.columns:
            portfolio[col] = pd.Series(dtype="object")

    # --- Extract current price ---
    if df is not None and not df.empty:
        if isinstance(df, pd.DataFrame):
            last_price = float(df["Close"].iloc[-1])
        elif isinstance(df, pd.Series):
            last_price = float(df.iloc[-1])
        else:
            last_price = float(df)
    else:
        print(f"⚠️ No price data for {ticker}, skipping...")
        return portfolio

    # --- Check existing positions (circuit breaker + SL/TP) ---
    for _, row in portfolio.iterrows():
        if row["Ticker"] == ticker and row["Status"] == "HOLD":
            entry_price = float(row["EntryPrice"])
            stop_loss = float(row["StopLoss"])
            take_profit = float(row["TakeProfit"])
            qty = int(row["Quantity"])
            entry_date = row.get("EntryDate", datetime.now().strftime('%Y-%m-%d'))

            # 🛡️ CIRCUIT BREAKER - Priority #1
            from scripts.risk_manager import check_circuit_breaker, analyze_drop_reason, format_alert_message, format_circuit_breaker_message
            from scripts.telegram_bot import send_telegram_message, check_if_position_on_hold

            pnl_pct = ((last_price - entry_price) / entry_price) * 100
            action, loss, analysis = check_circuit_breaker(
                ticker, entry_price, last_price, entry_date,
                alert_threshold=0.03, hard_stop=0.05  # Alert at 3% loss, hard stop at 5%
            )

            if action == 'CIRCUIT_BREAKER':
                print(f"🔴 CIRCUIT BREAKER: {ticker} | Loss: {pnl_pct:.2f}%")
                pnl = round((last_price - entry_price) * qty, 2)
                portfolio = portfolio[portfolio["Ticker"] != ticker]
                log_trade(ticker, "SELL", last_price, qty, "CIRCUIT-BREAKER", pnl=pnl)
                msg = format_circuit_breaker_message(ticker, analysis)
                send_telegram_message(msg)
                return portfolio

            elif action == 'ALERT':
                if not check_if_position_on_hold(ticker):
                    print(f"🚨 ALERT: {ticker} | Loss: {pnl_pct:.2f}% | Analyzing...")
                    drop_analysis = analyze_drop_reason(ticker)
                    try:
                        from scripts.ai_news_analyzer import get_ai_recommendation
                        ai_analysis = get_ai_recommendation(ticker, drop_analysis, entry_price, last_price, pnl_pct)
                    except:
                        ai_analysis = None
                    msg = format_alert_message(ticker, analysis, drop_analysis, ai_analysis)
                    send_telegram_message(msg)
                    print(f"   📱 AI: {ai_analysis.get('ai_recommendation', 'N/A') if ai_analysis else 'N/A'}")

            # Check if stop-loss hit
            if last_price <= stop_loss:
                pnl = round((last_price - entry_price) * qty, 2)
                portfolio = portfolio[portfolio["Ticker"] != ticker]
                log_trade(ticker, "SELL", last_price, qty, f"Stop-loss hit at {stop_loss:.2f}", pnl=pnl)
                print(f"🛑 Stop-loss triggered for {ticker} at ₹{last_price:.2f} | PnL: ₹{pnl}")
                return portfolio

            # Check if take-profit hit
            if last_price >= take_profit:
                pnl = round((last_price - entry_price) * qty, 2)
                portfolio = portfolio[portfolio["Ticker"] != ticker]
                log_trade(ticker, "SELL", last_price, qty, f"Take-profit hit at {take_profit:.2f}", pnl=pnl)
                print(f"🎯 Take-profit triggered for {ticker} at ₹{last_price:.2f} | PnL: ₹{pnl}")
                return portfolio

    # BUY logic with Kelly + Risk Parity sizing
    if signal == "BUY" and ticker not in portfolio["Ticker"].values:
        # --- PERFORMANCE LEARNING: Check if we should trade this stock ---
        if use_performance_learning:
            should_trade, reason, perf_metrics = should_trade_stock(
                ticker,
                lookback_days=performance_lookback_days
            )

            if not should_trade:
                print(f"🚫 Skipping {ticker} due to poor historical performance: {reason}")
                print(f"   Win Rate: {perf_metrics['win_rate']*100:.1f}% | "
                      f"Performance Score: {perf_metrics['performance_score']:.1f} | "
                      f"Total P&L: ₹{perf_metrics['total_pnl']:.0f}")
                return portfolio

            # Print performance info if available
            if perf_metrics['trade_count'] >= 3:
                print(f"✅ {ticker} performance check passed: {reason}")
                print(f"   Win Rate: {perf_metrics['win_rate']*100:.1f}% | "
                      f"Score: {perf_metrics['performance_score']:.1f} | "
                      f"Trades: {perf_metrics['trade_count']}")

        # Get stock category first
        category = get_stock_category(ticker)

        # Calculate ATR for volatility-based sizing
        atr = calculate_atr(df) if use_atr_sizing and df is not None else 0

        # Calculate position size with Kelly + Risk Parity
        if use_atr_sizing and atr > 0:
            # TODO: Calculate average category ATR from current portfolio
            # For now, use estimated averages
            avg_category_atr_map = {
                'Large-cap': 25.0,   # Lower volatility
                'Mid-cap': 45.0,     # Medium volatility
                'Microcap': 65.0     # Higher volatility
            }
            avg_cat_atr = avg_category_atr_map.get(category, 45.0)

            qty, allocation = calculate_position_size(
                price=last_price,
                atr=atr,
                account_size=account_size,
                risk_per_trade=0.02,
                category=category,
                kelly_fraction=0.05,  # Conservative 5% (from analysis)
                avg_category_atr=avg_cat_atr
            )

            # --- ADAPTIVE POSITION SIZING: Adjust based on historical performance ---
            if use_performance_learning:
                performance_multiplier = calculate_adaptive_position_multiplier(
                    ticker,
                    lookback_days=performance_lookback_days
                )
                if performance_multiplier != 1.0:
                    original_qty = qty
                    qty = max(1, int(qty * performance_multiplier))
                    allocation = qty * last_price
                    print(f"📊 Adjusted position size by {performance_multiplier}x: {original_qty} → {qty} shares")

            stop_loss_price, take_profit_price = calculate_dynamic_stops(last_price, atr, strategy='daily')
        else:
            # Fallback to category-based allocation
            category_allocations = {
                'Large-cap': 50000,
                'Mid-cap': 20000,
                'Microcap': 12500
            }
            allocation = category_allocations.get(category, 20000)
            qty = max(1, int(allocation // last_price))
            stop_loss_price = round(last_price * 0.95, 2)
            take_profit_price = round(last_price * 1.02, 2)  # 2% TP for daily strategy

        # Check portfolio limits before buying
        is_allowed, reason = check_portfolio_limits(
            portfolio, ticker, allocation,
            max_positions=max_positions,
            max_position_pct=max_position_pct,
            total_capital=account_size,
            stock_category=category
        )

        if not is_allowed:
            print(f"⛔ Cannot buy {ticker}: {reason}")
            return portfolio

        new_row = pd.DataFrame([{
            "Ticker": ticker,
            "Status": "HOLD",
            "EntryPrice": last_price,
            "Quantity": qty,
            "StopLoss": stop_loss_price,
            "TakeProfit": take_profit_price,
            "Category": category
        }])
        portfolio = pd.concat([portfolio, new_row], ignore_index=True)

        atr_info = f"ATR: {atr:.2f} | " if use_atr_sizing and atr > 0 else ""
        log_trade(ticker, "BUY", last_price, qty,
                 f"New buy | {atr_info}SL: ₹{stop_loss_price} | TP: ₹{take_profit_price}")
        print(f"✅ Bought {ticker}: Qty {qty} @ ₹{last_price:.2f} | {atr_info}SL ₹{stop_loss_price} | TP ₹{take_profit_price}")

    # SELL logic
    elif signal == "SELL":
        if ticker in portfolio["Ticker"].values:
            entry_price = float(portfolio.loc[portfolio["Ticker"] == ticker, "EntryPrice"].iloc[0])
            qty = int(portfolio.loc[portfolio["Ticker"] == ticker, "Quantity"].iloc[0])
            pnl = round((last_price - entry_price) * qty, 2)

            # Remove from portfolio
            portfolio = portfolio[portfolio["Ticker"] != ticker]

            log_trade(ticker, "SELL", last_price, qty, "Sell signal triggered", pnl=pnl)
            print(f"📉 Sold {ticker} at ₹{last_price:.2f} | PnL: ₹{pnl}")

    return portfolio
