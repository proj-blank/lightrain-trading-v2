#!/usr/bin/env python3
"""
EOD (End of Day) Summary - Runs at 3:30 PM IST daily
Provides comprehensive daily performance summary with benchmark comparison
"""

import os
import sys
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add trading path
sys.path.insert(0, '/home/ubuntu/trading')

from scripts.db_connection import get_db_cursor
from scripts.telegram_bot import send_telegram_message


def create_eod_history_table():
    """Create table for storing EOD historical data"""
    with get_db_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS eod_history (
                id SERIAL PRIMARY KEY,
                snapshot_date DATE NOT NULL,
                snapshot_time TIME NOT NULL,

                -- Daily strategy metrics
                daily_positions INTEGER DEFAULT 0,
                daily_today_pnl DECIMAL(15, 2) DEFAULT 0,
                daily_today_pnl_pct DECIMAL(10, 4) DEFAULT 0,
                daily_portfolio_value DECIMAL(15, 2) DEFAULT 0,

                -- Swing strategy metrics
                swing_positions INTEGER DEFAULT 0,
                swing_today_pnl DECIMAL(15, 2) DEFAULT 0,
                swing_today_pnl_pct DECIMAL(10, 4) DEFAULT 0,
                swing_portfolio_value DECIMAL(15, 2) DEFAULT 0,

                -- Combined metrics
                total_positions INTEGER DEFAULT 0,
                total_today_pnl DECIMAL(15, 2) DEFAULT 0,
                total_today_pnl_pct DECIMAL(10, 4) DEFAULT 0,
                total_portfolio_value DECIMAL(15, 2) DEFAULT 0,
                capital_utilization_pct DECIMAL(10, 4) DEFAULT 0,
                cash_idle DECIMAL(15, 2) DEFAULT 0,

                -- Benchmark performance
                nifty50_change_pct DECIMAL(10, 4) DEFAULT 0,
                nifty50_price DECIMAL(15, 2) DEFAULT 0,
                weighted_benchmark_pct DECIMAL(10, 4) DEFAULT 0,
                outperformance_pct DECIMAL(10, 4) DEFAULT 0,

                -- Category benchmarks
                nifty_large_pct DECIMAL(10, 4) DEFAULT 0,
                nifty_mid_pct DECIMAL(10, 4) DEFAULT 0,
                nifty_small_pct DECIMAL(10, 4) DEFAULT 0,

                -- Global benchmarks
                sp500_pct DECIMAL(10, 4) DEFAULT 0,
                nasdaq_pct DECIMAL(10, 4) DEFAULT 0,
                nikkei_pct DECIMAL(10, 4) DEFAULT 0,
                hangseng_pct DECIMAL(10, 4) DEFAULT 0,
                vix_pct DECIMAL(10, 4) DEFAULT 0,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(snapshot_date, snapshot_time)
            );

            CREATE INDEX IF NOT EXISTS idx_eod_history_date ON eod_history(snapshot_date DESC);
        """)
        print("✓ EOD history table created/verified")


def save_eod_to_database(summary_data):
    """Save EOD summary to database for historical tracking"""
    with get_db_cursor() as cur:
        cur.execute("""
            INSERT INTO eod_history (
                snapshot_date, snapshot_time,
                daily_positions, daily_today_pnl, daily_today_pnl_pct, daily_portfolio_value,
                swing_positions, swing_today_pnl, swing_today_pnl_pct, swing_portfolio_value,
                total_positions, total_today_pnl, total_today_pnl_pct, total_portfolio_value,
                capital_utilization_pct, cash_idle,
                nifty50_change_pct, nifty50_price,
                weighted_benchmark_pct, outperformance_pct,
                nifty_large_pct, nifty_mid_pct, nifty_small_pct,
                sp500_pct, nasdaq_pct, nikkei_pct, hangseng_pct, vix_pct
            ) VALUES (
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            ON CONFLICT (snapshot_date, snapshot_time) DO UPDATE SET
                daily_positions = EXCLUDED.daily_positions,
                daily_today_pnl = EXCLUDED.daily_today_pnl,
                daily_today_pnl_pct = EXCLUDED.daily_today_pnl_pct,
                daily_portfolio_value = EXCLUDED.daily_portfolio_value,
                swing_positions = EXCLUDED.swing_positions,
                swing_today_pnl = EXCLUDED.swing_today_pnl,
                swing_today_pnl_pct = EXCLUDED.swing_today_pnl_pct,
                swing_portfolio_value = EXCLUDED.swing_portfolio_value,
                total_positions = EXCLUDED.total_positions,
                total_today_pnl = EXCLUDED.total_today_pnl,
                total_today_pnl_pct = EXCLUDED.total_today_pnl_pct,
                total_portfolio_value = EXCLUDED.total_portfolio_value,
                capital_utilization_pct = EXCLUDED.capital_utilization_pct,
                cash_idle = EXCLUDED.cash_idle,
                nifty50_change_pct = EXCLUDED.nifty50_change_pct,
                nifty50_price = EXCLUDED.nifty50_price,
                weighted_benchmark_pct = EXCLUDED.weighted_benchmark_pct,
                outperformance_pct = EXCLUDED.outperformance_pct,
                nifty_large_pct = EXCLUDED.nifty_large_pct,
                nifty_mid_pct = EXCLUDED.nifty_mid_pct,
                nifty_small_pct = EXCLUDED.nifty_small_pct,
                sp500_pct = EXCLUDED.sp500_pct,
                nasdaq_pct = EXCLUDED.nasdaq_pct,
                nikkei_pct = EXCLUDED.nikkei_pct,
                hangseng_pct = EXCLUDED.hangseng_pct,
                vix_pct = EXCLUDED.vix_pct
        """, (
            summary_data['snapshot_date'], summary_data['snapshot_time'],
            summary_data['daily_positions'], summary_data['daily_today_pnl'],
            summary_data['daily_today_pnl_pct'], summary_data['daily_portfolio_value'],
            summary_data['swing_positions'], summary_data['swing_today_pnl'],
            summary_data['swing_today_pnl_pct'], summary_data['swing_portfolio_value'],
            summary_data['total_positions'], summary_data['total_today_pnl'],
            summary_data['total_today_pnl_pct'], summary_data['total_portfolio_value'],
            summary_data['capital_utilization_pct'], summary_data['cash_idle'],
            summary_data['nifty50_change_pct'], summary_data['nifty50_price'],
            summary_data['weighted_benchmark_pct'], summary_data['outperformance_pct'],
            summary_data['nifty_large_pct'], summary_data['nifty_mid_pct'], summary_data['nifty_small_pct'],
            summary_data['sp500_pct'], summary_data['nasdaq_pct'],
            summary_data['nikkei_pct'], summary_data['hangseng_pct'], summary_data['vix_pct']
        ))
        print("✓ EOD summary saved to database")


def get_nifty_performance():
    """Get Nifty 50 performance for today"""
    try:
        nifty = yf.download('^NSEI', period='5d', interval='1d', progress=False)
        if len(nifty) >= 2:
            today_close = float(nifty['Close'].iloc[-1])
            yesterday_close = float(nifty['Close'].iloc[-2])
            pct_change = ((today_close - yesterday_close) / yesterday_close) * 100
            return pct_change, today_close
        return 0.0, 0.0
    except Exception as e:
        print(f"Error fetching Nifty data: {e}")
        return 0.0, 0.0


def get_global_benchmarks():
    """Get global market performance for today"""
    benchmarks = {
        'S&P 500': '^GSPC',
        'NASDAQ': '^IXIC',
        'Nikkei 225': '^N225',
        'Hang Seng': '^HSI',
        'VIX': '^VIX'
    }

    results = {}

    for name, symbol in benchmarks.items():
        try:
            df = yf.download(symbol, period='5d', interval='1d', progress=False)
            if len(df) >= 2:
                today_close = float(df['Close'].iloc[-1])
                yesterday_close = float(df['Close'].iloc[-2])
                pct_change = ((today_close - yesterday_close) / yesterday_close) * 100
                results[name] = {
                    'change_pct': pct_change,
                    'price': today_close
                }
            else:
                results[name] = {'change_pct': 0.0, 'price': 0.0}
        except Exception as e:
            print(f"Error fetching {name} data: {e}")
            results[name] = {'change_pct': 0.0, 'price': 0.0}

    return results


def get_category_benchmarks():
    """Get category-specific NSE index performance"""
    benchmarks = {
        'Nifty 50 (Large)': '^NSEI',
        'Nifty Midcap 150': '^NSEMDCP150',
        'Nifty Smallcap 250': '^NSESMLCAP250'
    }

    results = {}

    for name, symbol in benchmarks.items():
        try:
            df = yf.download(symbol, period='5d', interval='1d', progress=False)
            if len(df) >= 2:
                today_close = float(df['Close'].iloc[-1])
                yesterday_close = float(df['Close'].iloc[-2])
                pct_change = ((today_close - yesterday_close) / yesterday_close) * 100
                results[name] = {
                    'change_pct': pct_change,
                    'price': today_close
                }
            else:
                results[name] = {'change_pct': 0.0, 'price': 0.0}
        except Exception as e:
            print(f"Error fetching {name} data: {e}")
            results[name] = {'change_pct': 0.0, 'price': 0.0}

    return results


def calculate_weighted_benchmark(category_benchmarks, positions_data):
    """Calculate weighted benchmark based on portfolio allocation"""
    if not positions_data:
        return 0.0

    # Calculate total value per category
    category_values = {'Large-cap': 0.0, 'Mid-cap': 0.0, 'Microcap': 0.0}

    for pos in positions_data:
        category = pos.get('category', 'Unknown')
        category_values[category] = category_values.get(category, 0.0) + pos['current_value']

    total_value = sum(category_values.values())

    if total_value == 0:
        return 0.0

    # Calculate weighted benchmark return
    weighted_return = 0.0

    # Map categories to benchmark keys
    benchmark_map = {
        'Large-cap': 'Nifty 50 (Large)',
        'Mid-cap': 'Nifty Midcap 150',
        'Microcap': 'Nifty Smallcap 250'
    }

    for category, value in category_values.items():
        if value > 0 and category in benchmark_map:
            weight = value / total_value
            benchmark_key = benchmark_map[category]
            if benchmark_key in category_benchmarks:
                weighted_return += weight * category_benchmarks[benchmark_key]['change_pct']

    return weighted_return


def get_strategy_positions(strategy):
    """Get all active positions for a strategy"""
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT ticker, entry_price, quantity, entry_date, category,
                   stop_loss, take_profit
            FROM positions
            WHERE strategy = %s AND status = 'HOLD'
            ORDER BY entry_date DESC
        """, (strategy,))

        positions = []
        for row in cur.fetchall():
            positions.append({
                'ticker': row['ticker'],
                'entry_price': float(row['entry_price']),
                'quantity': int(row['quantity']),
                'entry_date': row['entry_date'],
                'category': row['category'],
                'stop_loss': float(row['stop_loss']) if row['stop_loss'] else None,
                'take_profit': float(row['take_profit']) if row['take_profit'] else None
            })

        return positions


