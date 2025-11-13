# LightRain Trading System - DAILY Strategy

**Last Updated**: 2024-11-13  
**Purpose**: Complete guide to intraday DAILY strategy - entry, exits, position management

---

## Table of Contents
1. [Strategy Overview](#strategy-overview)
2. [Entry Conditions](#entry-conditions)
3. [Position Sizing](#position-sizing)
4. [TP/SL Calculation](#tpsl-calculation)
5. [Monitoring Process](#monitoring-process)
6. [Exit Conditions](#exit-conditions)
7. [Circuit Breakers](#circuit-breakers)
8. [Real Trade Walkthrough](#real-trade-walkthrough)

---

## 1. Strategy Overview

### Objective
**Capture 5-7% profit within a single trading day**

### Key Parameters

| Parameter | Value | Reasoning |
|-----------|-------|-----------|
| **Capital Pool** | ₹13,00,000 | Separate from SWING (₹10L) |
| **Hold Period** | 1 day (force exit 3:25 PM) | No overnight risk |
| **Target Profit** | 5-7% | Realistic intraday move |
| **Stop Loss** | 3-4% | Tight control on losses |
| **Position Sizing** | 60/20/20 allocation | Risk-balanced |
| **Max Position %** | 20% per stock | No over-concentration |
| **Min Score** | 60/100 | Moderate selectivity |
| **Min RS Rating** | 60/99 | Top 40% stocks |
| **Monitoring** | Every 5 minutes | Real-time tracking |

### Time Schedule (IST)

```
8:30 AM  - stocks_screening.py (populate universe)
9:00 AM  - daily_screening.py (score stocks)
9:00 AM  - daily_trading_pg.py (execute entries)
9:05-3:30 - monitor_daily.py (check TP/SL every 5 min)
3:25 PM  - Force exit ALL positions
3:30 PM  - EOD summary
```

### Risk/Reward Profile

```
Best Case: +7% in 1 day
Target: +5% average
Expected: +3-4% (accounting for losses)
Worst Case: -4% (SL hit)
Circuit Breaker: -5% (hard stop)
```

---

## 2. Entry Conditions

### Pre-Entry Checklist

**1. Technical Filters** (see 03-SCREENING-SCORING.md):
- ✅ RS Rating >= 60
- ✅ Technical score >= 60
- ✅ Majority BUY signals (5+ out of 9 indicators)

**2. Capital Check**:
```python
available_capital = get_available_cash('DAILY')
required_investment = entry_price * quantity

if available_capital < required_investment:
    skip_entry()
```

**3. Position Limit Check**:
```python
# 60/20/20 allocation enforced
large_cap_allocation = 0.60 * total_capital  # ₹7.8L
mid_cap_allocation = 0.20 * total_capital    # ₹2.6L
micro_cap_allocation = 0.20 * total_capital  # ₹2.6L

# Check if category has room
if category == 'Large-cap':
    deployed_in_category = sum(positions in Large-cap)
    if deployed_in_category >= large_cap_allocation:
        skip_entry()
```

**4. Circuit Breaker Check**:
```python
# Check if stock is on hold from previous session
if is_position_on_hold(ticker, 'DAILY'):
    skip_entry()  # User manually blocked this stock
```

### Entry Logic (daily_trading_pg.py)

**Phase 1: Collect All Candidates**
```python
candidates_by_category = {
    'large_caps': [],
    'mid_caps': [],
    'micro_caps': []
}

for ticker in stock_universe:
    # RS filter
    rs_rating = calculate_rs_rating(ticker)
    if rs_rating < 60:
        continue
    
    # Technical analysis
    signal, score, details = generate_signal_daily(df, min_score=60)
    
    if signal == 'BUY' and score >= 60:
        candidates_by_category[category].append({
            'ticker': ticker,
            'score': score,
            'rs_rating': rs_rating,
            'details': details
        })
```

**Phase 2: Rank and Select**
```python
# Sort each category by score (highest first)
for category in candidates_by_category:
    candidates_by_category[category].sort(key=lambda x: x['score'], reverse=True)

# Select positions using 60/20/20 allocation
selected_positions = select_positions_for_entry(
    candidates_by_category,
    available_capital,
    allocation={'large_caps': 0.60, 'mid_caps': 0.20, 'micro_caps': 0.20}
)
```

**Phase 3: Execute Entries**
```python
for position in selected_positions:
    ticker = position['ticker']
    category = position['category']
    entry_price = position['entry_price']
    quantity = position['quantity']
    
    # Calculate TP/SL
    stop_loss = entry_price * 0.96     # -4% SL
    take_profit = entry_price * 1.05    # +5% TP
    
    # Execute entry
    position_id = add_position(
        ticker=ticker,
        strategy='DAILY',
        entry_price=entry_price,
        quantity=quantity,
        stop_loss=stop_loss,
        take_profit=take_profit,
        category=category
    )
    
    # Debit capital
    investment = entry_price * quantity
    debit_capital('DAILY', investment)
    
    # Log trade
    log_trade(ticker, 'DAILY', 'BUY', entry_price, quantity)
    
    # Send Telegram alert
    send_trade_alert(ticker, 'BUY', entry_price, quantity, 'DAILY')
```

### Entry Telegram Alert Example

```
🟢 DAILY Entry
━━━━━━━━━━━━━━━
Ticker: RELIANCE.NS
Category: Large-cap
Entry: ₹2,450.00
Quantity: 20 shares
Investment: ₹49,000

Targets:
  TP: ₹2,573 (+5.0%)
  SL: ₹2,352 (-4.0%)

Score: 72/100
RS Rating: 75/99

Strategy: DAILY
Time: 9:15 AM
━━━━━━━━━━━━━━━
```

---

## 3. Position Sizing

### 60/20/20 Allocation Model

**Purpose**: Balance risk across market cap categories

```python
def calculate_percentage_allocation(total_capital, allocation_pcts):
    """
    total_capital: ₹13,00,000
    allocation_pcts: {'large_caps': 0.60, 'mid_caps': 0.20, 'micro_caps': 0.20}
    """
    allocations = {}
    allocations['large_caps'] = total_capital * 0.60   # ₹7,80,000
    allocations['mid_caps'] = total_capital * 0.20     # ₹2,60,000
    allocations['micro_caps'] = total_capital * 0.20   # ₹2,60,000
    return allocations
```

### Position Sizing Logic

**Without ATR (Default)**:
```python
# Max 20% of category allocation per position
category_allocation = allocations[category]
max_per_position = category_allocation * 0.20

# Example: Large-cap
# Category: ₹7,80,000
# Max per position: ₹1,56,000

quantity = int(max_per_position / entry_price)
actual_investment = quantity * entry_price
```

**With ATR Sizing** (if enabled):
```python
# Risk-based sizing using ATR
atr = calculate_atr(df)
risk_per_share = atr * 2  # 2x ATR stop

# Risk 1% of capital per trade
risk_amount = total_capital * 0.01  # ₹13,000

quantity = int(risk_amount / risk_per_share)
actual_investment = quantity * entry_price
```

### Example Calculations

**Scenario 1: Large-cap stock**
```
Category: Large-cap
Allocation: ₹7,80,000
Max per position: 20% = ₹1,56,000

Stock: RELIANCE.NS @ ₹2,450
Quantity: ₹1,56,000 / ₹2,450 = 63 shares
Actual: 63 * ₹2,450 = ₹1,54,350

Remaining large-cap: ₹7,80,000 - ₹1,54,350 = ₹6,25,650
```

**Scenario 2: Microcap stock**
```
Category: Microcap
Allocation: ₹2,60,000
Max per position: 20% = ₹52,000

Stock: DIGISPICE.NS @ ₹145
Quantity: ₹52,000 / ₹145 = 358 shares
Actual: 358 * ₹145 = ₹51,910

Remaining microcap: ₹2,60,000 - ₹51,910 = ₹2,08,090
```

---

## 4. TP/SL Calculation

### Stop Loss (SL)

**Formula**:
```python
stop_loss = entry_price * 0.96  # -4% from entry
```

**Alternative (ATR-based)**:
```python
atr = calculate_atr(df, period=14)
stop_loss = entry_price - (atr * 2)  # 2x ATR below entry
```

**Example**:
```
Entry: ₹2,450
SL: ₹2,450 * 0.96 = ₹2,352
Risk: -₹98 per share (-4%)

Quantity: 20 shares
Max Loss: 20 * ₹98 = ₹1,960
```

### Take Profit (TP)

**Formula**:
```python
# Range: +5% to +7%
# Default: +5%
take_profit = entry_price * 1.05  # +5% from entry

# Aggressive (if score > 80):
take_profit = entry_price * 1.07  # +7% from entry
```

**Example**:
```
Entry: ₹2,450
TP: ₹2,450 * 1.05 = ₹2,573 (+5%)

Quantity: 20 shares
Profit at TP: 20 * ₹123 = ₹2,460
```

### Risk/Reward Ratio

```
Entry: ₹2,450
SL: ₹2,352 (risk: ₹98 per share)
TP: ₹2,573 (reward: ₹123 per share)

Risk/Reward: 98 / 123 = 1:1.25

Position: 20 shares
Max Risk: ₹1,960
Max Reward: ₹2,460
```

**Why 1:1.25 ratio acceptable?**
- High win rate (targeting 60-65%)
- Tight intraday management
- Force exit prevents runaway losses

---

## 5. Monitoring Process

### Script: monitor_daily.py
### Frequency: Every 5 minutes (9:00 AM - 3:30 PM)

### What It Does

**Step 1: Load Active Positions**
```python
positions = db.execute("""
    SELECT ticker, entry_price, quantity, stop_loss, take_profit
    FROM positions
    WHERE status = 'HOLD' AND strategy = 'DAILY'
""")
```

**Step 2: Fetch Current Prices**
```python
for position in positions:
    ticker = position['ticker']
    
    # Get latest price from yfinance
    stock = yf.Ticker(ticker)
    hist = stock.history(period='1d')
    current_price = hist['Close'].iloc[-1]
```

**Step 3: Update Database**
```python
# Calculate unrealized P&L
unrealized_pnl = (current_price - entry_price) * quantity

# Update position
db.execute("""
    UPDATE positions
    SET current_price = %s,
        unrealized_pnl = %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE ticker = %s AND strategy = 'DAILY' AND status = 'HOLD'
""", (current_price, unrealized_pnl, ticker))
```

**Step 4: Check Exit Conditions**
```python
# Check TP hit
if current_price >= take_profit:
    exit_position(ticker, 'TP')

# Check SL hit
elif current_price <= stop_loss:
    exit_position(ticker, 'SL')

# Check time-based exit (3:25 PM)
elif current_time >= '15:25':
    exit_position(ticker, 'TIME')
```

### Monitor Log Example

```
[2024-11-13 10:15:22] Monitoring 5 DAILY positions...
[2024-11-13 10:15:23]   RELIANCE.NS: ₹2,480 | P&L: ₹600 (+1.22%) | TP: 3.75% away | SL: 5.16% away
[2024-11-13 10:15:24]   TCS.NS: ₹3,550 | P&L: -₹300 (-0.84%) | TP: 5.84% away | SL: 3.24% away
[2024-11-13 10:15:25]   INFY.NS: ₹1,460 | P&L: ₹200 (+1.37%) | TP: 3.63% away | SL: 5.48% away
[2024-11-13 10:15:26]   ✅ SBIN.NS HIT TP @ ₹625 | P&L: ₹3,000 (+5.04%)
[2024-11-13 10:15:27]   TATASTEEL.NS: ₹145 | P&L: -₹100 (-0.69%) | TP: 5.69% away | SL: 3.45% away
[2024-11-13 10:15:28] ✅ Exited 1 position(s)
```

---

## 6. Exit Conditions

### Exit Type 1: TP Hit (Target Achieved)

**Condition**: `current_price >= take_profit`

**Example**:
```
Entry: ₹2,450 @ 9:15 AM
TP: ₹2,573 (+5%)
Current: ₹2,575 @ 11:30 AM

✅ TP HIT - EXIT POSITION
```

**Exit Logic**:
```python
def exit_position_tp(ticker, current_price):
    position = get_position(ticker, 'DAILY')
    entry_price = position['entry_price']
    quantity = position['quantity']
    
    # Calculate P&L
    pnl = (current_price - entry_price) * quantity
    pnl_pct = ((current_price - entry_price) / entry_price) * 100
    
    # Close position in database
    close_position(ticker, 'DAILY', current_price, pnl)
    
    # Credit back investment
    original_investment = entry_price * quantity
    credit_capital('DAILY', original_investment)
    
    # Lock profit
    update_capital('DAILY', pnl)  # Adds to total_profits_locked
    
    # Log trade
    log_trade(ticker, 'DAILY', 'SELL', current_price, quantity, pnl,
              notes=f"TP Hit @ ₹{position['take_profit']:.2f}")
    
    # Telegram alert
    send_telegram_message(f"""
    🎯 DAILY TP Hit!
    
    Ticker: {ticker}
    Entry: ₹{entry_price:.2f}
    Exit: ₹{current_price:.2f}
    P&L: ₹{pnl:,.0f} ({pnl_pct:+.2f}%)
    Qty: {quantity}
    Time: {current_time}
    """)
```

**Telegram Alert**:
```
🎯 DAILY TP Hit!

Ticker: RELIANCE.NS
Entry: ₹2,450.00
Exit: ₹2,575.00
P&L: ₹2,500 (+5.10%)
Qty: 20
Time: 11:30 AM
```

---

### Exit Type 2: SL Hit (Stop Loss Triggered)

**Condition**: `current_price <= stop_loss`

**Example**:
```
Entry: ₹2,450 @ 9:15 AM
SL: ₹2,352 (-4%)
Current: ₹2,348 @ 10:45 AM

⛔ SL HIT - EXIT POSITION
```

**Exit Logic**: (same as TP, but negative P&L)
```python
pnl = -₹2,040  # Loss
update_capital('DAILY', pnl)  # Deducts from current_trading_capital
```

**Telegram Alert**:
```
🛑 DAILY SL Hit

Ticker: RELIANCE.NS
Entry: ₹2,450.00
Exit: ₹2,348.00
P&L: -₹2,040 (-4.16%)
Qty: 20
Time: 10:45 AM
Reason: Stop loss triggered
```

---

### Exit Type 3: Time-Based Exit (3:25 PM Force Close)

**Condition**: `current_time >= 15:25 IST`

**Why 3:25 PM?**
- Market closes at 3:30 PM
- Need 5 minutes to execute exits
- Avoid overnight risk (intraday strategy)

**Example**:
```
Entry: ₹2,450 @ 9:15 AM
Current @ 3:25 PM: ₹2,470 (+0.82%)
Neither TP nor SL hit

🕐 TIME EXIT - FORCE CLOSE
```

**Exit Logic**:
```python
# Check time
if datetime.now().time() >= time(15, 25):
    for position in active_daily_positions:
        current_price = fetch_price(position['ticker'])
        pnl = (current_price - position['entry_price']) * position['quantity']
        
        # Exit regardless of P&L
        close_position(position['ticker'], 'DAILY', current_price, pnl)
        credit_capital('DAILY', position['entry_price'] * position['quantity'])
        update_capital('DAILY', pnl)
        
        log_trade(..., notes="Time-based exit (3:25 PM)")
```

**Telegram Alert**:
```
🕐 DAILY Time Exit

Ticker: RELIANCE.NS
Entry: ₹2,450.00
Exit: ₹2,470.00
P&L: ₹400 (+0.82%)
Qty: 20
Time: 3:25 PM
Reason: End-of-day force close
```

**Why accept small profits/losses?**
- Intraday strategy = no overnight exposure
- Reset daily for fresh positions tomorrow
- Prevents gap-down risk next morning

---

## 7. Circuit Breakers

### 3% Alert Threshold

**Condition**: Position loses 3% or more

**Action**: Send Telegram alert, but DON'T exit

**Example**:
```
Entry: ₹2,450
Current: ₹2,376 (-3.02%)

⚠️ CIRCUIT BREAKER ALERT
```

**Alert Message**:
```
⚠️ CIRCUIT BREAKER ALERT

Ticker: RELIANCE.NS
Strategy: DAILY
Entry: ₹2,450.00
Current: ₹2,376.00
Loss: -₹1,480 (-3.02%)
SL: ₹2,352 (-4%)

Position is down 3%. Still above SL.
Monitor closely. Reply to override:
  /hold RELIANCE.NS - Keep position
  /exit RELIANCE.NS - Force exit now
```

**User Can Override**:
```python
# Via Telegram bot
if user_replies("/exit RELIANCE.NS"):
    # Force exit immediately
    exit_position(ticker, current_price, reason="User override")
    
elif user_replies("/hold RELIANCE.NS"):
    # Add to circuit_breaker_holds table
    # Suppress future alerts for this position
    add_circuit_breaker_hold(ticker, 'DAILY', 'HOLD', loss_pct=-3.02)
```

---

### 5% Hard Stop

**Condition**: Position loses 5% or more

**Action**: AUTOMATIC EXIT (cannot override)

**Example**:
```
Entry: ₹2,450
Current: ₹2,327 (-5.02%)

🚨 HARD STOP - AUTO EXIT
```

**Exit Logic**:
```python
if loss_pct <= -5.0:
    # Force exit immediately
    exit_position(ticker, current_price, reason="Hard stop (5% loss)")
    
    # Alert user
    send_telegram_message(f"""
    🚨 HARD STOP TRIGGERED
    
    Ticker: {ticker}
    Loss: {loss_pct:.2f}%
    
    Position automatically closed to prevent further loss.
    Circuit breaker activated at -5%.
    """)
```

**Telegram Alert**:
```
🚨 HARD STOP TRIGGERED

Ticker: RELIANCE.NS
Entry: ₹2,450.00
Exit: ₹2,327.00
Loss: -₹2,460 (-5.02%)
Qty: 20
Time: 11:15 AM

Position automatically closed.
Circuit breaker activated at -5%.
Review strategy for this stock.
```

**Why 5% hard stop?**
- Prevents runaway losses
- SL at -4% may not execute (gap down, illiquid stock)
- Hard stop is final safety net
- Protects capital pool

---

## 8. Real Trade Walkthrough

### Trade Example: RELIANCE.NS

**Date**: 2024-11-13  
**Strategy**: DAILY

---

#### 9:00 AM - Screening

```
Screening Process:
  Universe: 351 NSE stocks
  
  RELIANCE.NS Analysis:
  ✅ RS Rating: 72/99 (top 28%)
  ✅ Technical Score: 73/100
  
  Indicators:
    RSI: 42 (neutral-bullish)
    MACD: Bullish crossover ✅
    Bollinger: 0.35 position (buy zone)
    Volume: 1.6x average ✅
    Trend: 68 (uptrend)
  
  Signal: BUY
  Score: 73/100
```

---

#### 9:15 AM - Entry Execution

```python
Entry Details:
  Ticker: RELIANCE.NS
  Category: Large-cap
  Entry Price: ₹2,450.00
  Quantity: 20 shares
  Investment: ₹49,000
  
  Targets:
    Stop Loss: ₹2,352 (-4%)
    Take Profit: ₹2,573 (+5%)
  
  Capital Impact:
    Available before: ₹7,80,000
    Debited: ₹49,000
    Available after: ₹7,31,000
```

**Database**:
```sql
INSERT INTO positions (ticker, strategy, entry_price, quantity, stop_loss, take_profit, category)
VALUES ('RELIANCE.NS', 'DAILY', 2450.00, 20, 2352.00, 2573.00, 'Large-cap');

UPDATE capital_tracker
SET current_trading_capital = current_trading_capital - 49000
WHERE strategy = 'DAILY';

INSERT INTO trades (ticker, strategy, signal, price, quantity, notes)
VALUES ('RELIANCE.NS', 'DAILY', 'BUY', 2450.00, 20, 'Entry signal score: 73/100');
```

**Telegram Alert**: (sent via bot)
```
🟢 DAILY Entry
━━━━━━━━━━━━━━━
Ticker: RELIANCE.NS
Entry: ₹2,450.00
Qty: 20
Investment: ₹49,000

TP: ₹2,573 (+5%)
SL: ₹2,352 (-4%)

Score: 73/100
Time: 9:15 AM
━━━━━━━━━━━━━━━
```

---

#### 9:20-11:25 AM - Monitoring (Every 5 minutes)

```
9:20 AM: ₹2,455 (+0.20%) | P&L: +₹100 | TP: 4.8% away
9:25 AM: ₹2,462 (+0.49%) | P&L: +₹240 | TP: 4.5% away
9:30 AM: ₹2,458 (+0.33%) | P&L: +₹160 | TP: 4.7% away
...
10:45 AM: ₹2,490 (+1.63%) | P&L: +₹800 | TP: 3.3% away
11:00 AM: ₹2,520 (+2.86%) | P&L: +₹1,400 | TP: 2.1% away
11:25 AM: ₹2,550 (+4.08%) | P&L: +₹2,000 | TP: 0.9% away 🔥
```

**Database Updates** (every 5 min):
```sql
UPDATE positions
SET current_price = 2550.00,
    unrealized_pnl = 2000.00,
    updated_at = CURRENT_TIMESTAMP
WHERE ticker = 'RELIANCE.NS' AND strategy = 'DAILY' AND status = 'HOLD';
```

---

#### 11:30 AM - TP Hit! 🎯

```
Current Price: ₹2,575
Take Profit: ₹2,573
✅ TP HIT (exceeded by ₹2)
```

**Exit Execution**:
```python
Exit Details:
  Ticker: RELIANCE.NS
  Entry: ₹2,450.00
  Exit: ₹2,575.00
  Quantity: 20 shares
  
  P&L:
    Profit: ₹2,500
    ROI: +5.10%
    Hold Time: 2 hours 15 minutes
  
  Capital Impact:
    Investment returned: ₹49,000
    Profit locked: ₹2,500
    
    capital_tracker BEFORE:
      current_trading_capital: ₹7,31,000
      total_profits_locked: ₹0
    
    capital_tracker AFTER:
      current_trading_capital: ₹7,80,000 (investment returned)
      total_profits_locked: ₹2,500 (profit locked)
```

**Database**:
```sql
-- Close position
UPDATE positions
SET status = 'CLOSED',
    current_price = 2575.00,
    exit_date = CURRENT_DATE,
    realized_pnl = 2500.00,
    updated_at = CURRENT_TIMESTAMP
WHERE ticker = 'RELIANCE.NS' AND strategy = 'DAILY' AND status = 'HOLD';

-- Credit capital
UPDATE capital_tracker
SET current_trading_capital = current_trading_capital + 49000,  -- Return investment
    total_profits_locked = total_profits_locked + 2500,         -- Lock profit
    last_updated = CURRENT_TIMESTAMP
WHERE strategy = 'DAILY';

-- Log trade
INSERT INTO trades (ticker, strategy, signal, price, quantity, pnl, notes)
VALUES ('RELIANCE.NS', 'DAILY', 'SELL', 2575.00, 20, 2500.00, 'TP Hit @ ₹2,573');
```

**Telegram Alert**:
```
🎯 DAILY TP Hit!

Ticker: RELIANCE.NS
━━━━━━━━━━━━━━━
Entry: ₹2,450.00
Exit: ₹2,575.00
Profit: ₹2,500 (+5.10%)
━━━━━━━━━━━━━━━
Qty: 20 shares
Hold Time: 2h 15m
Time: 11:30 AM

✅ Profit locked in capital tracker
Available capital: ₹7,80,000
Total profits: ₹2,500
```

---

#### 3:30 PM - EOD Summary

```
DAILY Strategy Summary - 13 Nov 2024

Positions:
  Entries: 5
  Exits: 5
  
  TP Hits: 3 (60%)
  SL Hits: 1 (20%)
  Time Exits: 1 (20%)

P&L:
  Winning Trades: 3 → +₹7,200
  Losing Trades: 1 → -₹1,500
  Neutral Exits: 1 → +₹200
  
  Net P&L: +₹5,900
  ROI: 0.45% on ₹13L capital
  
Capital Status:
  Starting: ₹13,00,000
  Deployed today: ₹2,40,000 (peak)
  Locked profits: ₹5,900
  Current available: ₹13,00,000
  Total capital: ₹13,05,900
  
Best Trade: RELIANCE.NS (+₹2,500, +5.10%)
Worst Trade: TATASTEEL.NS (-₹1,500, -4.20%)
```

---

## Summary: DAILY Strategy Success Factors

### What Makes It Work
1. ✅ **High-probability entries** (score >= 60, RS >= 60)
2. ✅ **Tight risk control** (4% SL, 5% hard stop)
3. ✅ **Quick profits** (5-7% TP, captured intraday)
4. ✅ **No overnight risk** (all positions closed by 3:25 PM)
5. ✅ **Constant monitoring** (every 5 minutes)
6. ✅ **Profit protection** (locked profits never re-risked)

### Common Pitfalls to Avoid
1. ❌ Entering with score < 60
2. ❌ Ignoring RS rating filter
3. ❌ Not respecting SL
4. ❌ Holding past 3:25 PM
5. ❌ Over-allocating to one category
6. ❌ Overriding circuit breakers without reason

---

**Next**: See **05-SWING-STRATEGY.md** for multi-day trading strategy.

**Last Updated**: 2024-11-13  
**Version**: 2.0
