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

### Complete Cron Schedule

**All times in IST (Indian Standard Time)**

| Time (IST) | Script | Purpose |
|------------|--------|---------|
| 8:30 AM | `run_market_check.sh` | Global regime check (save to file + DB) |
| 8:30 AM | `run_stocks_screening.sh` | Pre-market stock screening |
| 9:00 AM | `run_daily_trading.sh` | DAILY strategy execution |
| 9:00 AM | `daily_screening.py` | Real-time daily screening |
| 9:00-3:30 PM (every 5 min) | `monitor_swing_pg.py` | Swing position monitoring |
| 9:00-3:30 PM (every 5 min) | `monitor_daily.py` | Daily position monitoring |
| 9:00-3:30 PM (every 5 min) | `monitor_positions.py` | Legacy position monitor |
| 9:25 AM | `run_swing_trading.sh` | SWING strategy execution |
| 2:00 PM | `regime_2pm_check.py` | Intraday regime deterioration check |
| 3:00 PM | `check_max_hold_warnings.py` | MAX-HOLD warning + AI analysis |
| 3:30 PM | `run_eod_summary.sh` | End-of-day summary (both strategies) |

**Note**: All jobs run Monday-Friday only.

### View Current Crontab
```bash
crontab -l
```

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

### Intraday Checks

#### MAX-HOLD Warning Check
**Schedule**: 3:00 PM IST (9:30 AM UTC)
**Script**: `check_max_hold_warnings.py`
- Alerts on positions approaching MAX-HOLD limit
- DAILY: Alerts on day 2 positions (will exit day 3)
- SWING: Alerts on day 9 positions (will exit day 10)
- Includes AI analysis with news for each position
- Gives 30 minutes before market close to decide

#### 2PM Regime Deterioration Check
**Schedule**: 2:00 PM IST (8:30 AM UTC)
**Script**: `regime_2pm_check.py`
- Monitors intraday regime changes
- Alerts if regime deteriorates significantly from morning
- Recommends /exitall if severe deterioration detected

---

## EOD Processing

### End-of-Day Summary
**Schedule**: 3:30 PM IST
**Script**: `run_eod_summary.sh`
- Takes capital snapshot for both DAILY and SWING strategies
- Calculates daily P&L
- Records EOD positions
- Sends Telegram summary with performance metrics

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