def calculate_position_pnl(position):
    """Calculate P&L for a single position"""
    try:
        ticker = position['ticker']
        df = yf.download(ticker, period='5d', interval='1d', progress=False)

        if df.empty or len(df) < 2:
            return None

        # Get today's close and yesterday's close
        # Handle both scalar and Series returns from yfinance
        close_val = df['Close'].iloc[-1]
        today_close = float(close_val.item() if hasattr(close_val, 'item') else close_val)

        # Try to get opening price from today
        if 'Open' in df.columns:
            open_val = df['Open'].iloc[-1]
            # Check if it's a valid value (not NaN)
            if hasattr(open_val, 'item'):
                open_val = open_val.item()
            if not pd.isna(open_val):
                today_open = float(open_val)
            else:
                # Fallback to yesterday's close
                close_yesterday = df['Close'].iloc[-2]
                today_open = float(close_yesterday.item() if hasattr(close_yesterday, 'item') else close_yesterday)
        else:
            # Fallback to yesterday's close
            close_yesterday = df['Close'].iloc[-2]
            today_open = float(close_yesterday.item() if hasattr(close_yesterday, 'item') else close_yesterday)

        entry_price = position['entry_price']
        quantity = position['quantity']

        # Calculate P&L
        current_value = today_close * quantity
        invested_value = entry_price * quantity
        total_pnl = current_value - invested_value
        total_pnl_pct = (total_pnl / invested_value) * 100

        # Calculate today's P&L (from today's open to close)
        today_pnl = (today_close - today_open) * quantity
        today_pnl_pct = ((today_close - today_open) / today_open) * 100

        return {
            'ticker': ticker,
            'current_price': today_close,
            'entry_price': entry_price,
            'quantity': quantity,
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'today_pnl': today_pnl,
            'today_pnl_pct': today_pnl_pct,
            'current_value': current_value,
            'category': position['category']
        }

    except Exception as e:
        print(f"Error calculating P&L for {position['ticker']}: {e}")
        return None


