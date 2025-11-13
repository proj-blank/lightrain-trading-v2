#!/bin/bash
# Apply MAX-HOLD bug fix to LightRain on AWS
# Run this on AWS VM when you have access

echo "========================================================================"
echo "🔧 Applying MAX-HOLD Bug Fix to LightRain"
echo "========================================================================"
echo ""

cd ~/trading

# Backup original file
echo "📦 Creating backup..."
cp swing_trading_pg.py swing_trading_pg.py.backup_$(date +%Y%m%d_%H%M%S)
echo "✅ Backup created"
echo ""

# Apply the fix manually (since patch command may not be available)
echo "🔧 Applying fix..."

# The fix: Move MAX-HOLD check before price data check
# Find line with "# Update days held" and insert MAX-HOLD check after it

python3 << 'PYEOF'
import re

# Read the file
with open('swing_trading_pg.py', 'r') as f:
    content = f.read()

# Find the section to replace
old_code = """        # Update days held
        days_held = (current_date - entry_date).days
        portfolio.at[idx, 'DaysHeld'] = days_held

        # Get current price
        if ticker not in stock_data or current_date not in stock_data[ticker].index:
            continue

        current_price = float(stock_data[ticker].loc[current_date, 'Close'])"""

new_code = """        # Update days held
        days_held = (current_date - entry_date).days
        portfolio.at[idx, 'DaysHeld'] = days_held

        # CHECK MAX HOLD FIRST (doesn't need price data)
        if days_held >= MAX_HOLD_DAYS:
            # Force exit due to max hold period - use last known price
            if ticker in stock_data and len(stock_data[ticker]) > 0:
                current_price = float(stock_data[ticker]['Close'].iloc[-1])
            else:
                log(f"⚠️ {ticker}: MAX-HOLD reached but no price data - skipping exit check")
                continue

            pnl = (current_price - entry_price) * qty
            pnl_pct = ((current_price - entry_price) / entry_price) * 100

            exits.append({
                'Date': current_date.strftime('%Y-%m-%d'),
                'Ticker': ticker,
                'Action': 'SELL',
                'Price': current_price,
                'Qty': qty,
                'EntryPrice': entry_price,
                'PnL': pnl,
                'PnL%': pnl_pct,
                'DaysHeld': days_held,
                'Reason': 'MAX-HOLD',
                'Category': row.get('Category', 'Unknown')
            })

            log(f"⏰ MAX-HOLD: {ticker} @ ₹{current_price:.2f} | P&L: ₹{pnl:,.0f} ({pnl_pct:+.2f}%) | {days_held}d")
            log_trade(exits[-1])
            portfolio = portfolio[portfolio['Ticker'] != ticker]
            continue

        # Get current price
        if ticker not in stock_data or current_date not in stock_data[ticker].index:
            continue

        current_price = float(stock_data[ticker].loc[current_date, 'Close'])"""

if old_code in content:
    content = content.replace(old_code, new_code)
    print("✅ Part 1: Added early MAX-HOLD check")
else:
    print("❌ Part 1: Could not find target code section")
    exit(1)

# Remove duplicate MAX-HOLD check later in the code
old_check = """        if current_price <= stop_loss:
            exit_reason = f"SMART-SL-{smart_stops['method'].upper()}" if 'smart_stops' in locals() else "STOP-LOSS"
        elif current_price >= take_profit:
            exit_reason = "TAKE-PROFIT"
        elif days_held >= MAX_HOLD_DAYS:
            exit_reason = "MAX-HOLD"
        elif 'smart_stops' in locals() and smart_stops.get('time_based_exit', False):
            exit_reason = "TIME-BASED\""""

new_check = """        if current_price <= stop_loss:
            exit_reason = f"SMART-SL-{smart_stops['method'].upper()}" if 'smart_stops' in locals() else "STOP-LOSS"
        elif current_price >= take_profit:
            exit_reason = "TAKE-PROFIT"
        elif 'smart_stops' in locals() and smart_stops.get('time_based_exit', False):
            exit_reason = "TIME-BASED"
        # NOTE: MAX-HOLD check moved earlier (before price data check)"""

if old_check in content:
    content = content.replace(old_check, new_check)
    print("✅ Part 2: Removed duplicate MAX-HOLD check")
else:
    print("⚠️ Part 2: Could not find duplicate check (may already be fixed)")

# Write the fixed file
with open('swing_trading_pg.py', 'w') as f:
    f.write(content)

print("✅ Fix applied successfully!")
PYEOF

echo ""
echo "========================================================================"
echo "✅ Fix Applied!"
echo "========================================================================"
echo ""
echo "📋 What was fixed:"
echo "   - MAX-HOLD check now runs BEFORE price data check"
echo "   - This ensures positions held >= 10 days exit even if price data missing"
echo "   - Bug that prevented TATACONSUM.NS from exiting at day 13 is now fixed"
echo ""
echo "🔄 Next steps:"
echo "   1. Test: python3 -c 'import swing_trading_pg; print(\"Syntax OK\")'"
echo "   2. Monitor: Next swing run should exit any positions >= 10 days"
echo ""
echo "📁 Backup saved to: swing_trading_pg.py.backup_*"
echo "========================================================================"
