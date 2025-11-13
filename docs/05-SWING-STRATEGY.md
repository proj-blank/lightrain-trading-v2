# LightRain Trading System - SWING Strategy

**Last Updated**: 2024-11-13  
**Purpose**: Complete guide to multi-day SWING strategy - entry, smart stops, position management

---

## Table of Contents
1. [Strategy Overview](#strategy-overview)
2. [Entry Conditions](#entry-conditions)
3. [Position Sizing](#position-sizing)
4. [Smart Stop System](#smart-stop-system)
5. [TP Calculation](#tp-calculation)
6. [Monitoring Process](#monitoring-process)
7. [Exit Conditions](#exit-conditions)
8. [Real Trade Walkthrough](#real-trade-walkthrough)

---

## 1. Strategy Overview

### Objective
**Capture 7-12% profit over 3-10 days with smart trailing stops**

### Key Parameters

| Parameter | Value | Reasoning |
|-----------|-------|-----------|
| **Capital Pool** | ₹10,00,000 | Separate from DAILY (₹13L) |
| **Hold Period** | 3-10 days | Multi-day momentum |
| **Target Profit** | 7-12% | Realistic swing move |
| **Initial Stop Loss** | 4-5% | Room for volatility |
| **Trailing Stop** | Chandelier (2.5x ATR) | Dynamic protection |
| **Position Sizing** | 60/20/20 allocation | Risk-balanced |
| **Max Position %** | 14% per stock | Slightly smaller than DAILY |
| **Min Score** | 65/100 | Higher selectivity |
| **Min RS Rating** | 65/99 | Top 35% stocks |
| **AI Validation** | Optional (recommended) | Claude analysis |
| **Monitoring** | Every 5 minutes | Same as DAILY |

### Time Schedule (IST)

```
8:30 AM  - stocks_screening.py (populate universe)
9:25 AM  - swing_trading_pg.py (execute entries)
9:05-3:30 - monitor_swing_pg.py (check TP/SL/trailing every 5 min)
Day 10   - Force exit if still holding
3:30 PM  - EOD summary (daily)
```

### Risk/Reward Profile

```
Best Case: +12% in 3-7 days
Target: +7-10% average
Expected: +5-6% (accounting for losses)
Worst Case: -5% (SL hit)
Max Hold: 10 days (force exit)
```

### Key Differences from DAILY

| Aspect | DAILY | SWING |
|--------|-------|-------|
| **Hold Period** | 1 day | 3-10 days |
| **TP Target** | 5-7% | 7-12% |
| **Initial SL** | 3-4% | 4-5% |
| **Trailing Stop** | No | Yes (Chandelier) |
| **Min Score** | 60 | 65 |
| **AI Validation** | No | Yes (optional) |
| **Entry Filters** | None | RSI < 70, Pullback check |
| **Force Exit** | 3:25 PM daily | Day 10 |
| **Capital** | ₹13L | ₹10L |

---

## 2. Entry Conditions

### Pre-Entry Checklist

**1. Technical Filters**:
- ✅ RS Rating >= 65 (top 35%)
- ✅ Technical score >= 65
- ✅ Majority BUY signals (6+ out of 9 indicators)
- ✅ RSI < 70 (not overbought)
- ✅ Preferably 0.5-3% pullback from 5-day high

**2. Market Regime Check**:
```python
# Check Nifty trend
nifty = yf.download('^NSEI', period='1mo')
nifty_sma20 = nifty['Close'].rolling(20).mean()

if nifty_current < nifty_sma20:
    # Bearish market → reduce score by 10 points
    score -= 10
```

**3. Capital Check** (same as DAILY):
```python
available_capital = get_available_cash('SWING')
required_investment = entry_price * quantity

if available_capital < required_investment:
    skip_entry()
```

**4. AI Validation** (Optional but Recommended):
```python
# Send to Claude for analysis
ai_result = analyze_position_with_AI(
    ticker=ticker,
    current_price=current_price,
    weekly_data=weekly_df,
    strategy='SWING'
)

# AI response format:
{
    'ai_agrees': True,
    'ai_confidence': 0.85,
    'ai_reasoning': 'Strong weekly uptrend...',
    'suggested_target': 6750,
    'suggested_stop': 5950
}

# Store in database
add_position(..., 
    ai_agrees=ai_result['ai_agrees'],
    ai_confidence=ai_result['ai_confidence'],
    ai_reasoning=ai_result['ai_reasoning']
)
```

### Entry Filters (SWING-Specific)

**Filter 1: RSI Overbought**
```python
if current_rsi > 70:
    return "HOLD", 0, {
        "filter_rejection": "RSI Overbought",
        "rsi": round(current_rsi, 2),
        "message": f"RSI too high ({current_rsi:.1f}) - rejecting entry"
    }
```

**Why?** Multi-day holds need room to run. Entering at RSI 70+ risks immediate pullback.

**Filter 2: Pullback Check**
```python
high_5d = df['High'].tail(5).max()
pullback_pct = ((high_5d - current_price) / high_5d) * 100

# Penalties:
if pullback_pct < 0.5:
    score -= 15  # Too close to highs (0-15 points)
elif pullback_pct > 4.0:
    score -= 10  # Too far from highs (0-10 points)
# Sweet spot: 0.5-3% pullback = no penalty
```

**Why?** Better risk/reward on slight pullbacks. Avoid buying at all-time highs or deep corrections.

**Filter 3: Market Regime**
```python
if nifty_trend == "BEARISH":
    score -= 10  # More selective in downtrends
```

**Why?** Align with broader market. Harder to profit swimming against the tide.

### Entry Execution (swing_trading_pg.py)

**Phase 1: Collect Candidates**
```python
for ticker in stock_universe:
    # RS filter
    rs_rating = calculate_rs_rating(ticker)
    if rs_rating < 65:
        continue
    
    # Technical analysis (with SWING weights)
    signal, score, details = generate_signal_swing(df, min_score=65)
    
    # SWING-specific filters
    if signal == 'BUY' and score >= 65:
        if details['rsi'] > 70:
            continue  # RSI filter
        
        # Pullback check
        pullback_pct = calculate_pullback(df)
        if pullback_pct < 0.5:
            score -= 15
        
        candidates[category].append({
            'ticker': ticker,
            'score': score,
            'rs_rating': rs_rating
        })
```

**Phase 2: AI Validation** (if enabled)
```python
for candidate in top_candidates:
    ai_result = analyze_with_claude(candidate['ticker'])
    candidate['ai_agrees'] = ai_result['ai_agrees']
    candidate['ai_confidence'] = ai_result['ai_confidence']
    
    # Optional: Skip if AI strongly disagrees
    if ai_result['ai_agrees'] == False and ai_result['ai_confidence'] > 0.80:
        skip_candidate()
```

**Phase 3: Execute Entries**
```python
for position in selected_positions:
    # Calculate smart stops (multi-layered)
    stop_loss, take_profit = calculate_smart_stops(
        entry_price=entry_price,
        atr=atr,
        recent_low=recent_low,
        strategy='SWING'
    )
    
    # Execute entry
    add_position(..., ai_agrees, ai_confidence, ai_reasoning)
    debit_capital('SWING', investment)
    log_trade(...)
    send_telegram_alert(...)
```

### Entry Telegram Alert Example

```
🔷 SWING Entry
━━━━━━━━━━━━━━━
Ticker: COFORGE.NS
Category: Mid-cap
Entry: ₹6,250.00
Quantity: 8 shares
Investment: ₹50,000

Targets:
  TP: ₹6,750 (+8.0%)
  SL: ₹5,950 (-4.8%)

Score: 72/100
RS Rating: 82/99

AI Validation:
  ✅ Agrees: Yes
  🎯 Confidence: 88%
  💡 "Strong weekly uptrend. 
      Support at ₹6,000. 
      Target realistic."

Strategy: SWING
Max Hold: 10 days
Time: 9:30 AM
━━━━━━━━━━━━━━━
```

---

## 3. Position Sizing

### 60/20/20 Allocation (Same as DAILY)

```python
allocations = {
    'Large-cap': ₹10,00,000 * 0.60 = ₹6,00,000
    'Mid-cap': ₹10,00,000 * 0.20 = ₹2,00,000
    'Micro-cap': ₹10,00,000 * 0.20 = ₹2,00,000
}

# Max 14% per position (vs 20% for DAILY)
max_per_position = category_allocation * 0.14
```

**Why 14% vs 20%?**
- SWING holds longer (more volatility exposure)
- Smaller positions = less overnight risk
- More diversification across positions

### Example Calculations

**Large-cap Position**:
```
Category: Large-cap
Allocation: ₹6,00,000
Max per position: 14% = ₹84,000

Stock: RELIANCE.NS @ ₹2,450
Quantity: ₹84,000 / ₹2,450 = 34 shares
Actual: 34 * ₹2,450 = ₹83,300
```

**Mid-cap Position**:
```
Category: Mid-cap
Allocation: ₹2,00,000
Max per position: 14% = ₹28,000

Stock: COFORGE.NS @ ₹6,250
Quantity: ₹28,000 / ₹6,250 = 4 shares
Actual: 4 * ₹6,250 = ₹25,000
```

---

## 4. Smart Stop System

### Multi-Layered Stop Loss Architecture

SWING strategy uses **5-layer smart stops** that automatically adjust:

```
┌─────────────────────────────────────────┐
│      SWING SMART STOP SYSTEM            │
├─────────────────────────────────────────┤
│ Layer 1: Fixed % Stop (Capital Guard)  │
│   → Entry * 0.95 = -5% hard floor      │
├─────────────────────────────────────────┤
│ Layer 2: ATR-Based Stop (Volatility)   │
│   → Entry - (ATR * 2.0)                │
├─────────────────────────────────────────┤
│ Layer 3: Chandelier Stop (Trailing)    │
│   → Highest - (ATR * 2.5) ⭐ KEY       │
├─────────────────────────────────────────┤
│ Layer 4: Support-Based (Technical)     │
│   → Recent Low * 0.98 (-2% buffer)     │
├─────────────────────────────────────────┤
│ Layer 5: Time-Based (10 days max)      │
│   → Force exit if no progress          │
└─────────────────────────────────────────┘

Final Stop = MAX(all layers) ← Tightest stop wins
```

### Layer Details

**Layer 1: Fixed Percentage Stop**
```python
stop_fixed = entry_price * 0.95  # -5% from entry
```
- **Purpose**: Hard floor to prevent catastrophic loss
- **Never moves**: Fixed at entry
- **Example**: Entry ₹6,250 → Stop ₹5,937.50

**Layer 2: ATR-Based Stop**
```python
atr = calculate_atr(df, period=14)
stop_atr = entry_price - (atr * 2.0)
```
- **Purpose**: Adapts to stock's volatility
- **Example**: 
  - Entry: ₹6,250
  - ATR: ₹150 (2.4%)
  - Stop: ₹6,250 - (₹150 * 2) = ₹5,950

**Layer 3: Chandelier Stop (Trailing)** ⭐
```python
chandelier = highest_price - (atr * 2.5)
```
- **Purpose**: Protect profits as position moves up
- **Updates**: Every time `highest_price` increases
- **Example**:
  ```
  Entry: ₹6,250 | Highest: ₹6,250 | ATR: ₹150
  Chandelier: ₹6,250 - (₹150 * 2.5) = ₹5,875
  
  [Price moves to ₹6,500]
  Highest: ₹6,500 (updated)
  Chandelier: ₹6,500 - (₹150 * 2.5) = ₹6,125 ✅ (stop moved up)
  
  [Price pulls back to ₹6,300]
  Highest: ₹6,500 (stays)
  Chandelier: ₹6,125 (stays) ← Trailing protection
  ```

**Why Chandelier is KEY**:
- Automatically locks in profits
- Trails below highest price (never drops)
- Gives room for normal pullbacks (2.5x ATR)
- Professional-grade stop

**Layer 4: Support-Based Stop**
```python
recent_low = df['Low'].tail(20).min()
support_stop = recent_low * 0.98  # 2% buffer below support
```
- **Purpose**: Respect technical levels
- **Example**:
  - Recent 20-day low: ₹6,000
  - Support stop: ₹6,000 * 0.98 = ₹5,880

**Layer 5: Time-Based Exit**
```python
if days_held >= 10 and current_price <= entry_price:
    # Force exit - no profit after 10 days
    time_based_exit = True
```
- **Purpose**: Prevent dead capital
- **Only triggers**: If no profit after 10 days
- **Action**: Exit at market price

### How Final Stop is Determined

```python
all_stops = {
    'fixed': 5937.50,
    'atr': 5950.00,
    'chandelier': 6125.00,  ← HIGHEST (tightest)
    'support': 5880.00
}

final_stop = max(all_stops.values())  # = 6125.00
active_method = 'chandelier'
```

**Why take the HIGHEST (tightest) stop?**
- Most protective
- Locks in profits fastest
- Reduces drawdown

### Stop Evolution Example

**Day 1 (Entry)**:
```
Entry: ₹6,250
Highest: ₹6,250
ATR: ₹150

Stops:
  Fixed: ₹5,937 (-5.0%)
  ATR: ₹5,950 (-4.8%)
  Chandelier: ₹5,875 (-6.0%)
  Support: ₹5,880 (-5.9%)

Final Stop: ₹5,950 (ATR is tightest) ✅
Risk: -₹300 per share (-4.8%)
```

**Day 3 (Price rises to ₹6,500)**:
```
Entry: ₹6,250
Current: ₹6,500
Highest: ₹6,500 (updated)
ATR: ₹150

Stops:
  Fixed: ₹5,937 (unchanged)
  ATR: ₹5,950 (unchanged from entry)
  Chandelier: ₹6,500 - 375 = ₹6,125 ← MOVED UP ✅
  Support: ₹5,880 (unchanged)

Final Stop: ₹6,125 (Chandelier now tightest) ✅
Risk: Now PROFIT protected! (+₹125 above entry)
```

**Day 5 (Price pulls back to ₹6,350)**:
```
Entry: ₹6,250
Current: ₹6,350
Highest: ₹6,500 (stays at peak)
ATR: ₹150

Stops:
  Chandelier: ₹6,500 - 375 = ₹6,125 (UNCHANGED) ✅

Final Stop: ₹6,125
→ Stop did NOT drop (trailing protection working)
→ Profit still protected even in pullback
```

**Day 7 (Price rises to ₹6,750 - TP hit!)**:
```
Current: ₹6,750
TP: ₹6,750
✅ EXIT at TP (no need for stop)
```

---

## 5. TP Calculation

### Take Profit Targets

**Formula**:
```python
# Range: +7% to +12%
# Default: Based on score and volatility

if score >= 75 and volatility == "LOW":
    take_profit = entry_price * 1.12  # +12% (aggressive)
elif score >= 70:
    take_profit = entry_price * 1.10  # +10% (moderate)
else:
    take_profit = entry_price * 1.07  # +7% (conservative)

# AI override (if available)
if ai_suggested_target:
    take_profit = ai_suggested_target
```

### Example Calculations

**Conservative (Score 65-69)**:
```
Entry: ₹6,250
TP: ₹6,250 * 1.07 = ₹6,687.50 (+7%)
SL: ₹5,950 (-4.8%)
R:R = 300 / 437.50 = 1:1.46
```

**Moderate (Score 70-74)**:
```
Entry: ₹6,250
TP: ₹6,250 * 1.10 = ₹6,875 (+10%)
SL: ₹5,950 (-4.8%)
R:R = 300 / 625 = 1:2.08 ✅
```

**Aggressive (Score 75+, Low Volatility)**:
```
Entry: ₹6,250
TP: ₹6,250 * 1.12 = ₹7,000 (+12%)
SL: ₹5,950 (-4.8%)
R:R = 300 / 750 = 1:2.5 ✅✅
```

**AI-Suggested (Overrides default)**:
```
Entry: ₹6,250
AI Target: ₹6,750 (+8%)
AI Stop: ₹5,950 (-4.8%)
R:R = 300 / 500 = 1:1.67
→ Use AI suggestion if confidence > 70%
```

---

## 6. Monitoring Process

### Script: monitor_swing_pg.py
### Frequency: Every 5 minutes (9:00 AM - 3:30 PM)

### What It Does

**Step 1: Load Active Positions**
```python
positions = db.execute("""
    SELECT ticker, entry_price, quantity, stop_loss, take_profit,
           highest_price, days_held, entry_date
    FROM positions
    WHERE status = 'HOLD' AND strategy = 'SWING'
""")
```

**Step 2: Fetch Current Prices**
```python
for position in positions:
    current_price = get_latest_price(position['ticker'])
    
    # Update days held
    days_held = (current_date - entry_date).days
```

**Step 3: Update Highest Price**
```python
if current_price > highest_price:
    highest_price = current_price
    
    # Recalculate Chandelier stop
    atr = calculate_atr(df)
    new_chandelier = highest_price - (atr * 2.5)
    
    # Update stop if Chandelier is now tightest
    new_stop = max(fixed_stop, atr_stop, new_chandelier, support_stop)
    
    db.execute("""
        UPDATE positions
        SET highest_price = %s,
            stop_loss = %s
        WHERE ticker = %s AND strategy = 'SWING'
    """, (highest_price, new_stop, ticker))
```

**Step 4: Check Exit Conditions**
```python
# TP hit
if current_price >= take_profit:
    exit_position(ticker, 'TP')

# SL hit (dynamic stop)
elif current_price <= stop_loss:
    exit_position(ticker, 'SL')

# Time exit (10 days)
elif days_held >= 10:
    exit_position(ticker, 'MAX-HOLD')
```

### Monitor Log Example

```
[2024-11-13 10:15:22] Monitoring 3 SWING positions...
[2024-11-13 10:15:23]   COFORGE.NS: Day 3 | ₹6,500 | P&L: +₹2,000 (+4.0%)
                        Highest: ₹6,500 | Stop: ₹6,125 (Chandelier) | TP: 3.85% away
[2024-11-13 10:15:24]   RELIANCE.NS: Day 5 | ₹2,520 | P&L: +₹1,360 (+2.86%)
                        Highest: ₹2,550 | Stop: ₹2,387 (Chandelier) | TP: 4.76% away
[2024-11-13 10:15:25]   PERSISTENT.NS: Day 8 | ₹5,450 | P&L: -₹800 (-1.43%)
                        Highest: ₹5,600 | Stop: ₹5,250 (Chandelier) | TP: 8.26% away
[2024-11-13 10:15:26] All positions within TP/SL range
```

---

## 7. Exit Conditions

### Exit Type 1: TP Hit

**Condition**: `current_price >= take_profit`

**Example**:
```
Entry: ₹6,250 @ Day 1
TP: ₹6,750 (+8%)
Current: ₹6,765 @ Day 7

✅ TP HIT
```

**Telegram Alert**:
```
🎯 SWING TP Hit!

Ticker: COFORGE.NS
━━━━━━━━━━━━━━━
Entry: ₹6,250.00
Exit: ₹6,765.00
Profit: ₹4,120 (+8.24%)
━━━━━━━━━━━━━━━
Qty: 8 shares
Hold: 7 days
Time: 2:15 PM

✅ Profit locked
AI Confidence: 88% ✅
Strategy: SWING
```

---

### Exit Type 2: Chandelier Stop Hit (Trailing)

**Condition**: `current_price <= stop_loss` (where stop_loss = Chandelier)

**Example**:
```
Entry: ₹6,250 @ Day 1
Highest: ₹6,500 @ Day 3
Chandelier: ₹6,125
Current: ₹6,120 @ Day 5

⛔ CHANDELIER STOP HIT
```

**This is a GOOD exit!**
- Profit protected: Entry ₹6,250 → Exit ₹6,120 = **-₹130 per share (-2.08%)**
- But highest was ₹6,500 (+4%)
- Chandelier locked in partial profit

**Telegram Alert**:
```
🛑 SWING Stop Hit (Chandelier)

Ticker: COFORGE.NS
━━━━━━━━━━━━━━━
Entry: ₹6,250.00
Highest: ₹6,500.00 (+4.0%)
Exit: ₹6,120.00
P&L: -₹1,040 (-2.08%)
━━━━━━━━━━━━━━━
Qty: 8 shares
Hold: 5 days
Stop Type: Chandelier Trailing

💡 Reason: Price pulled back 5.85% from high
   Chandelier protected against larger loss
Strategy: SWING
```

**Why this is acceptable**:
- Original SL was -4.8% (₹5,950)
- Chandelier moved up to protect profit zone
- Small loss beats -4.8% loss
- System working as designed

---

### Exit Type 3: Initial SL Hit

**Condition**: `current_price <= initial_stop_loss` (before Chandelier kicks in)

**Example**:
```
Entry: ₹6,250 @ Day 1
Never reached higher price
SL: ₹5,950 (-4.8%)
Current: ₹5,945 @ Day 2

⛔ STOP LOSS HIT
```

**Telegram Alert**:
```
🛑 SWING SL Hit

Ticker: COFORGE.NS
Entry: ₹6,250.00
Exit: ₹5,945.00
Loss: -₹2,440 (-4.88%)
━━━━━━━━━━━━━━━
Qty: 8 shares
Hold: 2 days
Stop Type: Initial SL

Reason: Failed to gain traction
Strategy: SWING
```

---

### Exit Type 4: Time-Based Exit (10 Days Max)

**Condition**: `days_held >= 10`

**Example**:
```
Entry: ₹6,250 @ Day 1
Current: ₹6,280 @ Day 10 (+0.48%)
Neither TP nor SL hit

🕐 MAX-HOLD EXIT (10 days)
```

**Telegram Alert**:
```
🕐 SWING Time Exit (MAX-HOLD)

Ticker: COFORGE.NS
Entry: ₹6,250.00
Exit: ₹6,280.00
P&L: +₹240 (+0.48%)
━━━━━━━━━━━━━━━
Qty: 8 shares
Hold: 10 days
Reason: Max hold period reached

💡 Position stagnant - free up capital
   for better opportunities
Strategy: SWING
```

**Why 10 days?**
- Opportunity cost: Capital locked too long
- Momentum lost: If not moving in 10 days, unlikely to
- Reset: Look for fresher setups

---

## 8. Real Trade Walkthrough

### Trade Example: COFORGE.NS

**Strategy**: SWING  
**Capital**: ₹10,00,000 (Mid-cap allocation: ₹2,00,000)

---

#### Day 1 (Nov 13, 9:30 AM) - Entry

**Screening**:
```
COFORGE.NS Analysis:
  RS Rating: 82/99 ✅ (top 18%)
  Technical Score: 72/100 ✅
  
  Indicators:
    RSI: 58 ✅ (< 70, not overbought)
    MACD: Bullish
    Trend: Strong uptrend
    Volume: 1.4x average
    Pullback: 1.8% from 5-day high ✅ (sweet spot)
  
  Nifty Trend: Bullish ✅
  
  Signal: BUY
  Score: 72/100
```

**AI Validation**:
```
Claude AI Analysis:
  ✅ Agrees: Yes
  🎯 Confidence: 88%
  💡 Reasoning: "Strong weekly uptrend confirmed. 
                 Broke ₹6,200 resistance with volume.
                 Support at ₹6,000 (3% below).
                 Weekly RSI: 65 (room to run).
                 Target: ₹6,750 (8%). 
                 Stop: ₹5,950 (4.8%).
                 Risk/reward: 1:1.67. Entry favorable."
```

**Entry Execution**:
```python
Entry Details:
  Ticker: COFORGE.NS
  Category: Mid-cap
  Entry Price: ₹6,250.00
  Quantity: 8 shares
  Investment: ₹50,000
  
  Stops Calculated:
    Fixed: ₹5,937 (-5.0%)
    ATR: ₹5,950 (-4.8%) ← Initial tightest
    Chandelier: ₹5,875 (-6.0%)
    Support: ₹5,880 (-5.9%)
  
  Initial Stop: ₹5,950 (ATR-based)
  Take Profit: ₹6,750 (+8%) [AI suggested]
  
  AI Data:
    ai_agrees: True
    ai_confidence: 0.88
    ai_reasoning: "Strong weekly uptrend..."
```

**Database**:
```sql
INSERT INTO positions (..., ai_agrees, ai_confidence, ai_reasoning)
VALUES ('COFORGE.NS', 'SWING', 6250.00, 8, 5950.00, 6750.00,
        'Mid-cap', CURRENT_DATE, true, 0.88, 
        'Strong weekly uptrend confirmed...');

UPDATE capital_tracker
SET current_trading_capital = current_trading_capital - 50000
WHERE strategy = 'SWING';
```

---

#### Day 2 (Nov 14, 11:00 AM) - Monitoring

```
Current Price: ₹6,320 (+1.12%)
Highest Price: ₹6,350 (reached earlier)

Stops:
  Chandelier: ₹6,350 - (₹150 * 2.5) = ₹5,975
  (Still below ATR stop of ₹5,950)

Active Stop: ₹5,975 (Chandelier moved up slightly)
Unrealized P&L: +₹560 (+1.12%)

Status: HOLD ✅
```

---

#### Day 3 (Nov 15, 2:00 PM) - Price Surge

```
Current Price: ₹6,500 (+4.0%) 🚀
Highest Price: ₹6,500 (new peak)

Stops:
  Fixed: ₹5,937 (unchanged)
  ATR: ₹5,950 (unchanged)
  Chandelier: ₹6,500 - 375 = ₹6,125 ✅ (MOVED UP)
  Support: ₹5,880 (unchanged)

Active Stop: ₹6,125 (Chandelier now tightest)
→ PROFIT PROTECTED! Stop above entry (₹6,250)

Unrealized P&L: +₹2,000 (+4.0%)
Distance to TP: ₹6,750 is 3.85% away

Status: HOLD ✅
```

**Database Update**:
```sql
UPDATE positions
SET current_price = 6500.00,
    highest_price = 6500.00,
    stop_loss = 6125.00,  -- Chandelier moved up
    unrealized_pnl = 2000.00,
    days_held = 3
WHERE ticker = 'COFORGE.NS' AND strategy = 'SWING';
```

---

#### Day 4-5 (Nov 16-17) - Consolidation

```
Day 4:
  Price: ₹6,450 (-0.77% from high)
  Highest: ₹6,500 (stays at peak)
  Stop: ₹6,125 (UNCHANGED) ← Trailing protection
  P&L: +₹1,600 (+3.2%)

Day 5:
  Price: ₹6,380 (-1.85% from high)
  Highest: ₹6,500 (stays)
  Stop: ₹6,125 (UNCHANGED)
  P&L: +₹1,040 (+2.08%)

Status: Normal pullback, stop holding ✅
```

---

#### Day 6 (Nov 19, 10:30 AM) - Breakout

```
Price: ₹6,680 (+2.77% surge)
Highest: ₹6,680 (new peak)

Stops:
  Chandelier: ₹6,680 - 375 = ₹6,305 ✅ (MOVED UP AGAIN)

Active Stop: ₹6,305
→ Profit protected at +₹55 minimum (₹6,305 vs ₹6,250 entry)

P&L: +₹3,440 (+6.88%)
Distance to TP: ₹6,750 is 1.05% away 🎯

Status: HOLD, TP nearly reached
```

---

#### Day 7 (Nov 20, 2:15 PM) - TP HIT! 🎯

```
Price: ₹6,765
Take Profit: ₹6,750
✅ TP EXCEEDED by ₹15
```

**Exit Execution**:
```python
Exit Details:
  Entry: ₹6,250.00
  Exit: ₹6,765.00
  Quantity: 8 shares
  
  P&L:
    Profit: ₹4,120
    ROI: +8.24%
    Hold Time: 7 days
  
  Capital Impact:
    Investment returned: ₹50,000
    Profit locked: ₹4,120
    
    capital_tracker BEFORE:
      current_trading_capital: ₹1,50,000
      total_profits_locked: ₹0
    
    capital_tracker AFTER:
      current_trading_capital: ₹2,00,000 (investment back)
      total_profits_locked: ₹4,120 (profit locked)
```

**Database**:
```sql
-- Close position
UPDATE positions
SET status = 'CLOSED',
    current_price = 6765.00,
    exit_date = CURRENT_DATE,
    realized_pnl = 4120.00,
    days_held = 7
WHERE ticker = 'COFORGE.NS' AND strategy = 'SWING';

-- Credit capital
UPDATE capital_tracker
SET current_trading_capital = current_trading_capital + 50000,
    total_profits_locked = total_profits_locked + 4120,
    last_updated = CURRENT_TIMESTAMP
WHERE strategy = 'SWING';

-- Log trade
INSERT INTO trades (...)
VALUES ('COFORGE.NS', 'SWING', 'SELL', 6765.00, 8, 4120.00,
        'TP Hit @ ₹6,750 | AI confidence: 88%');
```

**Telegram Alert**:
```
🎯 SWING TP Hit!

Ticker: COFORGE.NS
━━━━━━━━━━━━━━━━━━━━
Entry: ₹6,250.00
Exit: ₹6,765.00
Profit: ₹4,120 (+8.24%)
━━━━━━━━━━━━━━━━━━━━
Qty: 8 shares
Hold: 7 days
Time: 2:15 PM

📊 Trade Stats:
  Entry Score: 72/100
  RS Rating: 82/99
  AI Confidence: 88% ✅
  
🛡️ Stop Protection:
  Initial SL: ₹5,950 (-4.8%)
  Final Stop: ₹6,305 (+0.88%) [Chandelier]
  → Profit protected from Day 3
  
✅ Profit locked in capital tracker
Available: ₹2,00,000
Locked Profits: ₹4,120

Strategy: SWING
```

---

### Trade Summary

**Performance**:
```
Entry: ₹6,250 (Nov 13)
Exit: ₹6,765 (Nov 20)
Profit: ₹4,120 (+8.24%)
Hold: 7 days
Daily Return: 1.18% per day
Annualized: 430%+ (if repeated)
```

**What Went Right**:
1. ✅ High RS Rating (82/99) - strong momentum
2. ✅ AI validation (88% confidence)
3. ✅ Entry on 1.8% pullback (not at highs)
4. ✅ Chandelier stop protected profit from Day 3
5. ✅ TP reached in 7 days (well before 10-day limit)

**Risk Management**:
```
Max Risk: ₹2,400 (₹5,950 SL)
Risk: 4.8% downside
Reward: 8% upside
R:R Ratio: 1:1.67 ✅

Actual Outcome: +8.24% (exceeded target)
```

---

## Summary: SWING Strategy Success Factors

### What Makes It Work
1. ✅ **Higher selectivity** (score >= 65, RS >= 65)
2. ✅ **AI validation** (optional but powerful)
3. ✅ **Smart multi-layer stops** (Chandelier protects profits)
4. ✅ **Room to run** (7-12% targets over 3-10 days)
5. ✅ **Entry filters** (RSI < 70, pullback check)
6. ✅ **Automatic profit protection** (trailing stops)

### Common Pitfalls to Avoid
1. ❌ Entering at RSI > 70 (overbought)
2. ❌ Buying at all-time highs (no pullback)
3. ❌ Ignoring AI warnings (if < 50% confidence)
4. ❌ Disabling Chandelier stop (removes profit protection)
5. ❌ Holding beyond 10 days without progress
6. ❌ Over-allocating (respect 14% position limit)

### Key Differences from DAILY
| Aspect | DAILY | SWING |
|--------|-------|-------|
| Patience | None (exit 3:25 PM) | 3-10 days |
| Stops | Fixed TP/SL | Smart trailing (Chandelier) |
| Targets | 5-7% | 7-12% |
| Selectivity | Moderate (60+) | High (65+) |
| AI | No | Yes (recommended) |

---

**Last Updated**: 2024-11-13  
**Version**: 2.0  

**Next Steps**: 
- Review **00-QUICKSTART.md** for quick commands
- See **02-DATABASE-SCHEMA.md** for data queries
- Check **04-DAILY-STRATEGY.md** for comparison

**Happy Trading! 📈**
