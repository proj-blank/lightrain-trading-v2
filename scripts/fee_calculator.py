#!/usr/bin/env python3
"""
AngelOne Fee Calculator for Equity Delivery Trades
"""

def calculate_delivery_fees(buy_value, sell_value=None, num_scripts_sold=1):
    """
    Calculate AngelOne delivery trading fees
    
    Args:
        buy_value: Total buy value
        sell_value: Total sell value (if None, assumes same as buy for estimation)
        num_scripts_sold: Number of different scripts sold (for DP charges)
    
    Returns:
        dict with fee breakdown
    """
    if sell_value is None:
        sell_value = buy_value
    
    fees = {}
    
    # Brokerage - FREE for delivery
    fees['brokerage'] = 0
    
    # STT - 0.1% on sell side only
    fees['stt'] = sell_value * 0.001
    
    # Exchange Transaction Charges - 0.00345% both sides
    fees['exchange_txn'] = (buy_value + sell_value) * 0.0000345
    
    # SEBI Charges - 0.0001% on turnover
    fees['sebi'] = (buy_value + sell_value) * 0.000001
    
    # Stamp Duty - 0.015% on buy side only
    fees['stamp_duty'] = buy_value * 0.00015
    
    # GST - 18% on (brokerage + exchange charges)
    fees['gst'] = (fees['brokerage'] + fees['exchange_txn']) * 0.18
    
    # DP Charges - Rs.15.93 per script sold
    fees['dp_charges'] = 15.93 * num_scripts_sold
    
    fees['total'] = sum(fees.values())
    
    return fees


def calculate_position_fees(entry_price, current_price, quantity):
    """
    Calculate fees for a single position
    
    Returns:
        dict with buy_value, sell_value, gross_pnl, fees, net_pnl
    """
    buy_value = entry_price * quantity
    sell_value = current_price * quantity
    gross_pnl = sell_value - buy_value
    
    fees = calculate_delivery_fees(buy_value, sell_value, num_scripts_sold=1)
    
    net_pnl = gross_pnl - fees['total']
    
    return {
        'buy_value': buy_value,
        'sell_value': sell_value,
        'gross_pnl': gross_pnl,
        'fees': fees['total'],
        'net_pnl': net_pnl,
        'fee_breakdown': fees
    }


if __name__ == '__main__':
    # Test
    result = calculate_position_fees(1054.50, 1060, 3)
    print(f"Gross P&L: Rs.{result['gross_pnl']:.2f}")
    print(f"Fees: Rs.{result['fees']:.2f}")
    print(f"Net P&L: Rs.{result['net_pnl']:.2f}")
