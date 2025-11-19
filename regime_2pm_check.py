#!/usr/bin/env python3
"""
2PM Regime Check - Alert user if regime deteriorates during day
Runs at 14:00 IST (2:00 PM) - gives user option to /exitall before close
"""
import os
import sys
sys.path.insert(0, '/home/ubuntu/trading')

import yfinance as yf
import json
from datetime import datetime
import pytz
from scripts.telegram_bot import send_telegram_message

def calculate_live_score():
    """Calculate current global regime score (same logic as /gc command)"""
    score = 0
    details = []

    try:
        # 1. S&P Futures
        sp_fut = yf.Ticker('ES=F').history(period='2d')
        if len(sp_fut) >= 2:
            sp_change = ((sp_fut['Close'].iloc[-1] / sp_fut['Close'].iloc[-2]) - 1) * 100
            if sp_change > 1:
                sp_pts = 2
            elif sp_change > 0:
                sp_pts = 1
            elif sp_change > -1:
                sp_pts = -1
            else:
                sp_pts = -2
            score += sp_pts
            details.append(f"S&P Futures: {sp_change:+.2f}% [{sp_pts:+d}pts]")

        # 2. Nikkei
        nikkei = yf.Ticker('^N225').history(period='2d')
        if len(nikkei) >= 2:
            nikkei_change = ((nikkei['Close'].iloc[-1] / nikkei['Close'].iloc[-2]) - 1) * 100
            if nikkei_change > 1:
                nikkei_pts = 2
            elif nikkei_change > 0:
                nikkei_pts = 1
            elif nikkei_change > -1:
                nikkei_pts = -1
            else:
                nikkei_pts = -2
            score += nikkei_pts
            details.append(f"Nikkei: {nikkei_change:+.2f}% [{nikkei_pts:+d}pts]")

        # 3. Hang Seng
        hs = yf.Ticker('^HSI').history(period='2d')
        if len(hs) >= 2:
            hs_change = ((hs['Close'].iloc[-1] / hs['Close'].iloc[-2]) - 1) * 100
            if hs_change > 1:
                hs_pts = 1.5
            elif hs_change > 0:
                hs_pts = 1
            elif hs_change > -1:
                hs_pts = -1
            else:
                hs_pts = -1.5
            score += hs_pts
            details.append(f"Hang Seng: {hs_change:+.2f}% [{hs_pts:+.1f}pts]")

        # 4. Gold (inverse)
        gold = yf.Ticker('GC=F').history(period='2d')
        if len(gold) >= 2:
            gold_change = ((gold['Close'].iloc[-1] / gold['Close'].iloc[-2]) - 1) * 100
            if gold_change > 1.5:
                gold_pts = -2
            elif gold_change > 0.5:
                gold_pts = -1
            elif gold_change < -1.5:
                gold_pts = 2
            elif gold_change < -0.5:
                gold_pts = 1
            else:
                gold_pts = 0
            score += gold_pts
            details.append(f"Gold: {gold_change:+.2f}% [{gold_pts:+d}pts]")

        # 5. VIX
        vix = yf.Ticker('^VIX').history(period='1d')
        if not vix.empty:
            vix_val = vix['Close'].iloc[-1]
            if vix_val < 15:
                vix_pts = 2
                vix_level = "LOW"
            elif vix_val < 20:
                vix_pts = 1
                vix_level = "NORMAL"
            elif vix_val < 30:
                vix_pts = -1
                vix_level = "ELEVATED"
            else:
                vix_pts = -3
                vix_level = "HIGH"
            score += vix_pts
            details.append(f"VIX: {vix_val:.1f} ({vix_level}) [{vix_pts:+d}pts]")

    except Exception as e:
        details.append(f"Error: {str(e)}")

    return score, details

def main():
    """2PM regime check - alert user if deterioration detected"""
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)

    print("=" * 70)
    print("⏰ 2PM REGIME CHECK")
    print(f"Time: {now.strftime('%H:%M:%S IST')}")
    print("=" * 70)

    # Read morning regime (8:30 AM baseline)
    regime_file = '/home/ubuntu/trading/data/market_regime.json'
    morning_score = 0
    morning_regime = "UNKNOWN"

    if os.path.exists(regime_file):
        try:
            with open(regime_file, 'r') as f:
                regime_data = json.load(f)
            morning_score = regime_data.get('score', 0)
            morning_regime = regime_data.get('regime', 'UNKNOWN')
            print(f"📊 Morning (8:30 AM): {morning_regime} (Score: {morning_score:.1f})")
        except:
            pass
    else:
        print("⚠️ No morning regime data found")

    # Calculate current score
    current_score, details = calculate_live_score()

    # Determine current regime
    if current_score >= 4:
        current_regime = "BULL"
    elif current_score >= 1:
        current_regime = "NEUTRAL"
    elif current_score >= -2:
        current_regime = "CAUTION"
    else:
        current_regime = "BEAR"

    print(f"📊 Current (2:00 PM): {current_regime} (Score: {current_score:.1f})")
    print()
    for detail in details:
        print(f"  {detail}")

    # Calculate change
    score_change = current_score - morning_score

    # Determine if alert is needed
    alert_needed = False
    alert_level = ""

    if score_change <= -3:
        alert_needed = True
        alert_level = "🔴 SEVERE DETERIORATION"
        alert_msg = "Consider /exitall to close positions before market close"
    elif score_change <= -2:
        alert_needed = True
        alert_level = "🟡 MODERATE DETERIORATION"
        alert_msg = "Monitor closely. Consider /exitall if further weakness"
    elif current_score <= -3 and current_regime == "BEAR":
        alert_needed = True
        alert_level = "⚠️ BEAR REGIME DETECTED"
        alert_msg = "Regime is now BEAR. Consider /exitall to avoid overnight risk"

    # Send alert if needed
    if alert_needed:
        print(f"\n🚨 ALERT: {alert_level}")
        print(f"   {alert_msg}")

        telegram_msg = f"""<b>⏰ 2PM REGIME CHECK</b>

<b>{alert_level}</b>

<b>Morning (8:30 AM):</b> {morning_regime} (Score: {morning_score:.1f})
<b>Current (2:00 PM):</b> {current_regime} (Score: {current_score:.1f})

<b>Change:</b> {score_change:+.1f} points

<b>Current Data:</b>
{chr(10).join(details)}

━━━━━━━━━━━━━━━━━━━

<b>Recommendation:</b> {alert_msg}

Type /exitall to close all positions now
Type /gc for detailed global check
"""
        send_telegram_message(telegram_msg)
        print("📱 Alert sent to Telegram")
    else:
        print(f"\nℹ️ No alert needed (change: {score_change:+.1f} points)")
        print("   Regime stable or improving")

    print("\n" + "=" * 70)
    print("✅ 2PM check complete")
    print("=" * 70)

if __name__ == "__main__":
    main()
