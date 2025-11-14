#!/usr/bin/env python3
"""
Intraday Regime Check - Runs at 10 AM and 11 AM
Checks live VIX + multi-index data to decide if morning regime should be overridden
"""

import os
import json
import pyotp
from datetime import datetime
import pytz
from dotenv import load_dotenv
from SmartApi import SmartConnect

# Load environment
load_dotenv()

# AngelOne credentials
ANGEL_API_KEY = os.getenv('ANGELONE_API_KEY')
ANGEL_CLIENT_CODE = os.getenv('ANGELONE_CLIENT_ID')  # Note: .env uses CLIENT_ID
ANGEL_PASSWORD = os.getenv('ANGELONE_PASSWORD')
ANGEL_TOTP_SECRET = os.getenv('ANGELONE_TOTP_SECRET')

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_telegram(message):
    """Send Telegram alert"""
    import requests
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Telegram send failed: {e}")

def get_angel_session():
    """Create AngelOne session"""
    try:
        smart_api = SmartConnect(api_key=ANGEL_API_KEY)
        totp = pyotp.TOTP(ANGEL_TOTP_SECRET).now()
        data = smart_api.generateSession(ANGEL_CLIENT_CODE, ANGEL_PASSWORD, totp)
        if data['status']:
            return smart_api
    except Exception as e:
        print(f"AngelOne login failed: {e}")
    return None

def check_intraday_regime():
    """Check current market regime with live data"""
    try:
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)

        print(f"\n{'='*60}")
        print(f"Intraday Regime Check - {now.strftime('%H:%M:%S IST')}")
        print(f"{'='*60}\n")

        # Read pre-market regime
        regime_file = '/home/ubuntu/trading/data/market_regime.json'
        if not os.path.exists(regime_file):
            print("❌ No pre-market regime data found")
            return

        with open(regime_file, 'r') as f:
            regime_data = json.load(f)

        morning_regime = regime_data.get('regime', 'UNKNOWN')
        morning_score = regime_data.get('score', 0)
        morning_allow = regime_data.get('allow_new_entries', True)

        print(f"Morning Regime (8:30 AM): {morning_regime} (Score: {morning_score:.1f})")
        print(f"Morning Entries: {'ALLOWED' if morning_allow else 'BLOCKED'}\n")

        # Get live data from AngelOne
        session = get_angel_session()
        if not session:
            print("❌ Failed to create AngelOne session")
            return

        # Check India VIX
        vix_ltp = None
        try:
            vix_data = session.ltpData('NSE', 'INDIA VIX', '99926017')
            if vix_data and vix_data.get('status'):
                vix_ltp = float(vix_data['data'].get('ltp', 0))
                vix_level = "LOW" if vix_ltp < 15 else "MODERATE" if vix_ltp < 20 else "HIGH"
                print(f"India VIX: {vix_ltp:.2f} ({vix_level} FEAR)")
        except Exception as e:
            print(f"VIX fetch failed: {e}")

        # Check all 3 indices
        indices = [
            ('NIFTY 50', '99926000', 'Large-cap'),
            ('Nifty Midcap 150', '99926009', 'Mid-cap'),
            ('Nifty Smallcap 250', '99926013', 'Small-cap')
        ]

        green_count = 0
        total_count = 0
        index_data = []

        print("\nLive Indices:")
        for idx_name, token, category in indices:
            try:
                ltp_data = session.ltpData('NSE', idx_name, token)
                if ltp_data and ltp_data.get('status'):
                    data = ltp_data['data']
                    ltp = float(data.get('ltp', 0))
                    open_price = float(data.get('open', 0))

                    if open_price > 0:
                        change_pct = ((ltp - open_price) / open_price) * 100
                        is_green = change_pct >= 0

                        print(f"  {category}: {ltp:.2f} ({change_pct:+.2f}%) {'🟢' if is_green else '🔴'}")

                        index_data.append({
                            'name': idx_name,
                            'category': category,
                            'ltp': ltp,
                            'change_pct': change_pct,
                            'is_green': is_green
                        })

                        total_count += 1
                        if is_green:
                            green_count += 1
            except Exception as e:
                print(f"  {category}: Failed - {e}")

        # Calculate breadth
        breadth_pct = (green_count / total_count * 100) if total_count > 0 else 0
        print(f"\nMarket Breadth: {green_count}/{total_count} GREEN ({breadth_pct:.0f}%)")

        # Make decision
        override_morning = False
        intraday_verdict = ""
        recommendation = ""

        if breadth_pct >= 67:
            # Strong bullish
            intraday_verdict = "🟢 RISK-ON"
            if morning_regime == "BEAR":
                override_morning = True
                recommendation = "OVERRIDE: Strong intraday action, allow selective entries"
            else:
                recommendation = "ALIGNED: Continue with morning BULL signal"
        elif breadth_pct >= 33:
            # Mixed
            intraday_verdict = "🟡 NEUTRAL"
            recommendation = "CAUTIOUS: Mixed signals, be selective with entries"
        else:
            # Weak
            intraday_verdict = "🔴 RISK-OFF"
            recommendation = "AVOID: Weak market, skip new entries"

        print(f"\nIntraday Verdict: {intraday_verdict}")
        print(f"Decision: {recommendation}")

        # Update intraday override file
        intraday_file = '/home/ubuntu/trading/data/intraday_override.json'
        override_data = {
            'timestamp': now.isoformat(),
            'check_time': now.strftime('%H:%M IST'),
            'morning_regime': morning_regime,
            'intraday_verdict': intraday_verdict,
            'breadth_pct': breadth_pct,
            'green_count': green_count,
            'total_count': total_count,
            'vix': vix_ltp,
            'override_morning': override_morning,
            'allow_entries': override_morning or morning_allow,
            'recommendation': recommendation,
            'indices': index_data
        }

        with open(intraday_file, 'w') as f:
            json.dump(override_data, f, indent=2)

        print(f"\n✅ Saved intraday override data to {intraday_file}")

        # Send Telegram alert
        message = f"<b>📊 Intraday Regime Check</b>\n"
        message += f"⏰ {now.strftime('%H:%M:%S IST')}\n\n"
        message += f"<b>Morning (8:30 AM):</b> {morning_regime}\n"
        message += f"<b>Intraday:</b> {intraday_verdict}\n"
        message += f"<b>Breadth:</b> {green_count}/{total_count} GREEN ({breadth_pct:.0f}%)\n"

        if vix_ltp:
            message += f"<b>India VIX:</b> {vix_ltp:.2f}\n"

        message += f"\n<b>Decision:</b> {recommendation}\n"

        if override_morning:
            message += f"\n⚠️ <b>OVERRIDE ACTIVE</b>\n"
            message += f"Morning BEAR signal overridden by strong intraday action"

        send_telegram(message)
        print(f"\n✅ Sent Telegram alert")

        print(f"\n{'='*60}")

    except Exception as e:
        import traceback
        error_msg = f"❌ Intraday check failed: {e}\n{traceback.format_exc()}"
        print(error_msg)
        send_telegram(error_msg[:500])

if __name__ == "__main__":
    check_intraday_regime()
