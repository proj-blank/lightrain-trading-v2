# 11 - Troubleshooting

Common issues, fixes, and debugging guide for LightRain trading system.

---

## Table of Contents
1. [Database Issues](#database-issues)
2. [Data Fetching Issues](#data-fetching-issues)
3. [Cron Issues](#cron-issues)
4. [Telegram Bot Issues](#telegram-bot-issues)
5. [Position Management Issues](#position-management-issues)
6. [Debugging Tools](#debugging-tools)

---

## Database Issues

### Cannot Connect to Database
**Symptoms**:
```
psycopg2.OperationalError: could not connect to server
```

**Solutions**:
```bash
# 1. Check if PostgreSQL is running
sudo systemctl status postgresql

# 2. Start PostgreSQL if stopped
sudo systemctl start postgresql

# 3. Check connection settings
cat ~/trading/.env | grep DB

# 4. Test connection manually
psql -h localhost -U postgres -d trading_db -c "SELECT 1;"
```

### Table Not Found
**Symptoms**:
```
psycopg2.errors.UndefinedTable: relation "positions" does not exist
```

**Solutions**:
```bash
# 1. Check if database exists
psql -h localhost -U postgres -l | grep trading

# 2. Recreate tables (if needed)
psql -h localhost -U postgres -d trading_db -f ~/trading/schema.sql

# 3. Verify tables exist
psql -h localhost -U postgres -d trading_db -c "\dt"
```

### Duplicate Position Error
**Symptoms**:
```
psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint
```

**Solutions**:
```sql
-- Check for existing position
SELECT * FROM positions WHERE ticker = 'RELIANCE' AND status = 'HOLD';

-- Close duplicate manually (if needed)
UPDATE positions SET status = 'CLOSED' WHERE position_id = 123;
```

---

## Data Fetching Issues

### yfinance: No Data Returned
**Symptoms**:
```python
df.empty == True
```

**Solutions**:
```python
# 1. Check ticker format (must include .NS for NSE)
df = yf.download('RELIANCE.NS', period='6mo')  # Correct
df = yf.download('RELIANCE', period='6mo')     # Wrong

# 2. Try different period
df = yf.download('RELIANCE.NS', period='1y')

# 3. Check internet connection
ping yahoo.com
```

### yfinance: Rate Limited (429 Error)
**Symptoms**:
```
HTTP Error 429: Too Many Requests
```

**Solutions**:
```python
# Add delays between requests
import time
for ticker in tickers:
    df = yf.download(ticker, period='6mo')
    time.sleep(0.5)  # Wait 500ms
```

### Angel One: Session Expired
**Symptoms**:
```
Exception: Session expired or invalid
```

**Solutions**:
```python
# 1. Check TOTP secret
echo $ANGELONE_TOTP_SECRET

# 2. Re-login
python3 test_angelone_connection.py

# 3. Verify credentials in .env
cat ~/trading/.env | grep ANGELONE
```

### Angel One: Invalid Token
**Symptoms**:
```
Exception: Invalid symbol token
```

**Solutions**:
```bash
# Rebuild token mapping
cd ~/trading
python3 setup_angelone_symbols.py

# Verify mapping in database
psql -h localhost -U postgres -d trading_db -c "SELECT * FROM angelone_symbols LIMIT 10;"
```

---

## Cron Issues

### Cron Jobs Not Running
**Symptoms**:
- No logs generated
- Scripts not executing

**Solutions**:
```bash
# 1. Check cron service
sudo systemctl status cron

# 2. Restart cron
sudo systemctl restart cron

# 3. Check crontab syntax
crontab -l

# 4. View cron logs
grep CRON /var/log/syslog | tail -20
```

### Script Running But Failing
**Symptoms**:
- Logs show errors
- Positions not updating

**Solutions**:
```bash
# 1. Check log files
tail -50 logs/daily_trading_cron.log
tail -50 logs/monitor_swing.log

# 2. Test script manually
cd ~/trading
source venv/bin/activate
python3 daily_trading_pg.py

# 3. Check Python errors
grep -i "error\|exception" logs/*.log
```

### Timezone Issues
**Symptoms**:
- Scripts running at wrong times

**Solutions**:
```bash
# 1. Check system timezone
timedatectl

# 2. Verify cron times (cron uses UTC)
# IST = UTC + 5:30
# 9:00 AM IST = 3:30 AM UTC

# 3. Update crontab if needed
crontab -e
```

---

## Telegram Bot Issues

### Bot Not Responding
**Symptoms**:
- Commands don't return responses

**Solutions**:
```bash
# 1. Check if bot is running
ps aux | grep telegram_bot_listener

# 2. Restart bot
pkill -f telegram_bot_listener.py
cd ~/trading && nohup python3 telegram_bot_listener.py >> logs/telegram_bot.log 2>&1 &

# 3. Check bot logs
tail -50 logs/telegram_bot.log
```

### Bot Not Sending Alerts
**Symptoms**:
- Position alerts not received

**Solutions**:
```bash
# 1. Test message sending
cd ~/trading
python3 -c "from scripts.telegram_bot import send_telegram_message; send_telegram_message('Test')"

# 2. Check environment variables
cat ~/trading/.env | grep TELEGRAM

# 3. Verify chat ID
echo $TELEGRAM_CHAT_ID
```

### Bot Token Invalid
**Symptoms**:
```
telegram.error.Unauthorized: 401 Unauthorized
```

**Solutions**:
```bash
# 1. Verify bot token
cat ~/trading/.env | grep TELEGRAM_BOT_TOKEN

# 2. Get new token from @BotFather (if needed)

# 3. Update .env
nano ~/trading/.env
```

### Live Market Indices Not Showing
**Symptoms**:
- `/pnl` command shows "Market data temporarily unavailable"
- Happens daily after bot has been running >24 hours

**Root Cause**:
- AngelOne API sessions expire after 24 hours
- Bot was caching expired session and not refreshing

**Solution** (Fixed as of Nov 14, 2025):
The telegram bot now auto-refreshes AngelOne sessions:
- Tracks session age
- Auto-refreshes when >23 hours old
- Retries API calls with fresh session on failure

**Verification**:
```bash
# Check bot logs for session refresh messages
tail -50 ~/trading/logs/telegram_bot.log | grep -i "angel"

# Should see:
# "Creating new Angel One session..."
# "Angel One session created successfully"
```

**Manual Restart** (if needed):
```bash
# Restart bot to force new session
pkill -f telegram_bot_listener.py
cd ~/trading && nohup python3 telegram_bot_listener.py > logs/telegram_bot.log 2>&1 &
```

---

## Position Management Issues

### Position Not Entering
**Symptoms**:
- BUY signal generated but position not added

**Solutions**:
```python
# 1. Check available cash
from scripts.db_connection import get_available_cash
print(get_available_cash())

# 2. Check category allocation
# Verify not hitting max positions per category

# 3. Check logs
tail -50 logs/daily_trading_cron.log
```

### Position Not Exiting
**Symptoms**:
- Stop loss hit but position still HOLD

**Solutions**:
```bash
# 1. Check if position is on hold
psql -h localhost -U postgres -d trading_db -c \
  "SELECT * FROM circuit_breaker_holds WHERE ticker = 'RELIANCE';"

# 2. Force exit via Telegram
/exit RELIANCE

# 3. Check monitor logs
tail -50 logs/monitor_swing.log
```

### Take Profit Not Triggering
**Symptoms**:
- Price above TP level but no partial exit

**Solutions**:
```python
# 1. Verify TP levels in database
SELECT ticker, entry_price, take_profit FROM positions WHERE ticker = 'RELIANCE';

# 2. Check monitor script running
ps aux | grep monitor_swing_pg

# 3. Check current price fetch
python3 -c "import yfinance as yf; print(yf.Ticker('RELIANCE.NS').history(period='1d')['Close'].iloc[-1])"
```

---

## Debugging Tools

### Check Active Positions
```bash
psql -h localhost -U postgres -d trading_db -c \
  "SELECT ticker, strategy, entry_price, current_price, quantity, status FROM positions WHERE status = 'HOLD';"
```

### Check Capital Tracker
```bash
psql -h localhost -U postgres -d trading_db -c \
  "SELECT * FROM capital_tracker ORDER BY snapshot_date DESC, snapshot_time DESC LIMIT 5;"
```

### Check Today's Trades
```bash
psql -h localhost -U postgres -d trading_db -c \
  "SELECT * FROM trades_log WHERE entry_date = CURRENT_DATE;"
```

### Check Circuit Breaker Holds
```bash
psql -h localhost -U postgres -d trading_db -c \
  "SELECT * FROM circuit_breaker_holds WHERE hold_date = CURRENT_DATE;"
```

### Test Price Fetching
```python
# Test yfinance
python3 -c "import yfinance as yf; print(yf.download('TCS.NS', period='1d'))"

# Test Angel One
cd ~/trading
python3 test_angelone_connection.py
```

### View Logs in Real-Time
```bash
# Monitor all monitors
tail -f logs/monitor_*.log

# Monitor trading execution
tail -f logs/daily_trading_cron.log logs/swing_trading_cron.log
```

---

## Emergency Procedures

### Stop All Trading
```bash
# 1. Disable cron jobs
crontab -e
# Comment out all trading/monitoring jobs

# 2. Stop bot
pkill -f telegram_bot_listener.py

# 3. Close all positions (if needed)
# Use Telegram: /exit TICKER for each position
```

### Reset System
```bash
# 1. Stop all processes
pkill -f telegram_bot_listener.py
crontab -e  # Disable all jobs

# 2. Check database state
psql -h localhost -U postgres -d trading_db -c "SELECT COUNT(*) FROM positions WHERE status = 'HOLD';"

# 3. Re-enable gradually
# Start with monitors only, then add trading
```

### Recover from Crash
```bash
# 1. Check system logs
tail -100 /var/log/syslog

# 2. Check Python errors
grep -i "traceback\|exception" logs/*.log | tail -50

# 3. Restart services
sudo systemctl restart cron
sudo systemctl restart postgresql
cd ~/trading && nohup python3 telegram_bot_listener.py >> logs/telegram_bot.log 2>&1 &
```

---

## Preventive Measures

### Daily Health Checks
```bash
# 1. Check cron running
sudo systemctl status cron

# 2. Check database
psql -h localhost -U postgres -d trading_db -c "SELECT 1;"

# 3. Check bot
ps aux | grep telegram_bot_listener

# 4. Check disk space
df -h

# 5. Check recent logs
ls -lt logs/ | head -10
```

### Weekly Maintenance
```bash
# 1. Clean old logs
find logs/ -name "*.log" -mtime +30 -delete

# 2. Vacuum database
psql -h localhost -U postgres -d trading_db -c "VACUUM ANALYZE;"

# 3. Check for stale processes
ps aux | grep python

# 4. Update dependencies (if needed)
cd ~/trading
source venv/bin/activate
pip list --outdated
```

---

## Getting Help

### Log Files to Check
1. `logs/monitor_swing.log`
2. `logs/daily_trading_cron.log`
3. `logs/telegram_bot.log`
4. `/var/log/syslog`

### Information to Gather
- Error messages (full traceback)
- Recent log entries (50 lines)
- Database state (position counts)
- System status (cron, PostgreSQL, bot)

### Quick Diagnostics
```bash
# Run full diagnostic
cd ~/trading
bash diagnose.sh  # If available

# Or manual checks
echo "=== SYSTEM STATUS ==="
sudo systemctl status cron
sudo systemctl status postgresql
ps aux | grep telegram_bot_listener
echo "=== DATABASE CHECK ==="
psql -h localhost -U postgres -d trading_db -c "SELECT COUNT(*) FROM positions WHERE status = 'HOLD';"
echo "=== RECENT ERRORS ==="
grep -i "error" logs/*.log | tail -20
```

---

## Key Files

### Logs
- `logs/*.log`: All system logs
- `/var/log/syslog`: System cron logs

### Database
- `trading_db`: PostgreSQL database

### Scripts
- All Python scripts in `~/trading/`
- Shell scripts: `run_*.sh`

---

**End of Documentation**

Return to: [README.md](../README.md) | [00-QUICKSTART.md](00-QUICKSTART.md)