def format_strategy_summary(strategy, positions_data, nifty_change):
    """Format summary for a single strategy"""

    if not positions_data:
        return f"\n🎯 **{strategy} STRATEGY**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nNo active positions\n"

    # Calculate today's P&L
    total_today_pnl = sum(p['today_pnl'] for p in positions_data)
    total_value = sum(p['current_value'] for p in positions_data)
    total_invested = sum(p['entry_price'] * p['quantity'] for p in positions_data)
    today_pnl_pct = (total_today_pnl / total_invested) * 100 if total_invested > 0 else 0

    # Calculate total unrealized P&L
    total_unrealized_pnl = sum(p['total_pnl'] for p in positions_data)
    total_unrealized_pct = (total_unrealized_pnl / total_invested) * 100 if total_invested > 0 else 0

    # Performance vs Nifty (for today)
    outperformance = today_pnl_pct - nifty_change
    performance_emoji = "✅" if outperformance > 0 else "❌" if outperformance < -0.1 else "➖"

    message = f"\n🎯 **{strategy} STRATEGY**\n"
    message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

    # Today's Performance
    message += f"📊 **Today's Performance:**\n"
    message += f"  P&L: ₹{total_today_pnl:,.0f} ({today_pnl_pct:+.2f}%)\n"
    message += f"  vs Nifty Today: {nifty_change:+.2f}%\n"
    message += f"  Status: {performance_emoji} "

    if abs(outperformance) < 0.1:
        message += f"IN LINE ({outperformance:+.2f}%)\n"
    elif outperformance > 0:
        message += f"OUTPERFORMING ({outperformance:+.2f}%)\n"
    else:
        message += f"UNDERPERFORMING ({outperformance:+.2f}%)\n"

    # Total Unrealized P&L
    unrealized_emoji = "🟢" if total_unrealized_pnl >= 0 else "🔴"
    message += f"\n💰 **Total Unrealized P&L:**\n"
    message += f"  {unrealized_emoji} ₹{total_unrealized_pnl:,.0f} ({total_unrealized_pct:+.2f}%)\n"
    message += f"  Portfolio Value: ₹{total_value:,.0f}\n"
    message += f"  Invested: ₹{total_invested:,.0f}\n"

    # Get locked profits and losses from capital tracker
    from scripts.db_connection import get_db_cursor
    with get_db_cursor() as cur:
        cur.execute("SELECT total_profits_locked, total_losses FROM capital_tracker WHERE strategy = %s", (strategy,))
        cap_row = cur.fetchone()
        locked_profits = float(cap_row['total_profits_locked']) if cap_row else 0
        total_losses = float(cap_row['total_losses']) if cap_row else 0
    
    realized_pnl = locked_profits - total_losses
    realized_emoji = "🟢" if realized_pnl >= 0 else "🔴"
    
    message += f"\n💎 **Locked Profits (Realized):**\n"
    message += f"  Profits: ₹{locked_profits:,.0f}\n"
    message += f"  Losses: ₹{total_losses:,.0f}\n"
    message += f"  {realized_emoji} Net Realized: ₹{realized_pnl:,.0f}\n"
    
    # Grand Total P&L
    grand_total_pnl = total_unrealized_pnl + realized_pnl
    grand_emoji = "🟢" if grand_total_pnl >= 0 else "🔴"
    message += f"\n🎯 **TOTAL P&L (Unrealized + Realized):**\n"
    message += f"  {grand_emoji} ₹{grand_total_pnl:,.0f}\n"

    # Sort by today's P&L
    winners = sorted([p for p in positions_data if p['today_pnl'] > 0],
                     key=lambda x: x['today_pnl'], reverse=True)
    losers = sorted([p for p in positions_data if p['today_pnl'] < 0],
                    key=lambda x: x['today_pnl'])

    # Winners
    if winners:
        message += f"\n**Winners ({len(winners)}):**\n"
        for p in winners[:5]:  # Top 5
            message += f"  {p['ticker']}: ₹{p['today_pnl']:+,.0f} ({p['today_pnl_pct']:+.1f}%)\n"

    # Losers
    if losers:
        message += f"\n**Losers ({len(losers)}):**\n"
        for p in losers[:5]:  # Top 5
            message += f"  {p['ticker']}: ₹{p['today_pnl']:+,.0f} ({p['today_pnl_pct']:+.1f}%)\n"

    return message


