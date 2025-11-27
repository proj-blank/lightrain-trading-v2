# LightRain Trading System - SWING Strategy

**Last Updated**: 2025-11-27  
**Purpose**: Complete guide to multi-day SWING strategy - entry, smart stops, position management, profit-locking extension

---

## Table of Contents
1. [Strategy Overview](#strategy-overview)
2. [Entry Conditions](#entry-conditions)
3. [Position Sizing](#position-sizing)
4. [Smart Stop System](#smart-stop-system)
5. [**NEW: Profit-Locking Extension**](#profit-locking-extension) ⭐
6. [TP Calculation](#tp-calculation)
7. [Monitoring Process](#monitoring-process)
8. [Exit Conditions](#exit-conditions)
9. [Real Trade Walkthrough](#real-trade-walkthrough)

---

## 1. Strategy Overview

### Objective
**Capture 7-12% profit over 3-15 days with smart trailing stops and profit-locking extension**

### Key Parameters

| Parameter | Value | Reasoning |
|-----------|-------|-----------|
| **Capital Pool** | ₹10,00,000 | Separate from DAILY (₹13L) |
| **Hold Period** | 3-15 days | Multi-day momentum + extended hold for winners |
| **Profit-Lock Start** | Day 8 | Lock profit floor if profitable |
| **Target Profit** | 7-12% | Realistic swing move |
| **Initial Stop Loss** | 4-5% | Room for volatility |
| **Trailing Stop** | Chandelier (2.5x ATR) | Dynamic protection |
| **Profit-Lock Trail** | 2% below current | Once profit-lock activated |
| **Position Sizing** | 60/20/20 allocation | Risk-balanced |
| **Max Position %** | 14% per stock | Slightly smaller than DAILY |
| **Min Score** | 65/100 | Higher selectivity |
| **Min RS Rating** | 65/99 | Top 35% stocks |
| **AI Validation** | Optional (recommended) | Claude analysis |
| **Monitoring** | Every 5 minutes | Same as DAILY |

### 🆕 Profit-Locking Extension (NEW)

**What It Does:**
- At day 8+, if position is profitable → Activate profit-lock mode
- Lock minimum profit floor (never goes down)
- Extend MAX_HOLD from 10 days to 15 days
- Dynamic trailing: SL trails up but never below locked floor
- Dynamic TP: Always 1% above current price (keeps moving up)

**Benefits:**
- ✅ Protects profits from reversals
- ✅ Lets winners run beyond day 10
- ✅ Removes artificial cap on profitable positions
- ✅ Reduces giving back gains

---

[... rest of sections 2-4 remain the same ...]

---

## 5. Profit-Locking Extension ⭐ NEW

### Overview

Starting from **day 8**, if a position is profitable, the system automatically:
1. 🔒 **Locks a minimum profit floor** (guaranteed profit even if price drops)
2. 📈 **Trails stop-loss upward** (never below locked floor)
3. 🎯 **Adjusts TP dynamically** (1% above current price)
4. ⏰ **Extends hold to 15 days** (from original 10)

### Why This Matters

**Problem It Solves:**
```
Without Profit-Lock:
  Day 8: +5% profit
  Day 9: +8% profit  
  Day 10: Force exit at +6% (arbitrary MAX_HOLD)
  → Missed potential to reach +12%

  OR:
  
  Day 8: +5% profit
  Day 9: Reversal to +1%
  Day 10: Exit at +1%
  → Gave back +4% gains
```

**With Profit-Lock:**
```
  Day 8: +5% profit → Lock +3% floor, extend to day 15
  Day 9: +8% profit → Stop trails to +6%
  Day 10: +10% profit → Still holding, stop at +8%
  Day 11: Reversal to +7% → Exit at +8% (stop hit)
  
  Result: Locked +8% vs +1% without profit-lock ✅
```

### Activation Logic

**Conditions (ALL must be true):**
1. ✅ Position held >= 8 days
2. ✅ Current P&L > 0 (any profit)
3. ✅ Profit-lock not already active

**Triggered On:**
- First monitor run on day 8 where position is profitable
- System sends Telegram alert: "🔒 PROFIT-LOCK ACTIVATED"

### Locked Floor Calculation

**Profit Tiers:**

| Current Profit | Locked Floor | Description |
|----------------|--------------|-------------|
| +5% or more | +3% | Lock +3% minimum |
| +3% to +5% | +2% | Lock +2% minimum |
| +1% to +3% | +1% | Lock +1% minimum |

**Example:**
```python
Entry: ₹6,250
Day 8 Current: ₹6,550 (+4.8% profit)

Locked Floor: +3% (because profit >= +3%)
Locked Price: ₹6,250 * 1.03 = ₹6,437.50

→ Worst case exit now: ₹6,437.50 (+3% guaranteed)
```

### Dynamic Trailing Logic

**Stop-Loss Formula:**
```python
trailing_sl = current_price * 0.98  # 2% below current
locked_floor = entry_price * (1 + locked_pct / 100)

new_sl = max(locked_floor, trailing_sl)
```

**Example Walkthrough:**

```
Entry: ₹6,250

Day 8 (Profit-Lock Activates):
  Current: ₹6,550 (+4.8%)
  Locked Floor: ₹6,437 (+3%)
  Trailing SL: ₹6,550 * 0.98 = ₹6,419
  Final SL: max(₹6,437, ₹6,419) = ₹6,437 ✅ (locked floor wins)

Day 9 (Price rises):
  Current: ₹6,750 (+8%)
  Locked Floor: ₹6,437 (+3%) [unchanged]
  Trailing SL: ₹6,750 * 0.98 = ₹6,615
  Final SL: max(₹6,437, ₹6,615) = ₹6,615 ✅ (trailing wins, moved up)

Day 10 (Price consolidates):
  Current: ₹6,720 (-0.4%)
  Locked Floor: ₹6,437 [unchanged]
  Trailing SL: ₹6,720 * 0.98 = ₹6,585
  Final SL: ₹6,585 ✅ (still above floor)

Day 11 (Reversal):
  Current: ₹6,600 (-1.8%)
  Trailing SL: ₹6,600 * 0.98 = ₹6,468
  Final SL: ₹6,468 ✅ (still above floor, but moving down)

Day 12 (Further drop):
  Current: ₹6,450 (-2.3% more)
  Trailing SL: ₹6,450 * 0.98 = ₹6,321
  Final SL: max(₹6,437, ₹6,321) = ₹6,437 ✅ (locked floor protects!)
  
  → Stop will NOT go below ₹6,437 even if price crashes
```

### Dynamic Take-Profit

**Formula:**
```python
new_tp = current_price * 1.01  # Always 1% above current
```

**Why 1%?**
- Keeps moving target as price rises
- Not too far (allows natural exits)
- Encourages letting winners run

**Example:**
```
Day 8: Current ₹6,550 → TP = ₹6,615 (+1%)
Day 9: Current ₹6,750 → TP = ₹6,817 (+1%)
Day 10: Current ₹6,720 → TP = ₹6,787 (+1%)

If price spikes to TP, exit immediately and lock profit
```

### Extended Max Hold

**Original Behavior:**
- All positions force-exit at day 10 (regardless of profit)

**New Behavior:**
- If profit-lock activated → Extend to **15 days**
- If profit-lock NOT activated (unprofitable) → Still exit at day 10

**Logic:**
```python
if profit_lock_active:
    max_hold = 15
else:
    max_hold = 10

if days_held >= max_hold:
    force_exit()
```

### Telegram Alerts

**Activation Alert:**
```
🔒 PROFIT-LOCK ACTIVATED

Ticker: TITAN.NS (SWING)
Days Held: 8/15

Current P&L: +4.8%

✅ Locked Minimum: +3% (₹6,437.50)
📈 New TP: ₹6,615.00
🛡️ New SL: ₹6,437.50
⏰ Extended Hold: 15 days

Position will trail upwards while protecting profit floor
```

**Stop Update (if significant change):**
```
📊 SWING Stop Updated

Ticker: TITAN.NS (Day 9)
Current: ₹6,750 (+8%)

🛡️ SL moved: ₹6,437 → ₹6,615 (+2.8%)
📈 TP moved: ₹6,615 → ₹6,817 (+1%)

Profit-lock active - trailing upwards
```

**Exit with Profit-Lock Floor:**
```
🛡️ SWING SL Hit (Profit-lock floor)

Ticker: TITAN.NS
Entry: ₹6,250.00
Exit: ₹6,440.00
P&L: +₹1,520 (+3.04%)

Days Held: 12
Qty: 8

Profit-lock floor protected +3%
```

### Database Schema

**Positions Table Additions:**
```sql
-- No new columns needed!
-- Uses existing columns:
--   - stop_loss (dynamically updated)
--   - take_profit (dynamically updated)
--   - unrealized_pnl (for tier calculation)
--   - entry_date (for days_held calculation)
```

**Tracking:**
- Profit-lock activation logged in notes
- Stop updates logged every significant change
- Exit reason includes "Profit-lock floor" if applicable

---

[... sections 6-9 continue with original content, with monitoring section updated ...]

---

## 7. Monitoring Process (UPDATED)

### Script: monitor_swing_pg.py
### Frequency: Every 5 minutes (9:00 AM - 3:30 PM)

### What It Does

**Step 1: Load Active Positions**
```python
positions = db.execute("""
    SELECT ticker, entry_price, entry_date, quantity, stop_loss, take_profit,
           unrealized_pnl, current_price
    FROM positions
    WHERE status = 'HOLD' AND strategy = 'SWING'
""")
```

**Step 2: Check Profit-Lock Activation (NEW)**
```python
for position in positions:
    days_held = (today - entry_date).days
    
    # Check if profit-lock should activate
    if days_held >= 8 and unrealized_pnl > 0:
        # Calculate locked floor
        pnl_pct = (unrealized_pnl / (entry_price * quantity)) * 100
        
        if pnl_pct >= 5.0:
            locked_floor_pct = 3.0
        elif pnl_pct >= 3.0:
            locked_floor_pct = 2.0
        else:
            locked_floor_pct = 1.0
        
        locked_floor_price = entry_price * (1 + locked_floor_pct / 100)
        
        # Apply profit-lock logic
        new_sl, new_tp = apply_profit_lock(current_price, locked_floor_price)
        
        # Update database
        update_position_stops(ticker, new_sl, new_tp)
        
        # Send alert (first time only)
        if days_held == 8:
            send_telegram_message("🔒 PROFIT-LOCK ACTIVATED...")
```

**Step 3: Update Stops Dynamically**
```python
# If already in profit-lock mode
if profit_lock_active and days_held > 8:
    new_sl = max(locked_floor, current_price * 0.98)
    new_tp = current_price * 1.01
    
    # Update if >0.5% change
    if abs(new_sl - old_sl) / old_sl > 0.005:
        update_position_stops(ticker, new_sl, new_tp)
```

**Step 4: Check Exit Conditions**
```python
# TP hit
if current_price >= take_profit:
    exit_position(ticker, 'TP')

# SL hit (could be profit-lock floor)
elif current_price <= stop_loss:
    exit_position(ticker, 'SL')

# Time exit (15 days if profit-lock, else 10)
elif days_held >= max_hold:
    exit_position(ticker, 'MAX-HOLD')
```

---

## Summary: SWING Strategy Success Factors

### What Makes It Work
1. ✅ **Higher selectivity** (score >= 65, RS >= 65)
2. ✅ **AI validation** (optional but powerful)
3. ✅ **Smart multi-layer stops** (Chandelier protects profits)
4. ✅ **🆕 Profit-locking extension** (locks gains, extends winners)
5. ✅ **Room to run** (7-12% targets over 3-15 days)
6. ✅ **Entry filters** (RSI < 70, pullback check)
7. ✅ **Automatic profit protection** (trailing stops + locked floors)

### NEW Feature Benefits

**Profit-Locking Extension:**
- 🔒 Guarantees minimum profit on day 8+ winners
- 📈 Removes 10-day cap on profitable positions
- 🎯 Dynamic targets that move with price
- 🛡️ Protects against giving back gains
- ⏰ Lets momentum plays fully develop (15 days)

**When It Helps Most:**
- Strong trends that extend beyond day 10
- Volatile stocks (locks profit before reversals)
- Momentum plays with 10-15% potential
- Reduces regret of exiting winners too early

---

**Last Updated**: 2025-11-27  
**Version**: 3.0 (Added Profit-Locking Extension)

**What's New:**
- 🆕 Profit-locking extension at day 8+
- 🆕 Extended MAX_HOLD to 15 days for profitable positions
- 🆕 Dynamic trailing stops with locked floor
- 🆕 Dynamic TP (1% above current)

**Next Steps**: 
- Review **00-QUICKSTART.md** for quick commands
- See **02-DATABASE-SCHEMA.md** for data queries
- Check **04-DAILY-STRATEGY.md** for comparison

**Happy Trading! 📈**
