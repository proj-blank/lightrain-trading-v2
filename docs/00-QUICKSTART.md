# LightRain Trading System - Quick Start Guide

**Last Updated**: 2024-11-13  
**Purpose**: Get connected and verify system status in under 2 minutes

---

## 1. Connect to AWS Server

```bash
# SSH into AWS EC2
ssh -i ~/Downloads/projectbank-1.pem ubuntu@13.235.86.250

# Switch to trading directory
cd ~/trading
```

**Server Details:**
- **IP**: 13.235.86.250
- **User**: ubuntu
- **SSH Key**: `~/Downloads/projectbank-1.pem`
- **Region**: AWS Mumbai (ap-south-1)
- **Instance Type**: t2.micro (free tier)

---

## 2. Database Access

### PostgreSQL Connection
```bash
# Connect to database
python3 -c "from scripts.db_connection import get_db_cursor; \
with get_db_cursor() as cur: \
    cur.execute('SELECT NOW()'); \
    print('✅ Database connected:', cur.fetchone())"
```

**Database Details:**
- **Name**: lightrain
- **Host**: lightrain.crj4y7ulwktj.ap-south-1.rds.amazonaws.com
- **Port**: 5432
- **User**: postgres
- **Password**: (stored in scripts/db_connection.py)

### Quick Status Check
```bash
# Check capital status
cd ~/trading && python3 << 'EOF'
from scripts.db_connection import get_db_cursor

with get_db_cursor() as cur:
    # Capital status
    cur.execute("""
        SELECT strategy, 
               current_trading_capital as available,
               total_profits_locked as locked,
               total_losses as losses
        FROM capital_tracker
        ORDER BY strategy
    """)
    print("💰 CAPITAL STATUS:")
    print("="*60)
    for row in cur.fetchall():
        avail = float(row['available'])
        locked = float(row['locked'])
        losses = float(row['losses'])
        total = avail + locked - losses
        print(f"{row['strategy']:6} | Available: ₹{avail:,.0f} | Locked: ₹{locked:,.0f} | Total: ₹{total:,.0f}")
    
    # Position count
    cur.execute("""
        SELECT strategy, status, COUNT(*) as count
        FROM positions
        GROUP BY strategy, status
        ORDER BY strategy, status
    """)
    print("\n📊 POSITIONS:")
    print("="*60)
    for row in cur.fetchall():
        print(f"{row['strategy']:6} | {row['status']:6} | {row['count']} positions")
EOF
```

---

## 3. System Status Checks

### Check Running Processes
```bash
# Telegram bot status
ps aux | grep telegram_bot_listener | grep -v grep

# Monitor scripts (during market hours)
ps aux | grep monitor_ | grep -v grep
```

### Check Cron Jobs
```bash
# View crontab
crontab -l

# Check cron logs
ls -lht logs/*.log | head -10
tail -20 logs/telegram_bot.log
```

### Market Hours Schedule (IST)
```
8:30 AM  - Pre-market screening
9:00 AM  - DAILY trading + screening
9:25 AM  - SWING trading
9:00-3:30 - Position monitors (every 5 min)
3:30 PM  - EOD summary
4:00 PM  - EOD report
```

---

## 4. Emergency Commands

### Restart Telegram Bot
```bash
# Kill old bot
ps aux | grep telegram_bot_listener | grep -v grep | awk '{print $2}' | xargs -r kill

# Start new bot
cd ~/trading && nohup python3 telegram_bot_listener.py > logs/telegram_bot.log 2>&1 &

# Verify
ps aux | grep telegram_bot_listener | grep -v grep
tail -10 logs/telegram_bot.log
```

### Check Logs for Errors
```bash
# Recent errors across all logs
grep -i error logs/*.log | tail -20

# Specific script logs
tail -50 logs/daily_trading_cron.log
tail -50 logs/swing_trading_cron.log
tail -50 logs/monitor_daily.log
```

### Manual Trade Execution
```bash
# Run DAILY trading manually
cd ~/trading && bash run_daily_trading.sh

# Run SWING trading manually  
cd ~/trading && bash run_swing_trading.sh

# Run monitors manually
cd ~/trading && python3 monitor_daily.py
cd ~/trading && python3 monitor_swing_pg.py
```

---

## 5. Telegram Bot Commands

**Connect to bot**: Search for your bot on Telegram

**Key Commands:**
```
/status  - System health check
/pos     - Current positions
/cap     - Capital tracker
/pnl     - Unrealized P&L
/today   - Today's summary
/help    - All commands
```

