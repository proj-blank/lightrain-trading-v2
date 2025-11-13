# LightRain Trading System

**Automated algorithmic trading system for NSE stocks with dual-strategy execution (Daily + Swing), PostgreSQL backend, and Telegram integration.**

---

## Quick Stats

- **Capital**: ₹500,000
- **Strategies**: Daily (short-term) + Swing (5-20 days)
- **Universe**: Nifty 500 (Large-cap, Mid-cap, Microcap)
- **Allocation**: 60% Large-cap | 20% Mid-cap | 20% Microcap
- **Max Positions**: 19 total (Daily: 6, Swing: 13)
- **Risk Management**: 5% stop-loss, multi-level take-profits, circuit breakers

---

## Documentation

### Getting Started
- [00-QUICKSTART.md](docs/00-QUICKSTART.md) - 5-minute setup guide

### Core Documentation
- [01-SYSTEM-OVERVIEW.md](docs/01-SYSTEM-OVERVIEW.md) - Architecture, strategies, workflow
- [02-DATABASE-SCHEMA.md](docs/02-DATABASE-SCHEMA.md) - PostgreSQL tables, relationships, queries
- [03-SCREENING-SCORING.md](docs/03-SCREENING-SCORING.md) - Stock selection, indicators, scoring

### Strategy Deep Dives
- [04-DAILY-STRATEGY.md](docs/04-DAILY-STRATEGY.md) - Daily strategy details, execution
- [05-SWING-STRATEGY.md](docs/05-SWING-STRATEGY.md) - Swing strategy details, execution

### Operations
- [06-POSITION-MANAGEMENT.md](docs/06-POSITION-MANAGEMENT.md) - Entry/exit, TP/SL, circuit breakers
- [07-CAPITAL-TRACKER.md](docs/07-CAPITAL-TRACKER.md) - Capital flows, profit locking, P&L
- [08-MONITORING-CRON.md](docs/08-MONITORING-CRON.md) - Automation, cron schedule, logs

### Tools & APIs
- [09-TELEGRAM-BOT.md](docs/09-TELEGRAM-BOT.md) - All commands, alerts, features
- [10-DATA-SOURCES.md](docs/10-DATA-SOURCES.md) - yfinance, Angel One API, reliability
- [11-TROUBLESHOOTING.md](docs/11-TROUBLESHOOTING.md) - Common issues, debugging, fixes

---

## Quick Setup

### Prerequisites
```bash
# Ubuntu 20.04+, Python 3.8+, PostgreSQL 12+
sudo apt update
sudo apt install python3 python3-pip python3-venv postgresql postgresql-contrib
```

### Installation
```bash
# 1. Clone/setup repository
cd ~/trading

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
nano .env  # Add your API keys

# 5. Setup database
sudo -u postgres psql < setup_database.sql

# 6. Start Telegram bot
nohup python3 telegram_bot_listener.py >> logs/telegram_bot.log 2>&1 &

# 7. Setup cron jobs
crontab -e  # Copy from crontab.txt
```

---

## Telegram Commands

### Information
- `/help` - Show all commands
- `/status` - System overview + live indices
- `/positions` - All active positions
- `/pnl` - Detailed P&L breakdown
- `/cap` - Capital tracker summary

### Control
- `/hold TICKER` - Suppress exit signals (hold position)
- `/exit TICKER` - Force immediate exit

### Strategy-Specific
- `/daily` - Show Daily positions only
- `/swing` - Show Swing positions only

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LIGHTRAIN TRADING SYSTEM                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │   yfinance   │      │  Angel One   │                    │
│  │  (Historical)│      │  (Real-time) │                    │
│  └──────┬───────┘      └──────┬───────┘                    │
│         │                     │                            │
│         ▼                     ▼                            │
│  ┌─────────────────────────────────────┐                   │
│  │       SCREENING & SCORING           │                   │
│  │  - Technical indicators (12 total)  │                   │
│  │  - RS Rating (relative strength)    │                   │
│  │  - Global sentiment filter          │                   │
│  └──────────────┬──────────────────────┘                   │
│                 │                                           │
│        ┌────────┴────────┐                                 │
│        ▼                 ▼                                 │
│  ┌──────────┐      ┌──────────┐                            │
│  │  DAILY   │      │  SWING   │                            │
│  │ STRATEGY │      │ STRATEGY │                            │
│  │ (1 day)  │      │(5-20 days)│                           │
│  └────┬─────┘      └────┬─────┘                            │
│       │                 │                                   │
│       └────────┬────────┘                                   │
│                ▼                                            │
│  ┌─────────────────────────────┐                           │
│  │   POSITION MANAGEMENT       │                           │
│  │  - TP/SL monitoring         │                           │
│  │  - Circuit breakers         │                           │
│  │  - Capital tracking         │                           │
│  └──────────────┬──────────────┘                           │
│                 │                                           │
│                 ▼                                           │
│  ┌─────────────────────────────┐                           │
│  │    POSTGRESQL DATABASE      │                           │
│  │  - positions                │                           │
│  │  - trades_log               │                           │
│  │  - capital_tracker          │                           │
│  └──────────────┬──────────────┘                           │
│                 │                                           │
│                 ▼                                           │
│  ┌─────────────────────────────┐                           │
│  │      TELEGRAM BOT           │                           │
│  │  - Real-time alerts         │                           │
│  │  - Manual control           │                           │
│  │  - Performance tracking     │                           │
│  └─────────────────────────────┘                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Daily Workflow

### 8:30 AM IST - Pre-Market
1. Global market sentiment check (S&P 500, Nasdaq)
2. Stock screening (Nifty 500 universe)
3. Signal generation with scoring