def generate_eod_summary():
    """Generate complete EOD summary"""

    print(f"\n{'='*70}")
    print(f"📊 END OF DAY SUMMARY - {datetime.now().strftime('%d %b %Y, %H:%M')}")
    print(f"{'='*70}\n")

    # Create table if not exists
    create_eod_history_table()

    # Get Nifty performance
    nifty_change, nifty_price = get_nifty_performance()

    # Get global benchmarks
    global_benchmarks = get_global_benchmarks()

    # Get category-specific benchmarks
    category_benchmarks = get_category_benchmarks()

    # Get positions for both strategies
    daily_positions = get_strategy_positions('DAILY')
    swing_positions = get_strategy_positions('SWING')

    print(f"Active positions: Daily={len(daily_positions)}, Swing={len(swing_positions)}")

    # Calculate P&L for all positions
    daily_data = []
    for pos in daily_positions:
        pnl = calculate_position_pnl(pos)
        if pnl:
            daily_data.append(pnl)

    swing_data = []
    for pos in swing_positions:
        pnl = calculate_position_pnl(pos)
        if pnl:
            swing_data.append(pnl)

    # Format message
    message = f"📊 **END OF DAY SUMMARY**\n"
    message += f"📅 {datetime.now().strftime('%d %b %Y, %H:%M')}\n"
    message += "=" * 40 + "\n"

    # Daily strategy
    message += format_strategy_summary("DAILY", daily_data, nifty_change)

    # Swing strategy
    message += format_strategy_summary("SWING", swing_data, nifty_change)

    # Combined summary
    if daily_data or swing_data:
        all_data = daily_data + swing_data
        total_today_pnl = sum(p['today_pnl'] for p in all_data)
        total_value = sum(p['current_value'] for p in all_data)
        total_invested = sum(p['entry_price'] * p['quantity'] for p in all_data)

        combined_pnl_pct = (total_today_pnl / total_invested) * 100 if total_invested > 0 else 0

        # Calculate utilization using actual capital from database
        from scripts.db_connection import get_capital
        daily_cap = get_capital('DAILY')
        swing_cap = get_capital('SWING')
        TOTAL_CAPITAL = float(daily_cap['current_trading_capital']) + float(swing_cap['current_trading_capital'])

        utilization = (total_invested / TOTAL_CAPITAL) * 100 if TOTAL_CAPITAL > 0 else 0
        cash_idle = TOTAL_CAPITAL - total_invested

        message += f"\n💰 **COMBINED**\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        message += f"Total P&L Today: ₹{total_today_pnl:+,.0f} ({combined_pnl_pct:+.2f}%)\n"
        message += f"Total Portfolio: ₹{total_value:,.0f}\n"
        message += f"Capital Utilization: {utilization:.1f}%"

        if utilization < 85:
            message += f" ⚠️\n"
            message += f"Cash Idle: ₹{cash_idle:,.0f}\n"
        else:
            message += f" ✅\n"

        message += f"\n📊 Nifty 50: {nifty_price:,.2f} ({nifty_change:+.2f}%)\n"

        # Add category-specific benchmarks
        all_data = daily_data + swing_data
        weighted_benchmark = calculate_weighted_benchmark(category_benchmarks, all_data)

        message += f"\n📈 **CATEGORY BENCHMARKS (Your Portfolio Mix)**\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

        for benchmark_name, data in category_benchmarks.items():
            change_pct = data['change_pct']

            # Show emoji based on performance
            if change_pct > 0:
                emoji = "🟢"
            elif change_pct < 0:
                emoji = "🔴"
            else:
                emoji = "⚪"

            message += f"{emoji} {benchmark_name}: {change_pct:+.2f}%\n"

        # Show weighted benchmark
        message += f"\n💫 Weighted Benchmark: {weighted_benchmark:+.2f}%\n"
        outperformance_weighted = combined_pnl_pct - weighted_benchmark

        if abs(outperformance_weighted) < 0.1:
            message += f"Your Performance: In Line ({outperformance_weighted:+.2f}%)\n"
        elif outperformance_weighted > 0:
            message += f"Your Performance: ✅ +{outperformance_weighted:.2f}% better\n"
        else:
            message += f"Your Performance: ❌ {outperformance_weighted:.2f}% worse\n"

        # Add global benchmarks comparison
        message += f"\n🌍 **GLOBAL BENCHMARKS**\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

        for benchmark_name, data in global_benchmarks.items():
            change_pct = data['change_pct']
            price = data['price']

            # Show emoji based on performance
            if change_pct > 0:
                emoji = "🟢"
            elif change_pct < 0:
                emoji = "🔴"
            else:
                emoji = "⚪"

            # Compare portfolio vs this benchmark
            outperformance = combined_pnl_pct - change_pct

            message += f"{emoji} {benchmark_name}: {change_pct:+.2f}%"

            # Show if portfolio beat this benchmark
            if abs(outperformance) < 0.1:
                message += f" (In Line)\n"
            elif outperformance > 0:
                message += f" (You: {outperformance:+.2f}% better ✅)\n"
            else:
                message += f" (You: {outperformance:+.2f}% worse)\n"

    message += "\n" + "=" * 40

    # Save to database for historical tracking
    if daily_data or swing_data:
        # Calculate strategy-specific metrics
        daily_today_pnl = sum(p['today_pnl'] for p in daily_data) if daily_data else 0
        daily_portfolio_value = sum(p['current_value'] for p in daily_data) if daily_data else 0
        daily_invested = sum(p['entry_price'] * p['quantity'] for p in daily_data) if daily_data else 0
        daily_today_pnl_pct = (daily_today_pnl / daily_invested * 100) if daily_invested > 0 else 0

        swing_today_pnl = sum(p['today_pnl'] for p in swing_data) if swing_data else 0
        swing_portfolio_value = sum(p['current_value'] for p in swing_data) if swing_data else 0
        swing_invested = sum(p['entry_price'] * p['quantity'] for p in swing_data) if swing_data else 0
        swing_today_pnl_pct = (swing_today_pnl / swing_invested * 100) if swing_invested > 0 else 0

        summary_data = {
            'snapshot_date': datetime.now().date(),
            'snapshot_time': datetime.now().time(),
            'daily_positions': len(daily_data),
            'daily_today_pnl': daily_today_pnl,
            'daily_today_pnl_pct': daily_today_pnl_pct,
            'daily_portfolio_value': daily_portfolio_value,
            'swing_positions': len(swing_data),
            'swing_today_pnl': swing_today_pnl,
            'swing_today_pnl_pct': swing_today_pnl_pct,
            'swing_portfolio_value': swing_portfolio_value,
            'total_positions': len(all_data),
            'total_today_pnl': total_today_pnl,
            'total_today_pnl_pct': combined_pnl_pct,
            'total_portfolio_value': total_value,
            'capital_utilization_pct': utilization,
            'cash_idle': cash_idle,
            'nifty50_change_pct': nifty_change,
            'nifty50_price': nifty_price,
            'weighted_benchmark_pct': weighted_benchmark,
            'outperformance_pct': outperformance_weighted,
            'nifty_large_pct': category_benchmarks.get('Nifty 50 (Large)', {}).get('change_pct', 0),
            'nifty_mid_pct': category_benchmarks.get('Nifty Midcap 150', {}).get('change_pct', 0),
            'nifty_small_pct': category_benchmarks.get('Nifty Smallcap 250', {}).get('change_pct', 0),
            'sp500_pct': global_benchmarks.get('S&P 500', {}).get('change_pct', 0),
            'nasdaq_pct': global_benchmarks.get('NASDAQ', {}).get('change_pct', 0),
            'nikkei_pct': global_benchmarks.get('Nikkei 225', {}).get('change_pct', 0),
            'hangseng_pct': global_benchmarks.get('Hang Seng', {}).get('change_pct', 0),
            'vix_pct': global_benchmarks.get('VIX', {}).get('change_pct', 0)
        }

        save_eod_to_database(summary_data)

    # Send to Telegram
    send_telegram_message(message)

    print("\n✅ EOD summary sent to Telegram")
    print(f"{'='*70}\n")

    return message


if __name__ == "__main__":
    try:
        generate_eod_summary()
    except Exception as e:
        error_msg = f"❌ EOD Summary Error: {str(e)}"
        print(error_msg)
        send_telegram_message(error_msg)
        sys.exit(1)
