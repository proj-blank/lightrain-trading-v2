import sys
sys.path.insert(0, "/home/ubuntu/trading")
from scripts.db_connection import get_active_positions, get_capital, get_available_cash

# Check SWING positions
swing_pos = get_active_positions("SWING")
print(f"SWING Positions: {len(swing_pos)}")
for p in swing_pos:
    ticker = p['ticker']
    category = p['category']
    price = float(p['entry_price'])
    qty = p['quantity']
    print(f"  {ticker}: {category} - Rs.{price:,.2f} x {qty}")

# Check capital
swing_cap = get_capital("SWING")
swing_cash = get_available_cash("SWING")
total = float(swing_cap['current_trading_capital'])
cash = float(swing_cash)
util = ((total - cash) / total * 100)
print(f"\nSWING Capital: Rs.{total:,.0f}")
print(f"SWING Cash Available: Rs.{cash:,.0f}")
print(f"SWING Utilization: {util:.1f}%")

# Check DAILY too
daily_pos = get_active_positions("DAILY")
daily_cap = get_capital("DAILY")
daily_cash = get_available_cash("DAILY")
dtotal = float(daily_cap['current_trading_capital'])
dcash = float(daily_cash)
dutil = ((dtotal - dcash) / dtotal * 100)
print(f"\nDAILY Positions: {len(daily_pos)}")
print(f"DAILY Capital: Rs.{dtotal:,.0f}")
print(f"DAILY Cash Available: Rs.{dcash:,.0f}")
print(f"DAILY Utilization: {dutil:.1f}%")
