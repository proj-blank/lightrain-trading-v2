#!/usr/bin/env python3
"""
Script to integrate global market regime check into trading scripts
"""
import sys

# Insertion code for regime check
REGIME_CHECK_CODE = '''
    # 🌍 Global Market Regime Check
    from global_market_filter import get_current_regime
    regime_data = get_current_regime()

    if regime_data:
        regime = regime_data['regime']
        regime_emoji = {'BULL': '🟢', 'NEUTRAL': '🟡', 'CAUTION': '🟠', 'BEAR': '🔴'}.get(regime, '⚪')
        log(f"{regime_emoji} Global Market Regime: {regime}")
        log(f"   Position Sizing Multiplier: {regime_data['position_sizing_multiplier']:.0%}")
        log(f"   New Entries Allowed: {regime_data['allow_new_entries']}")

        # Store regime multiplier for position sizing
        REGIME_MULTIPLIER = regime_data['position_sizing_multiplier']
        ALLOW_NEW_ENTRIES = regime_data['allow_new_entries']

        if regime == 'BEAR':
            log("⚠️  BEAR REGIME: No new positions will be taken today")
            log("⚠️  Consider tightening stops on existing positions")
    else:
        log("⚠️ No market regime data found (run global_market_filter.py at 8:30 AM)")
        REGIME_MULTIPLIER = 1.0  # Default to normal if no data
        ALLOW_NEW_ENTRIES = True

'''

def patch_swing_trading():
    """Add regime check to swing_trading_pg.py"""
    file_path = '/home/ubuntu/trading/swing_trading_pg.py'

    with open(file_path, 'r') as f:
        lines = f.readlines()

    # Find the line "log(f"📅 Trading date: {current_date.date()}")"
    # Insert regime check after it
    new_lines = []
    inserted = False

    for i, line in enumerate(lines):
        new_lines.append(line)

        # Look for the trading date log line
        if 'Trading date:' in line and not inserted:
            # Add regime check code after this line
            new_lines.append(REGIME_CHECK_CODE)
            inserted = True

    if inserted:
        with open(file_path, 'w') as f:
            f.writelines(new_lines)
        print("✅ swing_trading_pg.py patched successfully")
        return True
    else:
        print("❌ Could not find insertion point in swing_trading_pg.py")
        return False

def patch_daily_trading():
    """Add regime check to daily_trading_pg.py"""
    file_path = '/home/ubuntu/trading/daily_trading_pg.py'

    with open(file_path, 'r') as f:
        lines = f.readlines()

    # Find similar insertion point
    new_lines = []
    inserted = False

    for i, line in enumerate(lines):
        new_lines.append(line)

        # Look for the date or similar initialization
        if ('datetime.now()' in line and 'print' in lines[i+1] if i+1 < len(lines) else False) and not inserted:
            # Skip a few lines to get past the header
            continue
        elif '="*' in line and 'DAILY' in lines[i-2] if i >= 2 else False and not inserted:
            new_lines.append(REGIME_CHECK_CODE.replace('log(', 'print('))
            inserted = True

    if inserted:
        with open(file_path, 'w') as f:
            f.writelines(new_lines)
        print("✅ daily_trading_pg.py patched successfully")
        return True
    else:
        print("⚠️ Could not find insertion point in daily_trading_pg.py (may need manual integration)")
        return False

if __name__ == "__main__":
    print("=" * 70)
    print("Integrating Global Market Regime Check")
    print("=" * 70)

    success_swing = patch_swing_trading()
    success_daily = patch_daily_trading()

    print("\n" + "=" * 70)
    if success_swing or success_daily:
        print("✅ Integration complete!")
        if not success_daily:
            print("⚠️  daily_trading_pg.py may need manual integration")
    else:
        print("❌ Integration failed")
    print("=" * 70)
