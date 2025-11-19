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

### Time Zone
- **AWS Server Timezone**: IST (Indian Standard Time)
- **All cron times are in IST**

### Complete Cron Schedule

| IST Time | Cron Expression | Script | Purpose |
|----------|-----------------|--------|---------|
| 8:30 AM | `30 8 * * 1-5` | `run_market_check.sh` | Global regime check (save to file + DB) |
| 8:30 AM | `30 8 * * 1-5` | `run_stocks_screening.sh` | Pre-market stock screening |
| 9:00 AM | `0 9 * * 1-5` | `run_daily_trading.sh` | DAILY strategy execution |
| 9:00 AM | `0 9 * * 1-5` | `daily_screening.py` | Real-time daily screening |
| 9:00-3:30 PM | `*/5 9-15 * * 1-5` | `monitor_swing_pg.py` | Swing position monitoring (every 5 min) |
| 9:00-3:30 PM | `*/5 9-15 * * 1-5` | `monitor_daily.py` | Daily position monitoring (every 5 min) |
| 9:00-3:30 PM | `*/5 9-15 * * 1-5` | `monitor_positions.py` | Legacy position monitor (every 5 min) |
| 9:25 AM | `25 9 * * 1-5` | `run_swing_trading.sh` | SWING strategy execution |
| 2:00 PM | `0 14 * * 1-5` | `regime_2pm_check.py` | Intraday regime deterioration check |
| 3:00 PM | `0 15 * * 1-5` | `check_max_hold_warnings.py` | MAX-HOLD warning + AI analysis |
| 3:30 PM | `30 15 * * 1-5` | `run_eod_summary.sh` | End-of-day capital snapshot |
| 4:00 PM | `0 16 * * 1-5` | `run_eod_report.sh` | Daily performance report |

**Note**: All jobs run Monday-Friday only. Server timezone is IST.

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
