# 06 - Position Management

Complete guide to position entry, exits, take-profits, stop-losses, and circuit breakers.

---

## Table of Contents
1. [Position Entry](#position-entry)
2. [Stop Loss Logic](#stop-loss-logic)
3. [Take Profit System](#take-profit-system)
4. [Exit Conditions](#exit-conditions)
5. [Circuit Breakers](#circuit-breakers)
6. [Position Holds](#position-holds)

---

## Position Entry

### Entry Workflow
1. **Screening Phase**: Stocks pass technical + fundamental filters
2. **Signal Generation**: BUY signal with score >= threshold
3. **Portfolio Allocation**: Smart allocation by category
4. **Position Sizing**: Volatility-adjusted (ATR-based)
5. **Order Execution**: Market order at 9:15 AM IST

### Position Sizing Formula
```
Position Size = (Kelly Fraction) × (Category Allocation / Max Positions) × (Volatility Adjustment)

Where:
- Kelly Fraction = 5% (from backtesting)
- Category Allocation:
  * Large-cap: ₹300,000 (6 positions max)
  * Mid-cap: ₹100,000 (5 positions max)
  * Microcap: ₹100,000 (8 positions max)
- Volatility Adjustment = 1 / (ATR_ratio × vol_factor)
```

### Entry Example
```python
# Large-cap stock with ATR = 50, avg_atr = 45
base_size = 300000 / 6 = 50,000
atr_ratio = 50 / 45 = 1.11
vol_adjustment = 1 / (1.11 × 0.8) = 1.13
position_value = 50,000 × 1.13 × 0.05 × 20 = ₹56,500
```

---

## Stop Loss Logic

### Dynamic Stop Loss
- **Initial SL**: Entry price × 0.95 (5% below entry)
- **Trailing SL**: Moves up as price increases
- **Never moves down**: Protects profits

### Trailing Logic
```python
if current_price > entry_price × 1.05:  # 5% profit
    new_sl = max(current_sl, current_price × 0.98)  # Trail at 2%
```

### Stop Loss Triggers
1. **5% Hard Stop**: Immediate exit if price drops 5% from entry
2. **Trailing Stop Hit**: Price drops below trailing SL
3. **Circuit Breaker**: 5% intraday drop triggers hold + review

---

## Take Profit System

### Multi-Level TP Strategy

#### Level 1: First TP (30% of position)
- **Trigger**: +10% from entry
- **Action**: Sell 30% of shares
- **SL Update**: Move to breakeven (entry price)

#### Level 2: Second TP (40% of position)
- **Trigger**: +20% from entry
- **Action**: Sell 40% of remaining shares
- **SL Update**: Move to +10% (lock in 10% profit)

#### Level 3: Final TP (30% of position)
- **Trigger**: +30% from entry
- **Action**: Sell remaining 30%
- **SL Update**: Trail at +15%

### Fractional TP Example
```
Entry: 100 shares @ ₹500
TP1 (+10%): Sell 30 shares @ ₹550 → 70 shares remain
TP2 (+20%): Sell 28 shares @ ₹600 → 42 shares remain
TP3 (+30%): Sell 42 shares @ ₹650 → Position closed
```

---

## Exit Conditions

### Automatic Exits
1. **Stop Loss Hit**: Price drops below SL
2. **Take Profit**: Any TP level reached
3. **SELL Signal**: Technical indicators turn bearish
4. **MAX-HOLD Exit**: Time-based forced exits to free capital
   - Daily: 3 calendar days (warning at 2 PM on day 2, exit at 9 AM on day 3)
   - Swing: 10 calendar days (warning at 2 PM on day 9, exit at 9 AM on day 10)
5. **Time-based (DAILY only)**: Exit at 3:15 PM if SELL signal

### Manual Exits (Telegram)
- `/exit TICKER`: Force exit immediately
- `/hold TICKER`: Suppress alerts, wait for hard stop

### Exit Priority
```
1. Circuit Breaker (5% drop) → HOLD + Alert
2. Hard Stop Loss (-5%) → EXIT
3. Take Profit levels → PARTIAL EXIT
4. SELL Signal → EXIT (if not on hold)
5. Time limit → EXIT (swing only)
```

---

## Circuit Breakers

### Purpose
Prevent panic selling during temporary volatility. Give position time to recover.

### Trigger Conditions
- **Intraday drop ≥ 5%** from day's high
- Position not already on hold
- No previous circuit breaker today

### Circuit Breaker Actions
1. **Alert Sent**: Telegram notification with reason analysis
2. **Position Held**: Suppress exit signals for today
3. **Hard Stop Active**: 5% SL from entry still enforced
4. **Review Tomorrow**: Circuit breaker resets overnight

### Alert Format
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

### Drop Reason Analysis
```python
def analyze_drop_reason(drop_pct):
    if drop_pct < -8:
        return Severe market-wide correction
    elif drop_pct < -6:
        return High volatility drop
    elif drop_pct < -5:
        return Moderate intraday volatility
```

---

## Position Holds

### Hold System
Positions can be put on hold to suppress exit signals temporarily.

### Hold Sources
1. **Circuit Breaker**: Automatic hold after 5% drop
2. **Manual Hold**: `/hold TICKER` command
3. **Strategy Override**: Temporary market conditions

### Hold Behavior
- **Alerts Suppressed**: No exit signals for today
- **Hard Stop Active**: 5% loss limit still enforced
- **Auto Reset**: Hold expires at market close
- **Manual Override**: `/exit TICKER` forces exit

### Database Tracking
```sql
CREATE TABLE circuit_breaker_holds (
    ticker VARCHAR(20),
    strategy VARCHAR(20),
    hold_date DATE,
    reason TEXT
);
```

---

## MAX-HOLD Warning System

### Purpose
Prevent capital from being locked in "dead meat" positions. Force exits after holding period to free capital for new opportunities.

### Hold Limits
- **DAILY Strategy**: 3 calendar days maximum
- **SWING Strategy**: 10 calendar days maximum

### Warning Timeline

#### Day Before Exit (2:00 PM IST)
At 2:00 PM on the day before forced exit, you receive a comprehensive alert:

**Alert Contents:**
1. **Position Details**: Ticker, strategy, entry price, quantity
2. **Performance**: Current P&L and percentage return
3. **Technical Analysis**: Current price, SMA(20), RSI
4. **AI Analysis**:
   - Recommendation (HOLD/EXIT)
   - Confidence level
   - Reasoning based on news + technicals
   - Recent news headlines (up to 3)

**Your Options:**
- **Manual Exit Today**: Exit before 3:30 PM market close
- **Let Auto-Exit**: Do nothing, position exits tomorrow at 9:00 AM

#### Exit Day (9:00 AM IST)
If you didn't exit manually, the position automatically exits at market open:
- Exit price: Market price at 9:00 AM
- Capital freed: Original investment + P&L returned to available capital
- New opportunities: Capital available for fresh entries

### Alert Example
```
🔔 MAX-HOLD WARNING + AI ANALYSIS

📊 Ticker: RELIANCE (DAILY)
📅 Held: 2 days (max: 3)
💰 Current P&L: 🟢 ₹4,200 (+2.80%)

Entry: ₹500.00 | Current: ₹514.00
Quantity: 300

━━━ TECHNICAL ━━━
Current: ₹514.00 | SMA(20): ₹508.50 | RSI: 58.5 | P&L: +2.80%

━━━ AI ANALYSIS ━━━
Recommendation: HOLD FOR RECOVERY
Confidence: MEDIUM
Reasoning: Recent correction on weak volume. Support at ₹510.
Positive sector sentiment with upcoming results.

📰 Recent News (2 articles):
  1. Reliance announces Q4 earnings date
  2. Oil prices stable, benefiting refining margins

━━━━━━━━━━━━━━━━━━━

⏰ Will auto-exit tomorrow at 9:00 AM

Options:
• Exit manually today before 3:30 PM close
• Let auto-exit handle tomorrow morning
• Type /exitall to exit all positions now

You have 30 minutes to decide before market close
```

### Database Tracking
MAX-HOLD exits are logged in `trades` table with:
- `exit_reason`: "MAX-HOLD"
- `days_held`: Actual calendar days held
- P&L and percentage return recorded

### Configuration
Located in strategy scripts:
- `daily_trading_pg.py`: `MAX_HOLD_DAYS = 3`
- `swing_trading_pg.py`: `MAX_HOLD_DAYS = 10`

### Key Script
- `check_max_hold_warnings.py`: Runs at 2:00 PM IST daily
- Checks positions at warning threshold (day 2 for DAILY, day 9 for SWING)
- Fetches AI analysis with news for each position
- Sends Telegram alert with comprehensive details

---

## Best Practices

### Entry
- ✅ Enter at market open (9:15 AM)
- ✅ Verify sufficient cash before entry
- ✅ Respect category allocation limits
- ❌ Never enter after 10:00 AM

### Exit
- ✅ Honor stop losses immediately
- ✅ Take partial profits at TP levels
- ✅ Let winners run (trailing SL)
- ❌ Never override circuit breakers manually

### Monitoring
- ✅ Check positions every 5 minutes (automated)
- ✅ Review circuit breaker alerts promptly
- ✅ Update SL as price increases
- ❌ Don't panic sell on small drops

---

## Common Scenarios

### Scenario 1: Quick Profit
```
Entry: ₹1,000
Day 1: ₹1,100 (+10%) → TP1 hit, sell 30%, SL → ₹1,000
Day 2: ₹1,200 (+20%) → TP2 hit, sell 40%, SL → ₹1,100
Day 3: ₹1,300 (+30%) → TP3 hit, close position
```

### Scenario 2: Stop Loss Hit
```
Entry: ₹1,000
Day 1: ₹980 (-2%) → Hold
Day 2: ₹950 (-5%) → SL hit, exit at ₹950
Loss: -5%
```

### Scenario 3: Circuit Breaker
```
Entry: ₹1,000
Day 1: ₹970 (-3%) → Monitor
Day 1 (later): ₹945 (-5.5% from high) → Circuit breaker triggered
Day 1 (close): ₹960 → Position held
Day 2: ₹1,020 (+2%) → Resume normal monitoring
```

---

## Key Files

### Position Management
- `monitor_swing_pg.py`: Swing position monitoring
- `monitor_daily.py`: Daily position monitoring
- `monitor_positions.py`: Legacy monitor

### Risk Management
- `scripts/risk_manager.py`: Circuit breakers, SL/TP logic
- `scripts/db_connection.py`: Position CRUD operations

### Configuration
- Stop loss: 5% (hardcoded)
- Take profit: 10%, 20%, 30% (configurable)
- Circuit breaker: 5% intraday drop
- Max hold: 20 days (swing), 1 day (daily)

---

**Next**: [07-CAPITAL-TRACKER.md](07-CAPITAL-TRACKER.md) - Capital flows and profit tracking
