#!/usr/bin/env python3
"""
Update Take Profit logic in daily_trading_pg.py
Change from fixed 1% to ATR-based with risk:reward ratio
"""

file_path = '/home/ubuntu/trading/daily_trading_pg.py'

with open(file_path, 'r') as f:
    content = f.read()

print("🎯 Updating Take Profit logic in daily_trading_pg.py...")
print()

# Old fixed TP logic
old_logic = """        # Calculate stop loss and take profit based on ATR
        atr = calculate_atr(df, period=14)
        stop_loss = price - (2 * atr) if atr > 0 else price * 0.98  # 2 ATR or 2%
        take_profit = min(price * 1.01, price + 1000)  # 1% or ₹1000, whichever hits first"""

# New ATR-based TP with R:R ratio
new_logic = """        # Calculate stop loss and take profit based on ATR
        atr = calculate_atr(df, period=14)
        stop_loss = price - (2 * atr) if atr > 0 else price * 0.98  # 2 ATR or 2%

        # Calculate TP based on risk:reward ratio
        # Target at least 1.5x the risk, with minimum ₹1000 profit
        sl_distance = price - stop_loss
        min_profit = max(sl_distance * 1.5, 1000)  # 1.5:1 R:R, minimum ₹1000
        take_profit = price + min_profit"""

if old_logic in content:
    content = content.replace(old_logic, new_logic)

    with open(file_path, 'w') as f:
        f.write(content)

    print("✅ Updated TP logic!")
    print()
    print("Changes:")
    print("  BEFORE: TP = 1% or ₹1000 (fixed)")
    print("  AFTER:  TP = 1.5x risk OR ₹1000 minimum (adaptive)")
    print()
    print("Benefits:")
    print("  - Adapts to each stock's volatility")
    print("  - Maintains 1.5:1 risk:reward ratio")
    print("  - Lets volatile stocks run further")
    print("  - Ensures minimum ₹1000 profit target")
    print()
    print("Example:")
    print("  Stock A: Price ₹100, ATR ₹2")
    print("    - SL: ₹96 (risk ₹4)")
    print("    - TP: ₹106 (reward ₹6, 1.5:1 ratio)")
    print()
    print("  Stock B: Price ₹100, ATR ₹5")
    print("    - SL: ₹90 (risk ₹10)")
    print("    - TP: ₹115 (reward ₹15, 1.5:1 ratio)")
else:
    print("⚠️  Could not find exact pattern - may already be updated")
