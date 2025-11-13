#!/usr/bin/env python3
import os, sys
sys.path.insert(0, '/Users/brosshack/project_blank/LightRain')
sys.path.insert(0, '/Users/brosshack/project_blank/LightRain/LightRain')
from scripts.db_connection import get_active_positions, update_position_price
from scripts.data_loader_angelone import get_current_prices_angelone
from scripts.order_executor import get_order_executor

STRATEGY = "SWING"
positions = get_active_positions(strategy=STRATEGY)
if not positions: sys.exit(0)

position_tickers = [p['ticker'] for p in positions]
current_prices = get_current_prices_angelone(position_tickers)
order_executor = get_order_executor(STRATEGY)

for pos in positions:
    ticker = pos['ticker']
    entry_price = float(pos['entry_price'])
    quantity = int(pos['quantity'])
    stop_loss = float(pos['stop_loss'])
    take_profit = float(pos['take_profit'])
    current_price = current_prices.get(ticker)
    if not current_price: continue
    
    # Update unrealized P&L in database
    update_position_price(ticker, STRATEGY, current_price)
    
    if current_price <= stop_loss:
        order_executor.execute_sell(ticker, quantity, current_price, "Monitor: Stop loss hit")
    elif current_price >= take_profit:
        order_executor.execute_sell(ticker, quantity, current_price, "Monitor: Take profit hit")
