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
from scripts.db_connection import get_db_cursor

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
        """Fetch S&P Futures (live overnight sentiment) and fallback to cash"""
        try:
            # Try S&P Futures first (ES=F) - live 24hr trading
            sp_futures = yf.Ticker("ES=F")
            futures_data = sp_futures.history(period="5d")

            if len(futures_data) >= 2:
                fut_current = futures_data['Close'].iloc[-1]
                fut_prev = futures_data['Close'].iloc[-2]
                fut_change_pct = ((fut_current - fut_prev) / fut_prev) * 100

                self.indicators['sp_futures'] = {
                    'price': fut_current,
                    'change_pct': fut_change_pct,
                    'source': 'FUTURES'
                }
                print(f"✅ S&P Futures: {fut_current:.2f} ({fut_change_pct:+.2f}%)")
            else:
                # Fallback to S&P 500 cash
                spy = yf.Ticker("^GSPC")
                spy_data = spy.history(period="5d")

                if len(spy_data) >= 2:
                    spy_current = spy_data['Close'].iloc[-1]
                    spy_prev = spy_data['Close'].iloc[-2]
                    spy_change_pct = ((spy_current - spy_prev) / spy_prev) * 100

                    self.indicators['sp_futures'] = {
                        'price': spy_current,
                        'change_pct': spy_change_pct,
                        'source': 'CASH (fallback)'
                    }
                    print(f"⚠️ S&P Cash (fallback): {spy_current:.2f} ({spy_change_pct:+.2f}%)")

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

    def fetch_asian_markets(self):
        """Fetch Nikkei and Hang Seng (live at 8:30 AM IST)"""
        try:
            # Nikkei 225
            nikkei = yf.Ticker("^N225")
            nikkei_data = nikkei.history(period="5d")

            if len(nikkei_data) >= 2:
                nikkei_current = nikkei_data['Close'].iloc[-1]
                nikkei_prev = nikkei_data['Close'].iloc[-2]
                nikkei_change = ((nikkei_current - nikkei_prev) / nikkei_prev) * 100

                self.indicators['nikkei'] = {
                    'price': nikkei_current,
                    'change_pct': nikkei_change
                }
                print(f"✅ Nikkei: {nikkei_current:.2f} ({nikkei_change:+.2f}%)")

            # Hang Seng
            hangseng = yf.Ticker("^HSI")
            hs_data = hangseng.history(period="5d")

            if len(hs_data) >= 2:
                hs_current = hs_data['Close'].iloc[-1]
                hs_prev = hs_data['Close'].iloc[-2]
                hs_change = ((hs_current - hs_prev) / hs_prev) * 100

                self.indicators['hang_seng'] = {
                    'price': hs_current,
                    'change_pct': hs_change
                }
                print(f"✅ Hang Seng: {hs_current:.2f} ({hs_change:+.2f}%)")

            return True

        except Exception as e:
            print(f"⚠️ Error fetching Asian markets: {e}")
            return False

    def fetch_gold(self):
        """Fetch Gold Futures (inverse risk indicator)"""
        try:
            gold = yf.Ticker("GC=F")
            gold_data = gold.history(period="5d")

            if len(gold_data) >= 2:
                gold_current = gold_data['Close'].iloc[-1]
                gold_prev = gold_data['Close'].iloc[-2]
                gold_change = ((gold_current - gold_prev) / gold_prev) * 100

                self.indicators['gold'] = {
                    'price': gold_current,
                    'change_pct': gold_change
                }
                print(f"✅ Gold: ${gold_current:.2f} ({gold_change:+.2f}%)")

            return True

        except Exception as e:
            print(f"⚠️ Error fetching Gold: {e}")
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
        Determine market regime based on global indicators

        New Weighting System (approved Nov 19, 2024):
        - S&P Futures: 35%
        - Nikkei: 25%
        - Hang Seng: 20%
        - Gold (inverse): 10%
        - VIX: 10%

        Score Thresholds:
        ≥ 4:  BULL (100% sizing)
        1-4:  NEUTRAL (75% sizing)
        -2-1: CAUTION (50% sizing)
        ≤-3:  BEAR (HALT - 0% sizing)
        """

        score = 0
        signals = []

        # 1. S&P Futures (35% weight) - Live overnight sentiment
        if 'sp_futures' in self.indicators:
            sp = self.indicators['sp_futures']
            change = sp['change_pct']
            source = sp['source']

            if change > 1:
                score += 2
                signals.append(f"✅ S&P {source}: {change:+.2f}% [+2pts, 35%wt]")
            elif change > 0:
                score += 1
                signals.append(f"🟢 S&P {source}: {change:+.2f}% [+1pt, 35%wt]")
            elif change > -1:
                score -= 1
                signals.append(f"🟡 S&P {source}: {change:+.2f}% [-1pt, 35%wt]")
            else:
                score -= 2
                signals.append(f"🔴 S&P {source}: {change:+.2f}% [-2pts, 35%wt]")

        # 2. Nikkei (25% weight) - Asian sentiment
        if 'nikkei' in self.indicators:
            nikkei = self.indicators['nikkei']
            change = nikkei['change_pct']

            if change > 1:
                score += 2
                signals.append(f"✅ Nikkei: {change:+.2f}% [+2pts, 25%wt]")
            elif change > 0:
                score += 1
                signals.append(f"🟢 Nikkei: {change:+.2f}% [+1pt, 25%wt]")
            elif change > -1:
                score -= 1
                signals.append(f"🟡 Nikkei: {change:+.2f}% [-1pt, 25%wt]")
            else:
                score -= 2
                signals.append(f"🔴 Nikkei: {change:+.2f}% [-2pts, 25%wt]")

        # 3. Hang Seng (20% weight) - Asian sentiment
        if 'hang_seng' in self.indicators:
            hs = self.indicators['hang_seng']
            change = hs['change_pct']

            if change > 1:
                score += 1.5
                signals.append(f"✅ Hang Seng: {change:+.2f}% [+1.5pts, 20%wt]")
            elif change > 0:
                score += 1
                signals.append(f"🟢 Hang Seng: {change:+.2f}% [+1pt, 20%wt]")
            elif change > -1:
                score -= 1
                signals.append(f"🟡 Hang Seng: {change:+.2f}% [-1pt, 20%wt]")
            else:
                score -= 1.5
                signals.append(f"🔴 Hang Seng: {change:+.2f}% [-1.5pts, 20%wt]")

        # 4. Gold (10% weight) - INVERSE correlation
        if 'gold' in self.indicators:
            gold = self.indicators['gold']
            change = gold['change_pct']

            if change > 1.5:
                score -= 2
                signals.append(f"🔴 Gold: {change:+.2f}% (RISK-OFF) [-2pts, 10%wt]")
            elif change > 0.5:
                score -= 1
                signals.append(f"🟡 Gold: {change:+.2f}% (Risk-off) [-1pt, 10%wt]")
            elif change < -1.5:
                score += 2
                signals.append(f"✅ Gold: {change:+.2f}% (RISK-ON) [+2pts, 10%wt]")
            elif change < -0.5:
                score += 1
                signals.append(f"🟢 Gold: {change:+.2f}% (Risk-on) [+1pt, 10%wt]")
            else:
                signals.append(f"⚪ Gold: {change:+.2f}% (Neutral) [0pts, 10%wt]")

        # 5. VIX (10% weight) - Fear gauge
        if 'vix' in self.indicators:
            vix = self.indicators['vix']
            level = vix['level']
            value = vix['value']

            if level == "LOW":
                score += 2
                signals.append(f"✅ VIX: {value:.1f} (LOW) [+2pts, 10%wt]")
            elif level == "NORMAL":
                score += 1
                signals.append(f"🟢 VIX: {value:.1f} (NORMAL) [+1pt, 10%wt]")
            elif level == "ELEVATED":
                score -= 1
                signals.append(f"🟡 VIX: {value:.1f} (ELEVATED) [-1pt, 10%wt]")
            else:  # HIGH
                score -= 3
                signals.append(f"🔴 VIX: {value:.1f} (HIGH FEAR) [-3pts, 10%wt]")

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
            self.allow_new_entries = True
        else:  # score <= -3 (NEW STRICT THRESHOLD)
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

    def save_to_database(self, analysis):
        """Save market regime to database for historical tracking"""
        try:
            with get_db_cursor() as cur:
                # Extract indicator data
                sp_futures = self.indicators.get('sp_futures', {})
                nikkei = self.indicators.get('nikkei', {})
                hang_seng = self.indicators.get('hang_seng', {})
                gold = self.indicators.get('gold', {})
                vix = self.indicators.get('vix', {})

                # Insert regime check data
                cur.execute("""
                    INSERT INTO market_regime_history (
                        check_date, regime, score,
                        position_sizing_multiplier, allow_new_entries,
                        sp_futures_price, sp_futures_change_pct,
                        nikkei_price, nikkei_change_pct,
                        hang_seng_price, hang_seng_change_pct,
                        gold_price, gold_change_pct,
                        vix_value
                    ) VALUES (
                        CURRENT_DATE, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (check_date)
                    DO UPDATE SET
                        regime = EXCLUDED.regime,
                        score = EXCLUDED.score,
                        position_sizing_multiplier = EXCLUDED.position_sizing_multiplier,
                        allow_new_entries = EXCLUDED.allow_new_entries,
                        sp_futures_price = EXCLUDED.sp_futures_price,
                        sp_futures_change_pct = EXCLUDED.sp_futures_change_pct,
                        nikkei_price = EXCLUDED.nikkei_price,
                        nikkei_change_pct = EXCLUDED.nikkei_change_pct,
                        hang_seng_price = EXCLUDED.hang_seng_price,
                        hang_seng_change_pct = EXCLUDED.hang_seng_change_pct,
                        gold_price = EXCLUDED.gold_price,
                        gold_change_pct = EXCLUDED.gold_change_pct,
                        vix_value = EXCLUDED.vix_value
                """, (
                    analysis['regime'],
                    float(analysis['score']) if analysis['score'] is not None else None,
                    float(analysis['position_sizing_multiplier']) if analysis['position_sizing_multiplier'] is not None else None,
                    analysis['allow_new_entries'],
                    float(sp_futures.get('price')) if sp_futures.get('price') is not None else None,
                    float(sp_futures.get('change_pct')) if sp_futures.get('change_pct') is not None else None,
                    float(nikkei.get('price')) if nikkei.get('price') is not None else None,
                    float(nikkei.get('change_pct')) if nikkei.get('change_pct') is not None else None,
                    float(hang_seng.get('price')) if hang_seng.get('price') is not None else None,
                    float(hang_seng.get('change_pct')) if hang_seng.get('change_pct') is not None else None,
                    float(gold.get('price')) if gold.get('price') is not None else None,
                    float(gold.get('change_pct')) if gold.get('change_pct') is not None else None,
                    float(vix.get('value')) if vix.get('value') is not None else None
                ))

            print(f"✅ Market regime saved to database")
            return True

        except Exception as e:
            print(f"⚠️ Error saving regime to database: {e}")
            return False

    def run_full_check(self):
        """Run complete market check"""
        print("=" * 70)
        print("🌍 GLOBAL MARKET FILTER - MORNING CHECK")
        print("=" * 70)
        print(f"📅 {datetime.now().strftime('%d %b %Y, %H:%M:%S IST')}")
        print("=" * 70)

        # Fetch all indicators (NEW SYSTEM - Nov 19, 2024)
        print("\n📥 Fetching market data...")
        self.fetch_us_markets()         # S&P Futures (or cash fallback)
        self.fetch_asian_markets()      # Nikkei + Hang Seng
        self.fetch_gold()                # Gold futures (inverse)
        self.fetch_vix()                 # VIX fear gauge

        # Analyze regime
        print("\n🔍 Analyzing market regime...")
        analysis = self.analyze_regime()

        print(f"\n{analysis['regime']} regime detected (score: {analysis['score']})")
        print(f"Position sizing multiplier: {analysis['position_sizing_multiplier']:.0%}")
        print(f"Allow new entries: {analysis['allow_new_entries']}")

        # Save to file
        self.save_to_file(analysis)

        # Save to database for historical tracking
        self.save_to_database(analysis)

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