---

## 6. File Locations Map

```
~/trading/
├── scripts/               # Core modules
│   ├── db_connection.py   # Database operations
│   ├── risk_manager.py    # TP/SL calculations
│   └── telegram_bot.py    # Bot utilities
│
├── Main Trading Scripts:
│   ├── daily_trading_pg.py      # DAILY strategy entry
│   ├── swing_trading_pg.py      # SWING strategy entry
│   ├── monitor_daily.py         # DAILY monitoring
│   ├── monitor_swing_pg.py      # SWING monitoring
│   └── telegram_bot_listener.py # Telegram bot
│
├── Screening:
│   ├── daily_screening.py       # Intraday candidates
│   └── stocks_screening_pg.py   # SWING candidates
│
├── EOD:
│   ├── eod_summary.py          # Daily summary
│   └── eod_report.py           # Detailed report
│
├── Shell Scripts:
│   ├── run_daily_trading.sh
│   ├── run_swing_trading.sh
│   └── run_eod_summary.sh
│
└── logs/                  # All execution logs
```

---

## 7. Common Issues & Quick Fixes

### Issue: Telegram bot not responding
```bash
# Restart bot (see section 4)
pkill -f telegram_bot_listener
cd ~/trading && nohup python3 telegram_bot_listener.py > logs/telegram_bot.log 2>&1 &
```

### Issue: Database connection error
```bash
# Test connection
cd ~/trading && python3 -c "from scripts.db_connection import get_db_cursor; \
with get_db_cursor() as cur: cur.execute('SELECT 1')"

# Check RDS status on AWS console if fails
```

### Issue: Positions not updating
```bash
# Manually run monitors
cd ~/trading && python3 monitor_daily.py
cd ~/trading && python3 monitor_swing_pg.py

# Check unrealized P&L updated
python3 -c "from scripts.db_connection import get_db_cursor; \
with get_db_cursor() as cur: \
    cur.execute('SELECT strategy, SUM(unrealized_pnl) FROM positions WHERE status='HOLD' GROUP BY strategy'); \
    print(cur.fetchall())"
```

### Issue: Trading not executing at scheduled time
```bash
# Check cron is running
sudo systemctl status cron

# Verify cron times (remember: cron uses UTC, India is UTC+5:30)
crontab -l

# Check recent cron execution
ls -lt logs/*_cron.log | head -5
```

---

## 8. Key Metrics to Monitor

**Daily Health Check (Every Morning):**
1. Telegram bot responding? (`/status`)
2. Last night's EOD report generated? (check logs)
3. Capital levels correct? (`/cap`)
4. Any positions stuck? (`/pos`)
5. Monitor scripts running? (`ps aux | grep monitor`)

**During Market Hours:**
1. Monitors running every 5 min?
2. Telegram alerts coming through?
3. Unrealized P&L tracking correctly?

**After Market Close:**
1. EOD summary generated? (3:30 PM IST)
2. All positions closed if TP/SL hit?
3. Capital locked if profits made?

---

## 9. Documentation Index

- **00-QUICKSTART.md** ← You are here
- **01-SYSTEM-OVERVIEW.md** - Architecture & data flow
- **02-DATABASE-SCHEMA.md** - Tables & queries
- **03-SCREENING-SCORING.md** - How stocks are selected
- **04-DAILY-STRATEGY.md** - Intraday trading logic
- **05-SWING-STRATEGY.md** - Multi-day trading logic
- **06-POSITION-MANAGEMENT.md** - TP/SL & exits
- **07-CAPITAL-TRACKER.md** - Money flow
- **08-MONITORING-CRON.md** - Automation
- **09-TELEGRAM-BOT.md** - Bot features
- **10-DATA-SOURCES.md** - AngelOne & yfinance
- **11-TROUBLESHOOTING.md** - Common problems

---

## 10. Git Repository

**Clone locally:**
```bash
cd ~/project_blank
git clone https://github.com/YOUR_USERNAME/lightrain-trading.git
```

**Pull latest changes:**
```bash
cd ~/project_blank/lightrain-trading
git pull
```

**On AWS - commit changes:**
```bash
cd ~/trading
git add .
git commit -m "Description of changes"
git push
```

---

**Need More Help?** See 01-SYSTEM-OVERVIEW.md for high-level architecture or 11-TROUBLESHOOTING.md for specific issues.
