#!/usr/bin/env python3
"""
Fix swing_trading_pg.py exit patterns to include credit_capital
"""

file_path = '/home/ubuntu/trading/swing_trading_pg.py'

with open(file_path, 'r') as f:
    content = f.read()

print("🔧 Fixing swing_trading_pg.py exit patterns...")

# Pattern without try block
old_pattern = """            close_position(ticker, STRATEGY, current_price, pnl)
            update_capital(STRATEGY, pnl)"""

new_pattern = """            close_position(ticker, STRATEGY, current_price, pnl)

            # Credit back the original investment
            original_investment = entry_price * qty
            credit_capital(STRATEGY, original_investment)

            # Update capital with P&L
            update_capital(STRATEGY, pnl)"""

count = content.count(old_pattern)
if count > 0:
    content = content.replace(old_pattern, new_pattern)
    print(f"  ✅ Fixed {count} exit point(s) in swing_trading_pg.py")

    with open(file_path, 'w') as f:
        f.write(content)

    print("  ✅ swing_trading_pg.py exits fixed!")
else:
    print("  ⚠️  Pattern not found - may already be fixed")
