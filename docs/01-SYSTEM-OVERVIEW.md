# LightRain Trading System - System Overview

**Last Updated**: 2024-11-13  
**Purpose**: High-level architecture, components, strategies, and data flow

---

## Table of Contents
1. [System Architecture](#system-architecture)
2. [Data Flow](#data-flow)
3. [Component Breakdown](#component-breakdown)
4. [Trading Strategies](#trading-strategies)
5. [Technology Stack](#technology-stack)
6. [Automation Schedule](#automation-schedule)
7. [Safety Mechanisms](#safety-mechanisms)

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      LIGHTRAIN TRADING SYSTEM                       │
│                     AWS EC2 (Mumbai Region)                         │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                ┌──────────────────┼──────────────────┐
                │                  │                  │
        ┌───────▼────────┐ ┌──────▼──────┐  ┌───────▼────────┐
        │   SCREENING    │ │   TRADING   │  │   MONITORING   │
        │                │ │             │  │                │
        │ • Daily (9AM)  │ │ • DAILY     │  │ • Every 5 min  │
        │ • Swing (8:30) │ │ • SWING     │  │ • TP/SL check  │
        └───────┬────────┘ └──────┬──────┘  └───────┬────────┘
                │                  │                  │
                │         ┌────────▼──────────┐       │
                └────────►│   PostgreSQL DB   │◄──────┘
                          │   (AWS RDS)       │
                          │                   │
                          │ • positions       │
                          │ • capital_tracker │
                          │ • trades_log      │
                          │ • eod_history     │
                          └────────┬──────────┘
                                   │
                          ┌────────▼──────────┐
                          │  Telegram Bot     │
                          │                   │
                          │ • Alerts          │
                          │ • Reports         │
                          │ • Commands        │
                          └───────────────────┘
```

**External Data Sources:**
- **yfinance** → Historical stock prices (NSE, BSE)
- **AngelOne API** → Real-time data (future integration)
- **Anthropic Claude API** → AI validation for swing trades

---

## 2. Data Flow

### Morning Screening Flow (8:30 AM - 9:25 AM IST)

```
┌──────────────┐
│ 8:30 AM IST  │
└──────┬───────┘
       │
       ▼
┌─────────────────────────────┐
│ stocks_screening.py         │
│ • Load 351 NSE stocks       │
│ • Save to screened_stocks   │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ 9:00 AM IST                 │
│ daily_screening.py          │
│ • Technical analysis        │
│ • Score 0-100               │
│ • Filter score >= 60        │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ 9:00 AM IST                 │
│ daily_trading_pg.py         │
│ • Read scored stocks        │
│ • Apply RS rating filter    │
│ • Generate BUY signals      │
│ • Execute positions         │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ 9:25 AM IST                 │
│ swing_trading_pg.py         │
│ • Read screened_stocks      │
│ • Weekly analysis           │
│ • AI validation             │
│ • Execute positions         │
└─────────────────────────────┘
```

### Trading Execution Flow

```
Stock Screening
       │
       ├─► Technical Scoring (0-100)
       │   ├─ RSI (20%)
       │   ├─ MACD (25%)
       │   ├─ Bollinger Bands (15%)
       │   ├─ Volume (10%)
       │   ├─ Trend (10%)
       │   └─ Other indicators (20%)
       │
       ├─► RS Rating Filter (Min 60/99)
       │
       ├─► AI Validation (SWING only)
       │
       ▼
Entry Decision
       │
       ├─► Position Sizing
       │   ├─ 60% Large-cap
       │   ├─ 20% Mid-cap
       │   └─ 20% Micro-cap
       │
       ├─► Calculate TP/SL
       │   ├─ DAILY: TP +5-7%, SL -3-4%
       │   └─ SWING: TP +7-12%, SL -4-5%
       │
       ▼
Execute Trade
       │
       ├─► Update positions table
       ├─► Debit capital_tracker
       ├─► Log to trades table
       └─► Send Telegram alert
```

### Position Monitoring Flow

```
┌────────────────────┐
│ Every 5 minutes    │
│ (9:00-3:30 IST)    │
└─────────┬──────────┘
          │
          ▼
┌───────────────────────────┐
│ monitor_daily.py          │
│ monitor_swing_pg.py       │
│                           │
│ For each HOLD position:   │
│ 1. Fetch current price    │
│ 2. Check TP hit           │
│ 3. Check SL hit           │
│ 4. Check trailing stop    │
│ 5. Check time-based exit  │
└─────────┬─────────────────┘
          │
          ├─► TP Hit?
          │   ├─► Close position
          │   ├─► Lock profits
          │   └─► Telegram alert
          │
          ├─► SL Hit?
          │   ├─► Close position
          │   ├─► Deduct loss
          │   └─► Telegram alert
          │
          └─► Time Exit? (DAILY: 3:25 PM, SWING: 10 days)
              ├─► Force close
              └─► Telegram alert
```

### Capital Management Flow

```
Entry Trade
    │
    ├─► Debit trading capital
    │   └─► capital_tracker.current_trading_capital -= investment
    │
    └─► Hold position
            │
Exit Trade (Profit)
    │
    ├─► Credit back investment
    │   └─► capital_tracker.current_trading_capital += investment
    │
    └─► Lock profit
        └─► capital_tracker.total_profits_locked += profit

Exit Trade (Loss)
    │
    ├─► Credit back remaining amount
    │   └─► capital_tracker.current_trading_capital += (investment - loss)
    │
    └─► Record loss
        └─► capital_tracker.total_losses += loss
```

---

## 3. Component Breakdown

### Core Modules (`scripts/`)

| Module | Purpose | Key Functions |
|--------|---------|---------------|
| `db_connection.py` | PostgreSQL operations | `get_active_positions()`, `add_position()`, `close_position()`, `get_capital()` |
| `signal_generator_daily.py` | DAILY signals | `generate_signal_daily()` - Technical scoring |
| `signal_generator_swing.py` | SWING signals | `generate_signal_swing()` - Multi-day analysis |
| `risk_manager.py` | TP/SL calculations | `calculate_position_metrics()`, `check_circuit_breaker()` |
| `telegram_bot.py` | Notifications | `send_trade_alert()`, `send_telegram_message()` |
| `rs_rating.py` | Relative Strength | `calculate_rs_rating()` - Rank stocks 1-99 |
| `percentage_based_allocation.py` | Position sizing | `calculate_percentage_allocation()` - 60/20/20 split |
| `ai_analyzer.py` | AI validation | `analyze_position_with_AI()` - Claude analysis |

### Trading Scripts

| Script | Strategy | Runs When | Purpose |
|--------|----------|-----------|---------|
| `daily_trading_pg.py` | DAILY | 9:00 AM IST | Enter intraday positions |
| `swing_trading_pg.py` | SWING | 9:25 AM IST | Enter multi-day positions |
| `monitor_daily.py` | DAILY | Every 5 min | Check TP/SL for DAILY positions |
| `monitor_swing_pg.py` | SWING | Every 5 min | Check TP/SL for SWING positions |
| `telegram_bot_listener.py` | Both | Always (daemon) | Handle Telegram commands |

### Screening Scripts

| Script | Purpose | Runs When |
|--------|---------|-----------|
| `stocks_screening.py` | Populate NSE universe (351 stocks) | 8:30 AM IST |
| `daily_screening.py` | Score stocks for DAILY trading | 9:00 AM IST |

### Reporting Scripts

| Script | Purpose | Runs When |
|--------|---------|-----------|
| `eod_summary.py` | Daily portfolio snapshot | 3:30 PM IST |
| `eod_report.py` | Detailed performance report | 4:00 PM IST |

---

## 4. Trading Strategies

### DAILY Strategy (Intraday)

**Objective**: Capture 5-7% profit in single trading day

| Parameter | Value |
|-----------|-------|
| **Capital** | ₹13,00,000 (separate pool) |
| **Max Hold** | 1 day (force exit 3:25 PM) |
| **Target Profit** | 5-7% |
| **Stop Loss** | 3-4% |
| **Position Sizing** | 60/20/20 (Large/Mid/Micro) |
| **Max Positions** | Dynamic (based on allocation) |
| **Min Score** | 60/100 |
| **Min RS Rating** | 60/99 |
| **Monitoring** | Every 5 minutes |

**Entry Criteria**:
- Technical score >= 60
- RS Rating >= 60
- Strong momentum indicators (RSI, MACD, Volume)
- No circuit breaker flags

**Exit Criteria**:
- TP hit: +5-7%
- SL hit: -3-4%
- Time exit: 3:25 PM IST (force close all positions)

### SWING Strategy (Multi-day)

**Objective**: Capture 7-12% profit over 3-10 days

| Parameter | Value |
|-----------|-------|
| **Capital** | ₹10,00,000 (separate pool) |
| **Max Hold** | 10 days (force exit) |
| **Target Profit** | 7-12% |
| **Stop Loss** | 4-5% (initial) |
| **Trailing Stop** | Chandelier + ATR-based |
| **Position Sizing** | 60/20/20 (Large/Mid/Micro) |
| **Max Positions** | Dynamic (based on allocation) |
| **Min Score** | 65/100 |
| **Min RS Rating** | 65/99 |
| **AI Validation** | Yes (Claude analyzes charts) |
| **Monitoring** | Every 5 minutes |

**Entry Criteria**:
- Technical score >= 65
- RS Rating >= 65
- Weekly chart trend confirmation
- AI validation (optional but recommended)
- No RSI overbought (< 70)
- Preferably 0.5-3% pullback from 5-day high

**Exit Criteria**:
- TP hit: +7-12%
- SL hit: -4-5%
- Trailing stop hit (if in profit)
- Time exit: 10 days max hold
- Smart stops: Chandelier trailing stop

---

## 5. Technology Stack

### Backend
- **Language**: Python 3.8+
- **Database**: PostgreSQL 13 (AWS RDS)
- **Server**: Ubuntu 20.04 LTS (AWS EC2 t2.micro)
- **Region**: AWS Mumbai (ap-south-1)

### Python Libraries
```
yfinance          # Stock price data
psycopg2          # PostgreSQL driver
pandas            # Data manipulation
numpy             # Numerical computing
anthropic         # Claude AI API
python-telegram-bot # Telegram bot
python-dotenv     # Environment variables
```

### Data Sources
- **yfinance**: Historical OHLCV data (NSE/BSE)
- **AngelOne API**: Real-time data (future)
- **Anthropic Claude**: AI trade validation

### Infrastructure
- **Scheduler**: Cron (Linux)
- **Process Manager**: nohup for daemon processes
- **Logging**: File-based logs (`logs/` directory)
- **Version Control**: Git

---

## 6. Automation Schedule

**All times in IST (UTC+5:30)**

| Time | Script | Purpose | Frequency |
|------|--------|---------|-----------|
| 8:30 AM | `stocks_screening.py` | Populate NSE universe | Daily (Mon-Fri) |
| 9:00 AM | `daily_screening.py` | Score stocks for DAILY | Daily (Mon-Fri) |
| 9:00 AM | `daily_trading_pg.py` | Execute DAILY trades | Daily (Mon-Fri) |
| 9:25 AM | `swing_trading_pg.py` | Execute SWING trades | Daily (Mon-Fri) |
| 9:00-3:30 | `monitor_daily.py` | Monitor DAILY positions | Every 5 min |
| 9:00-3:30 | `monitor_swing_pg.py` | Monitor SWING positions | Every 5 min |
| 3:30 PM | `eod_summary.py` | Daily snapshot | Daily (Mon-Fri) |
| 4:00 PM | `eod_report.py` | Detailed report | Daily (Mon-Fri) |
| Always | `telegram_bot_listener.py` | Bot daemon | Continuous |

**Crontab Configuration** (in UTC):
```bash
# Screening (8:30 AM IST = 3:00 AM UTC)
0 3 * * 1-5 cd /home/ubuntu/trading && bash run_stocks_screening.sh

# Trading (9:00 AM IST = 3:30 AM UTC)
30 3 * * 1-5 cd /home/ubuntu/trading && bash run_daily_trading.sh
30 3 * * 1-5 cd /home/ubuntu/trading && python3 daily_screening.py

# Swing trading (9:25 AM IST = 3:55 AM UTC)
55 3 * * 1-5 cd /home/ubuntu/trading && bash run_swing_trading.sh

# Monitoring (9:00-3:30 IST = 3:30-10:00 UTC)
*/5 3-10 * * 1-5 cd /home/ubuntu/trading && python3 monitor_daily.py
*/5 3-10 * * 1-5 cd /home/ubuntu/trading && python3 monitor_swing_pg.py

# EOD reports (3:30 PM = 10:00 UTC, 4:00 PM = 10:30 UTC)
0 10 * * 1-5 cd /home/ubuntu/trading && bash run_eod_summary.sh
30 10 * * 1-5 cd /home/ubuntu/trading && bash run_eod_report.sh
```

---

## 7. Safety Mechanisms

### 1. Circuit Breakers

**3% Alert Threshold**:
- System sends Telegram alert when position loses 3%
- Position continues to hold (no auto-exit)
- User can manually override via Telegram

**5% Hard Stop**:
- Automatic exit if position loses 5%
- Cannot be overridden
- Capital preservation priority

**Implementation**:
```python
# In risk_manager.py
def check_circuit_breaker(entry_price, current_price):
    loss_pct = ((current_price - entry_price) / entry_price) * 100
    
    if loss_pct <= -5.0:
        return "HARD_STOP", "Automatic exit at 5% loss"
    elif loss_pct <= -3.0:
        return "ALERT", "Warning: Position down 3%"
    else:
        return "OK", ""
```

### 2. Position Limits

**Capital-Based Limits**:
- DAILY: ₹13L total capital
- SWING: ₹10L total capital
- Max 20% per position (14% for SWING)

**60/20/20 Allocation**:
- 60% → Large-cap stocks (lower risk)
- 20% → Mid-cap stocks (moderate risk)
- 20% → Micro-cap stocks (higher risk)

**Prevents over-concentration** in any single category

### 3. AI Validation (SWING only)

**Claude AI analyzes**:
- Weekly chart patterns
- Support/resistance levels
- Trend strength
- Risk/reward ratio

**Output**:
- `ai_agrees`: Boolean (True/False)
- `ai_confidence`: Float (0.0-1.0)
- `ai_reasoning`: Text explanation

**Example**:
```json
{
  "ai_agrees": true,
  "ai_confidence": 0.85,
  "ai_reasoning": "Strong uptrend with bullish MACD crossover. Support at ₹450. Target ₹520 realistic."
}
```

### 4. Time-Based Exits

**DAILY Strategy**:
- Force exit ALL positions at **3:25 PM IST**
- Prevents overnight risk
- Locks in day's gains/losses

**SWING Strategy**:
- Max hold: **10 days**
- Prevents dead capital in stagnant positions
- Exit regardless of profit/loss after 10 days

### 5. RS Rating Filter

**Relative Strength Rating (1-99)**:
- Ranks stock vs. entire universe
- Based on 3M, 6M, 9M, 12M returns
- Weighted average with recent performance emphasized

**Thresholds**:
- DAILY: Min RS >= 60 (top 40% stocks)
- SWING: Min RS >= 65 (top 35% stocks)

**Filters out weak performers** before trade consideration

### 6. Profit Lock Mechanism

**Automatic Profit Protection**:
- When position closed with profit → transfer to `total_profits_locked`
- Locked profits **never re-enter trading pool**
- Only losses deducted from `current_trading_capital`

**Example Flow**:
```
Starting capital: ₹13,00,000

Trade 1: +₹50,000 profit
  → current_trading_capital: ₹13,00,000
  → total_profits_locked: ₹50,000

Trade 2: -₹20,000 loss
  → current_trading_capital: ₹12,80,000
  → total_profits_locked: ₹50,000

Net: ₹12,80,000 (trading) + ₹50,000 (locked) = ₹13,30,000 total
```

### 7. Database Constraints

**Referential Integrity**:
- Foreign keys ensure data consistency
- Unique constraints prevent duplicate entries
- Timestamps track all changes

**Example Constraints**:
```sql
-- Prevent duplicate active positions
UNIQUE (ticker, strategy) WHERE status = 'HOLD'

-- Ensure capital never negative
CHECK (current_trading_capital >= 0)

-- Valid strategy values only
CHECK (strategy IN ('DAILY', 'SWING'))
```

---

## Next Steps

- **02-DATABASE-SCHEMA.md** → Database tables, columns, and queries
- **03-SCREENING-SCORING.md** → How stocks are selected and scored
- **04-DAILY-STRATEGY.md** → Deep dive into DAILY trading
- **05-SWING-STRATEGY.md** → Deep dive into SWING trading

---

**Last Updated**: 2024-11-13  
**Version**: 2.0  
**Maintainer**: LightRain System
