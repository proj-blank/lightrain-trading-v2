#!/usr/bin/env python3
"""
Fix TP logic - ₹1000 should be TOTAL profit, not price increase!
"""

file_path = '/home/ubuntu/trading/daily_trading_pg.py'

with open(file_path, 'r') as f:
    content = f.read()

print("🔧 Fixing TP logic - correcting ₹1000 to be TOTAL profit...")

# Wrong logic I added
old_logic = """        # Calculate TP based on risk:reward ratio
        # Target at least 1.5x the risk, with minimum ₹1000 profit
        sl_distance = price - stop_loss
        min_profit = max(sl_distance * 1.5, 1000)  # 1.5:1 R:R, minimum ₹1000
        take_profit = price + min_profit"""

# Correct logic
new_logic = """        # Calculate TP based on risk:reward ratio
        # Target at least 1.5x the risk, OR ₹1000 TOTAL profit
        sl_distance = price - stop_loss
        rr_target_per_share = sl_distance * 1.5  # 1.5:1 risk:reward per share

        # Minimum profit per share to achieve ₹1000 total profit
        min_profit_per_share = 1000 / qty if qty > 0 else 1000

        # Use whichever gives better profit
        target_profit_per_share = max(rr_target_per_share, min_profit_per_share)
        take_profit = price + target_profit_per_share"""

if old_logic in content:
    content = content.replace(old_logic, new_logic)

    with open(file_path, 'w') as f:
        f.write(content)

    print("✅ Fixed TP logic!")
    print()
    print("Correction:")
    print("  BEFORE (WRONG): TP = price + max(1.5x risk, ₹1000)")
    print("                  → Added ₹1000 to PRICE (absurd!)")
    print()
    print("  AFTER (CORRECT): TP = price + max(1.5x risk, ₹1000/qty)")
    print("                   → Ensures ₹1000 TOTAL profit")
    print()
    print("Example: EICHERMOT @ ₹6778, Qty: 5")
    print("  Old (wrong): TP @ ₹7778 (₹1000 per share!)")
    print("  New (correct): TP @ ₹7003 (₹200 per share = ₹1000 total)")
else:
    print("⚠️  Could not find pattern - may need manual check")
