# 08 - Monitoring & Cron

Complete automation schedule, cron setup, monitoring scripts, and log management.

---

## Table of Contents
1. [Cron Schedule Overview](#cron-schedule-overview)
2. [Position Monitors](#position-monitors)
3. [Trading Execution](#trading-execution)
4. [EOD Processing](#eod-processing)
5. [Log Management](#log-management)

---

## Cron Schedule Overview

### Time Zone Configuration
- **System Time**: IST (Indian Standard Time)
- **Cron Interprets**: UTC
- **Conversion**: IST = UTC + 5:30

### Full Schedule
View: `crontab -l` or `cat ~/trading/crontab.txt`

---

## Position Monitors

### Swing Monitor
**Schedule**: Every 5 minutes during market hours (9:00 AM - 3:30 PM IST)

Track swing positions, check TP/SL levels, detect circuit breakers, send Telegram alerts.

### Daily Monitor
**Schedule**: Every 5 minutes during market hours

Track daily positions with more aggressive exit rules. Close all at 3:15 PM if SELL signal.

---

## Trading Execution

### Pre-Market Checks
**Schedule**: 8:30 AM IST (3:00 AM UTC)
- Market check (global sentiment)
- Stock screening

### Market Open Execution
**Schedule**: 9:00 AM IST (3:30 AM UTC)
- Daily trading execution
- Daily screening (real-time)

### Swing Execution
**Schedule**: 9:25 AM IST (3:55 AM UTC)
- Execute swing strategy positions after market stabilizes

---

## EOD Processing

### Market Close Summary
**Schedule**: 3:30 PM IST (10:00 AM UTC)
- Take capital snapshot
- Calculate daily P&L
- Record EOD positions

### Final Report
**Schedule**: 4:00 PM IST (10:30 AM UTC)
- Send Telegram EOD summary
- Performance metrics

---

## Log Management

### Log Directory
All logs in `~/trading/logs/`:
- monitor_swing.log
- monitor_daily.log
- daily_trading_cron.log
- swing_trading_cron.log
- eod_summary.log

### Log Commands
- View last 50 lines: `tail -50 logs/monitor_swing.log`
- Real-time monitoring: `tail -f logs/monitor_swing.log`
- Find errors: `grep -i error logs/*.log`

---

## Key Files

### Monitoring Scripts
- `monitor_swing_pg.py`: Swing position monitoring
- `monitor_daily.py`: Daily position monitoring
- `telegram_bot_listener.py`: Command listener (24/7)

### Shell Scripts
- `run_daily_trading.sh`
- `run_swing_trading.sh`
- `run_eod_summary.sh`
- `run_market_check.sh`

---

**Next**: [09-TELEGRAM-BOT.md](09-TELEGRAM-BOT.md) - Telegram bot commands
