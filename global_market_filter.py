#!/usr/bin/env python3
"""
Global Market Filter System
Checks overnight US markets, VIX, Nifty futures, and India VIX
to determine market regime before Indian market opens.
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Add path for imports
sys.path.insert(0, '/home/ubuntu/trading')

from scripts.telegram_bot import send_telegram_message

class GlobalMarketFilter:
    """
    Analyzes global market conditions to determine trading regime
    """

    def __init__(self):
        self.indicators = {}
        self.regime = None
        self.position_sizing_multiplier = 1.0
        self.allow_new_entries = True

    def fetch_us_markets(self):
        """Fetch S&P 500 and Nasdaq overnight performance"""
        try:
            # S&P 500
            spy = yf.Ticker("^GSPC")
            spy_data = spy.history(period="5d")

            if len(spy_data) >= 2:
                spy_current = spy_data['Close'].iloc[-1]
                spy_prev = spy_data['Close'].iloc[-2]
                spy_change_pct = ((spy_current - spy_prev) / spy_prev) * 100

                # 20-day SMA for trend
                spy_20d = spy.history(period="1mo")
                spy_sma20 = spy_20d['Close'].rolling(20).mean().iloc[-1]
                spy_trend = "ABOVE" if spy_current > spy_sma20 else "BELOW"

                self.indicators['sp500'] = {
                    'price': spy_current,
                    'change_pct': spy_change_pct,
                    'sma20': spy_sma20,
                    'trend': spy_trend
                }

            # Nasdaq
            nasdaq = yf.Ticker("^IXIC")
            nasdaq_data = nasdaq.history(period="5d")

            if len(nasdaq_data) >= 2:
                nasdaq_current = nasdaq_data['Close'].iloc[-1]
                nasdaq_prev = nasdaq_data['Close'].iloc[-2]
                nasdaq_change_pct = ((nasdaq_current - nasdaq_prev) / nasdaq_prev) * 100

                self.indicators['nasdaq'] = {
                    'price': nasdaq_current,
                    'change_pct': nasdaq_change_pct
                }

            return True

        except Exception as e:
            print(f"⚠️ Error fetching US markets: {e}")
            return False

    def fetch_vix(self):
        """Fetch VIX (Fear Index)"""
        try:
            vix = yf.Ticker("^VIX")
            vix_data = vix.history(period="5d")

            if not vix_data.empty:
                vix_current = vix_data['Close'].iloc[-1]

                # VIX interpretation
                if vix_current < 15:
                    vix_level = "LOW"  # Complacent market
                elif vix_current < 20:
                    vix_level = "NORMAL"
                elif vix_current < 30:
                    vix_level = "ELEVATED"  # Caution
                else:
                    vix_level = "HIGH"  # Fear/panic

                self.indicators['vix'] = {
                    'value': vix_current,
                    'level': vix_level
                }

            return True

        except Exception as e:
            print(f"⚠️ Error fetching VIX: {e}")
            return False

    def fetch_india_vix(self):
        """Fetch India VIX"""
        try:
            india_vix = yf.Ticker("^INDIAVIX")
            vix_data = india_vix.history(period="5d")

            if not vix_data.empty:
                india_vix_current = vix_data['Close'].iloc[-1]

                # India VIX interpretation
                if india_vix_current < 12:
                    level = "LOW"
                elif india_vix_current < 15:
                    level = "NORMAL"
                elif india_vix_current < 20:
                    level = "ELEVATED"
                else:
                    level = "HIGH"

                self.indicators['india_vix'] = {
                    'value': india_vix_current,
                    'level': level
                }

            return True

        except Exception as e:
            print(f"⚠️ Error fetching India VIX: {e}")
            return False

    def fetch_nifty_futures(self):
        """Fetch Nifty 50 futures/index"""
        try:
            # Nifty 50 Index
            nifty = yf.Ticker("^NSEI")
            nifty_data = nifty.history(period="5d")

            if len(nifty_data) >= 2:
                nifty_current = nifty_data['Close'].iloc[-1]
                nifty_prev = nifty_data['Close'].iloc[-2]
                nifty_change_pct = ((nifty_current - nifty_prev) / nifty_prev) * 100

                # 50-day SMA for trend
                nifty_50d = nifty.history(period="3mo")
                nifty_sma50 = nifty_50d['Close'].rolling(50).mean().iloc[-1]
                nifty_trend = "ABOVE" if nifty_current > nifty_sma50 else "BELOW"

                self.indicators['nifty'] = {
                    'price': nifty_current,
                    'change_pct': nifty_change_pct,
                    'sma50': nifty_sma50,
                    'trend': nifty_trend
                }

            return True

        except Exception as e:
            print(f"⚠️ Error fetching Nifty: {e}")
            return False

    def analyze_regime(self):
        """
        Determine market regime based on all indicators

        Regimes:
        - BULL: Strong positive momentum, low volatility
        - NEUTRAL: Mixed signals, moderate volatility
        - CAUTION: Elevated volatility, mixed trend
        - BEAR: Negative momentum, high volatility
        """

        # Scoring system
        score = 0
        signals = []

        # 1. US Markets (40% weight)
        if 'sp500' in self.indicators:
            sp500 = self.indicators['sp500']

            # Overnight change
            if sp500['change_pct'] > 1:
                score += 2
                signals.append("✅ S&P 500 strong (+)")
            elif sp500['change_pct'] > 0:
                score += 1
                signals.append("🟢 S&P 500 positive")
            elif sp500['change_pct'] > -1:
                score -= 1
                signals.append("🟡 S&P 500 slightly negative")
            else:
                score -= 2
                signals.append("🔴 S&P 500 weak (-)")

            # Trend vs SMA20
            if sp500['trend'] == "ABOVE":
                score += 1
                signals.append("✅ S&P 500 above 20-SMA")
            else:
                score -= 1
                signals.append("⚠️ S&P 500 below 20-SMA")

        # 2. VIX (30% weight)
        if 'vix' in self.indicators:
            vix = self.indicators['vix']

            if vix['level'] == "LOW":
                score += 2
                signals.append("✅ VIX low (calm market)")
            elif vix['level'] == "NORMAL":
                score += 1
                signals.append("🟢 VIX normal")
            elif vix['level'] == "ELEVATED":
                score -= 1
                signals.append("⚠️ VIX elevated (caution)")
            else:  # HIGH
                score -= 3
                signals.append("🔴 VIX high (fear)")

        # 3. India VIX (20% weight)
        if 'india_vix' in self.indicators:
            india_vix = self.indicators['india_vix']

            if india_vix['level'] == "LOW":
                score += 1
                signals.append("✅ India VIX low")
            elif india_vix['level'] == "NORMAL":
                score += 0.5
                signals.append("🟢 India VIX normal")
            elif india_vix['level'] == "ELEVATED":
                score -= 1
                signals.append("⚠️ India VIX elevated")
            else:
                score -= 2
                signals.append("🔴 India VIX high")

        # 4. Nifty Trend (10% weight)
        if 'nifty' in self.indicators:
            nifty = self.indicators['nifty']

            if nifty['trend'] == "ABOVE":
                score += 1
                signals.append("✅ Nifty above 50-SMA")
            else:
                score -= 1
                signals.append("⚠️ Nifty below 50-SMA")

        # Determine regime based on score
        if score >= 4:
            self.regime = "BULL"
            self.position_sizing_multiplier = 1.0
            self.allow_new_entries = True
        elif score >= 1:
            self.regime = "NEUTRAL"
            self.position_sizing_multiplier = 0.75
            self.allow_new_entries = True
        elif score >= -2:
            self.regime = "CAUTION"
            self.position_sizing_multiplier = 0.5
            self.allow_new_entries = True  # But reduced size
        else:
            self.regime = "BEAR"
            self.position_sizing_multiplier = 0.0
            self.allow_new_entries = False

        return {
            'regime': self.regime,
            'score': score,
            'signals': signals,
            'position_sizing_multiplier': self.position_sizing_multiplier,
            'allow_new_entries': self.allow_new_entries
        }

    def format_report(self, analysis):
        """Format market report for Telegram"""

        regime_emoji = {
            'BULL': '🟢',
            'NEUTRAL': '🟡',
            'CAUTION': '🟠',
            'BEAR': '🔴'
        }

        emoji = regime_emoji.get(analysis['regime'], '⚪')

        report = f"""
{emoji} *GLOBAL MARKET CHECK*
📅 {datetime.now().strftime('%d %b %Y, %H:%M IST')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 *Market Regime: {analysis['regime']}*
Score: {analysis['score']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Overnight US Markets:*
"""

        if 'sp500' in self.indicators:
            sp500 = self.indicators['sp500']
            report += f"S&P 500: {sp500['price']:.2f} ({sp500['change_pct']:+.2f}%)\n"
            report += f"  Trend: {sp500['trend']} 20-SMA\n"

        if 'nasdaq' in self.indicators:
            nasdaq = self.indicators['nasdaq']
            report += f"Nasdaq: {nasdaq['price']:.2f} ({nasdaq['change_pct']:+.2f}%)\n"

        report += "\n*Volatility:*\n"

        if 'vix' in self.indicators:
            vix = self.indicators['vix']
            report += f"VIX: {vix['value']:.2f} ({vix['level']})\n"

        if 'india_vix' in self.indicators:
            india_vix = self.indicators['india_vix']
            report += f"India VIX: {india_vix['value']:.2f} ({india_vix['level']})\n"

        if 'nifty' in self.indicators:
            nifty = self.indicators['nifty']
            report += f"\n*Nifty 50:*\n"
            report += f"{nifty['price']:.2f} ({nifty['change_pct']:+.2f}%)\n"
            report += f"Trend: {nifty['trend']} 50-SMA\n"

        report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        report += "*Key Signals:*\n"
        for signal in analysis['signals']:
            report += f"{signal}\n"

        report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        report += "*Trading Guidance:*\n"

        if analysis['regime'] == 'BULL':
            report += "✅ Normal trading - full position sizing\n"
        elif analysis['regime'] == 'NEUTRAL':
            report += "🟡 Cautious trading - 75% position sizing\n"
        elif analysis['regime'] == 'CAUTION':
            report += "⚠️ Defensive mode - 50% position sizing\n"
        else:  # BEAR
            report += "🛑 Risk-off mode - NO NEW ENTRIES\n"
            report += "Consider tightening stops on existing positions\n"

        return report

    def save_to_file(self, analysis):
        """Save market regime to file for trading scripts to read"""
        try:
            regime_file = '/home/ubuntu/trading/data/market_regime.json'
            os.makedirs(os.path.dirname(regime_file), exist_ok=True)

            import json
            data = {
                'timestamp': datetime.now().isoformat(),
                'regime': analysis['regime'],
                'score': analysis['score'],
                'position_sizing_multiplier': analysis['position_sizing_multiplier'],
                'allow_new_entries': analysis['allow_new_entries'],
                'indicators': self.indicators
            }

            with open(regime_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)

            print(f"✅ Market regime saved to {regime_file}")
            return True

        except Exception as e:
            print(f"⚠️ Error saving regime file: {e}")
            return False

    def run_full_check(self):
        """Run complete market check"""
        print("=" * 70)
        print("🌍 GLOBAL MARKET FILTER - MORNING CHECK")
        print("=" * 70)
        print(f"📅 {datetime.now().strftime('%d %b %Y, %H:%M:%S IST')}")
        print("=" * 70)

        # Fetch all indicators
        print("\n📥 Fetching market data...")
        self.fetch_us_markets()
        self.fetch_vix()
        self.fetch_india_vix()
        self.fetch_nifty_futures()

        # Analyze regime
        print("\n🔍 Analyzing market regime...")
        analysis = self.analyze_regime()

        print(f"\n{analysis['regime']} regime detected (score: {analysis['score']})")
        print(f"Position sizing multiplier: {analysis['position_sizing_multiplier']:.0%}")
        print(f"Allow new entries: {analysis['allow_new_entries']}")

        # Save to file
        self.save_to_file(analysis)

        # Send Telegram report
        report = self.format_report(analysis)
        send_telegram_message(report, parse_mode="Markdown")

        print("\n" + "=" * 70)
        print("✅ Global market check complete!")
        print("=" * 70)

        return analysis


def get_current_regime():
    """
    Read current market regime from file
    Returns regime data or None if file doesn't exist/is stale
    """
    try:
        import json
        regime_file = '/home/ubuntu/trading/data/market_regime.json'

        if not os.path.exists(regime_file):
            return None

        with open(regime_file, 'r') as f:
            data = json.load(f)

        # Check if data is fresh (within last 24 hours)
        timestamp = datetime.fromisoformat(data['timestamp'])
        if datetime.now() - timestamp > timedelta(hours=24):
            return None

        return data

    except Exception as e:
        print(f"⚠️ Error reading regime file: {e}")
        return None


if __name__ == "__main__":
    # Run morning market check
    filter_system = GlobalMarketFilter()
    filter_system.run_full_check()