### 9:00 AM IST - Market Open
1. Daily strategy execution (6 positions max)
2. Real-time screening with market data

### 9:25 AM IST - Post-Open
1. Swing strategy execution (13 positions max)
2. Portfolio balancing by category

### 9:00 AM - 3:30 PM - Intraday
1. Position monitoring (every 5 minutes)
2. TP/SL checking
3. Circuit breaker detection
4. Telegram alerts

### 3:30 PM IST - Market Close
1. EOD capital snapshot
2. Daily P&L calculation
3. Benchmark tracking

### 4:00 PM IST - Post-Market
1. Telegram EOD report
2. Performance summary
3. Position review

---

## Key Features

### Risk Management
- **Stop Loss**: 5% hard stop from entry
- **Take Profit**: 3 levels (10%, 20%, 30%)
- **Circuit Breaker**: 5% intraday drop triggers hold
- **Position Sizing**: Volatility-adjusted (ATR-based)

### Capital Management
- **Total Capital**: ₹500,000
- **Category Limits**: 60/20/20 split
- **Position Limits**: 19 total positions max
- **Profit Locking**: Partial exits at TP levels

### Data Sources
- **Historical**: yfinance (6 months daily OHLCV)
- **Real-time**: Angel One API (live quotes)
- **Benchmarks**: Nifty 50, Mid 150, Small 250

### Automation
- **Cron Jobs**: 11 scheduled tasks
- **Position Monitoring**: Every 5 minutes
- **Telegram Bot**: 24/7 listening
- **EOD Processing**: Automatic snapshots

---

## Performance Tracking

### Metrics
- Daily P&L (amount + percentage)
- Win rate per strategy
- Average hold period
- Sharpe ratio
- Max drawdown
- Portfolio vs benchmarks

### Database Queries
```sql
-- Today's P&L
SELECT SUM(locked_profits) - SUM(realized_losses) AS net_pnl
FROM capital_tracker
WHERE snapshot_date = CURRENT_DATE;

-- Win rate (last 30 days)
SELECT 
    COUNT(CASE WHEN pnl > 0 THEN 1 END)::FLOAT / COUNT(*) AS win_rate
FROM trades_log
WHERE exit_date >= CURRENT_DATE - INTERVAL '30 days';

-- Best performing positions
SELECT ticker, 
    ((exit_price - entry_price) / entry_price * 100) AS return_pct
FROM trades_log
WHERE exit_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY return_pct DESC
LIMIT 10;
```

---

## File Structure

```
~/trading/
├── README.md                      # This file
├── requirements.txt               # Python dependencies
├── crontab.txt                    # Cron schedule reference
├── .env                           # Environment variables (credentials)
├── .gitignore                     # Git ignore rules
│
├── docs/                          # Documentation
│   ├── 00-QUICKSTART.md
│   ├── 01-SYSTEM-OVERVIEW.md
│   ├── 02-DATABASE-SCHEMA.md
│   ├── 03-SCREENING-SCORING.md
│   ├── 04-DAILY-STRATEGY.md
│   ├── 05-SWING-STRATEGY.md
│   ├── 06-POSITION-MANAGEMENT.md
│   ├── 07-CAPITAL-TRACKER.md
│   ├── 08-MONITORING-CRON.md
│   ├── 09-TELEGRAM-BOT.md
│   ├── 10-DATA-SOURCES.md
│   └── 11-TROUBLESHOOTING.md
│
├── scripts/                       # Core modules
│   ├── db_connection.py           # Database operations
│   ├── telegram_bot.py            # Telegram messaging
│   ├── signal_generator_daily.py  # Daily signals
│   ├── signal_generator_swing.py  # Swing signals
│   ├── risk_manager.py            # TP/SL/circuit breakers
│   ├── data_loader_angelone.py    # Angel One data
│   ├── percentage_based_allocation.py # Portfolio allocation
│   └── ... (20+ modules)
│
├── daily_trading_pg.py            # Daily strategy executor
├── swing_trading_pg.py            # Swing strategy executor
├── monitor_swing_pg.py            # Swing position monitor
├── monitor_daily.py               # Daily position monitor
├── telegram_bot_listener.py       # Bot command listener
├── eod_summary.py                 # End-of-day summary
│
├── run_daily_trading.sh           # Shell wrappers for cron
├── run_swing_trading.sh
├── run_eod_summary.sh
└── logs/                          # All system logs
    ├── monitor_swing.log
    ├── daily_trading_cron.log
    └── ... (10+ log files)
```

---

## Environment Variables

Required in `.env`:
```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=trading_db
DB_USER=postgres
DB_PASSWORD=your_password

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Angel One
ANGELONE_API_KEY=your_api_key
ANGELONE_CLIENT_ID=your_client_id
ANGELONE_PASSWORD=your_password
ANGELONE_TOTP_SECRET=your_totp_secret
```

---

## Maintenance

### Daily
- Monitor Telegram alerts
- Check position status: `/positions`
- Review EOD report

### Weekly
- Check log file sizes: `ls -lh logs/`
- Verify cron jobs: `crontab -l`
- Review capital tracker trends

### Monthly
- Analyze performance metrics
- Rebalance category allocations (if needed)
- Clean old logs: `find logs/ -mtime +30 -delete`

---

## License

Private trading system. Not for distribution.

---

## Contact

- Telegram Bot: @your_bot_name
- AWS Instance: ubuntu@13.235.86.250
- Location: ~/trading/

---

**Last Updated**: 2024-11-13

**Version**: 1.0.0

**Status**: Production
