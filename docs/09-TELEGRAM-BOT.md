# 09 - Telegram Bot

Complete guide to Telegram bot commands, features, and alert formats.

---

## Table of Contents
1. [Bot Overview](#bot-overview)
2. [All Commands](#all-commands)
3. [Position Commands](#position-commands)
4. [Alert Formats](#alert-formats)
5. [Bot Setup](#bot-setup)

---

## Bot Overview

### Purpose
Real-time monitoring, position control, and alerts via Telegram.

### Features
- 24/7 command listening
- Real-time position queries
- Manual position control (hold/exit)
- Capital tracking
- Performance metrics
- Live market indices

---

## All Commands

### Information Commands

#### /help
Show all available commands with descriptions.

#### /status
System status overview:
- Active positions count (Daily/Swing)
- Capital breakdown
- Today's P&L
- Live market indices (Nifty 50, Mid 150, Small 250)

#### /positions
List all active positions across both strategies with:
- Ticker, category, days held
- Entry price, current price
- Unrealized P&L (amount + percentage)

#### /daily
Show only DAILY strategy positions

#### /swing
Show only SWING strategy positions

#### /pnl
Detailed P&L breakdown:
- Position-by-position P&L
- Strategy subtotals
- Grand total P&L
- Portfolio vs benchmarks (Nifty, S&P 500, Nasdaq)

#### /cap
Capital tracker summary:
- Total capital
- Available cash
- Invested capital
- Locked profits
- Realized losses
- Net P&L
- Category allocation breakdown

#### /gc
**Global Check** - Live global market regime analysis (refactored 2024-11-19)

**Purpose**: Real-time intraday monitoring of global market conditions

**What It Shows**:
1. **Live Global Markets** (via yfinance):
   - S&P 500 Futures (ES=F) - Price & daily change
   - Nikkei 225 (^N225) - Price & daily change
   - Hang Seng (^HSI) - Price & daily change
   - Gold Futures (GC=F) - Price & daily change (inverse indicator)
   - VIX (^VIX) - Volatility level and classification

2. **Regime Analysis**:
   - Current regime score (-10 to +10)
   - Regime classification (BULL/NEUTRAL/CAUTION/BEAR)
   - Position sizing recommendation
   - Comparison with morning 8:30 AM baseline

3. **India Markets** (live via AngelOne API):
   - Nifty 50 (Large-cap) - Intraday performance
   - Nifty Mid 150 (Mid-cap) - Intraday performance
   - Nifty Small 250 (Small-cap) - Intraday performance

**Key Features** (since Nov 19 refactor):
- Uses `GlobalMarketFilter` class (single source of truth)
- Same scoring logic as morning 8:30 AM check
- Does NOT save to database (live query only)
- Reduced from 177 lines to 85 lines
- Added India market indices for intraday context

**Example Response**:
```
🌍 GLOBAL CHECK (LIVE)
⏰ 14:30:25 IST

━━━ LIVE GLOBAL MARKETS ━━━
S&P Futures: 5,985.50 (+0.65%) [+1pts]
Nikkei: 38,250.00 (+1.20%) [+2pts]
Hang Seng: 19,850.00 (+0.80%) [+1pts]
Gold: 2,025.50 (-0.40%) [+1pts]
VIX: 14.5 (LOW) [+2pts]

━━━ REGIME ANALYSIS ━━━
Total Score: +7.0
Current Regime: 🟢 BULL
Position Sizing: 100%
New Entries: ✅ ALLOWED

Baseline (8:30 AM): NEUTRAL (Score: +2.5)

━━━ INDIA MARKETS (LIVE) ━━━
Nifty 50 (Large): 21,450.30 (+0.45%)
Nifty Mid 150: 45,230.15 (+0.78%)
Nifty Small 250: 13,850.60 (+1.02%)
```

**When to Use**:
- Intraday check before entering new positions
- After significant market moves during the day
- To compare current conditions with morning baseline
- To gauge India market strength across market caps

**Note**: /gc is for live monitoring only. The 8:30 AM check saves to SQL database for historical tracking.

---

## Position Commands

### /hold TICKER
Mark position to HOLD:
- Suppress exit signals for today
- Prevents automatic selling on dips
- Circuit breaker (5%) still active
- Useful when you believe in recovery

**Example**:
```
/hold RELIANCE
```

**Response**:
```
✅ HOLD COMMAND RECEIVED

📊 Ticker: RELIANCE

Position will continue holding.
Alert suppressed for today.
Circuit breaker (5%) still active.
```

### /exit TICKER
Force immediate exit:
- Overrides all holds
- Exits at current market price
- Records P&L
- Updates capital tracker

**Example**:
```
/exit INFY
```

**Response**:
```
✅ EXIT COMMAND EXECUTED

📊 Ticker: INFY
💰 Entry: ₹1,450 | Exit: ₹1,520
📈 P&L: +₹7,000 (+4.83%)
🕒 Held for: 7 days

Position closed successfully.
```

---

## Alert Formats

### Position Entry Alert
```
🟢 NEW POSITION OPENED

📊 Ticker: TCS
💰 Entry Price: ₹3,500
📦 Quantity: 30 shares
💵 Investment: ₹105,000
📂 Category: Large-cap
📈 Strategy: SWING

🎯 Take Profit: ₹3,850 (+10%)
🛑 Stop Loss: ₹3,325 (-5%)
```

### Take Profit Hit Alert
```
🎯 TAKE PROFIT LEVEL 1 HIT

📊 Ticker: HDFCBANK
💰 Entry: ₹1,600 | Current: ₹1,760
📈 Gain: +₹4,800 (+10.0%)
📦 Partial Exit: 30 shares (30%)

🔒 Profit Locked: ₹4,800
📦 Remaining: 70 shares
🛑 Stop Loss Updated: ₹1,600 (breakeven)
```

### Stop Loss Hit Alert
```
🔴 STOP LOSS HIT

📊 Ticker: WIPRO
💰 Entry: ₹450 | Exit: ₹427.50
📉 Loss: -₹2,250 (-5.0%)
📦 Quantity: 100 shares
🕒 Held for: 3 days

Position closed to protect capital.
```

### Circuit Breaker Alert
```
🚨 CIRCUIT BREAKER TRIGGERED

📊 Ticker: RELIANCE
💰 Current: ₹2,400 | Entry: ₹2,500
📉 Drop: -6.5% (from intraday high)
🔴 Reason: High volatility drop

⚠️ Position held for review.
Hard stop (5%) still active.
Will re-evaluate tomorrow.
```

### EOD Summary Alert
```
📊 END OF DAY SUMMARY
Date: 2024-11-13

💰 CAPITAL
Total: ₹500,000
Available: ₹125,000
Invested: ₹375,000

📈 TODAY'S P&L: +₹4,500 (+0.90%)
🔒 Locked Profits: ₹18,500
🔴 Realized Losses: ₹6,200
💵 Net P&L: +₹12,300 (+2.46%)

📊 ACTIVE POSITIONS: 16
  Daily: 5 positions (₹145,000)
  Swing: 11 positions (₹230,000)

🎯 BENCHMARKS (Today)
  🟢 Nifty 50: +0.85%
  🟢 S&P 500: +1.20%
  🔴 Nasdaq: -0.45%

📂 CATEGORY ALLOCATION
  Large-cap: ₹285,000 (57%)
  Mid-cap: ₹90,000 (18%)
  Microcap: ₹100,000 (20%)
```

---

## Bot Setup

### Start Bot
```bash
cd ~/trading
nohup python3 telegram_bot_listener.py >> logs/telegram_bot.log 2>&1 &
```

### Check Bot Status
```bash
ps aux | grep telegram_bot_listener
```

### Stop Bot
```bash
pkill -f telegram_bot_listener.py
```

### View Bot Logs
```bash
tail -f logs/telegram_bot.log
```

---

## Environment Variables

Required in `.env`:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

---

## Bot Polling

### How It Works
1. Bot polls Telegram API every 2 seconds
2. Checks for new messages
3. Processes commands instantly
4. Sends response back

### Command Processing
```python
def process_command(text):
    cmd = text.strip().lower()
    
    if cmd == '/help':
        return handle_help()
    elif cmd == '/status':
        return handle_status()
    elif cmd == '/positions':
        return handle_positions()
    # ... etc
```

---

## Real-Time Price Data

### Data Sources
1. **yfinance**: Delayed quotes (15-min delay)
2. **Angel One API**: Real-time quotes (live)

### Angel One Integration
```python
# Fetch real-time index data
benchmarks = {
    'Nifty 50': ('99926000', 'NIFTY 50'),
    'Nifty Mid 150': ('99926023', 'NIFTY MIDCAP 150'),
    'Nifty Small 250': ('99926037', 'NIFTY SMLCAP 250')
}
```

---

## Best Practices

### Using Commands
- ✅ Use `/pnl` for daily performance check
- ✅ Use `/hold` during temporary dips
- ✅ Use `/exit` for emergency exits only
- ❌ Don't override circuit breakers without reason

### Monitoring Alerts
- ✅ React to circuit breaker alerts promptly
- ✅ Review take-profit alerts (profit locked)
- ✅ Check EOD summary daily
- ❌ Don't ignore stop loss alerts

---

## Key Files

### Bot Scripts
- `telegram_bot_listener.py`: Main bot listener (24/7)
- `scripts/telegram_bot.py`: Message sending functions

### Related Scripts
- `monitor_swing_pg.py`: Sends position alerts
- `monitor_daily.py`: Sends position alerts
- `eod_summary.py`: Sends EOD summary

---

**Next**: [10-DATA-SOURCES.md](10-DATA-SOURCES.md) - Data sources and APIs
