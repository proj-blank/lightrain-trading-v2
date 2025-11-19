# Global Market Sentiment System

**Last Updated**: 2024-11-19 (Added actual implementation details)

## 🌍 Overview

Solves the **overnight gap problem**: US/Asia markets move while India is closed, creating prediction opportunities.

**Note**: This document covers both the conceptual framework AND the actual implemented regime-based system (`global_market_filter.py`)

---

## 🎯 The Problem We're Solving

**Scenario:**
1. **3:30 PM IST** - India market closes, NIFTY down -1%, sentiment negative
2. **7:00 PM IST** - US markets open, rally +2% overnight
3. **12:30 AM IST** - Japan (Nikkei) opens higher, continues rally
4. **9:15 AM IST** - India opens with +1.5% gap up

**Without this system**: Your bot skipped good stocks yesterday because sentiment was negative.

**With this system**: Pre-market check at 8:45 AM detects bullish global cues, adjusts strategy BEFORE market opens.

---

## 📊 What Gets Tracked

### **1. US Markets (Overnight Session)**
- S&P 500, Nasdaq, Dow changes
- VIX (fear gauge)
- US futures (pre-market if available)

### **2. Asian Markets (Today's Session)**
- Nikkei (Japan) - opens 6:30 AM IST
- Hang Seng (Hong Kong) - opens 6:15 AM IST
- Shanghai Composite
- **SGX Nifty** (Singapore Nifty futures) ← Best predictor!

### **3. India Context**
- Previous NIFTY close
- India VIX
- Expected gap based on correlations

---

## ⏰ Daily Flow

### **8:45 AM IST - Pre-Market Check**
```
1. Fetch overnight US data (closed ~5:30 AM IST)
2. Fetch Asian market data (live or just closed)
3. Calculate global sentiment score
4. Predict NIFTY opening gap
5. Send Telegram alert if significant
6. Save to database for analysis
```

### **9:15 AM IST - Market Opens**
Your trading bots read the global sentiment and adjust:
- **Bullish overnight (+1% gap expected)** → Increase position sizes by 30%
- **Bearish overnight (-1% gap expected)** → Reduce position sizes by 50%
- **Neutral** → Trade normally

---

## 🧮 Sentiment Calculation

**Global Score Formula:**
```
US Score = (S&P500 change + Nasdaq change) / 2
Asia Score = (Nikkei change + Hang Seng change) / 2
VIX Score = -VIX change (inverse: high VIX = bad)

Global Score = (US × 40%) + (Asia × 40%) + (VIX × 20%)
```

**Expected NIFTY Gap:**
```
Gap = (US Score × 0.6) + (Asia Score × 0.3)
```
*Based on historical ~60% correlation with S&P500, 30% with Asia*

---

## 📈 Strategy Adjustments

| Global Sentiment | Expected Gap | Action | Position Multiplier |
|-----------------|--------------|--------|-------------------|
| Strong Bullish | > +1.0% | BOOST | 1.3x (30% larger) |
| Moderate Bullish | +0.5% to +1.0% | BOOST | 1.15x (15% larger) |
| Neutral | -0.5% to +0.5% | NORMAL | 1.0x |
| Moderate Bearish | -1.0% to -0.5% | REDUCE | 0.7x (30% smaller) |
| Strong Bearish | < -1.0% | REDUCE | 0.5x (50% smaller) |
| High VIX (>25) | Any | REDUCE | 0.6x (40% smaller) |

---

## 📊 Database Tables

### **global_market_indicators**
Stores every pre-market snapshot:
- US market closes (S&P, Nasdaq, VIX)
- Asian market data (Nikkei, Hang Seng)
- SGX Nifty futures
- Calculated sentiment and gap prediction

### **Key Queries**

**Today's sentiment:**
```sql
SELECT * FROM latest_global_sentiment;
```

**Pre-market signal:**
```sql
SELECT * FROM premarket_signal;
```

**Prediction accuracy:**
```sql
SELECT * FROM overnight_accuracy
ORDER BY snapshot_date DESC
LIMIT 30;
```

**How often do we get it right?**
```sql
SELECT
    prediction_accuracy,
    COUNT(*),
    AVG(ABS(predicted_gap - actual_gap)) as avg_error
FROM overnight_accuracy
GROUP BY prediction_accuracy;
```

---

## 🚀 Usage Examples

### **Scenario 1: Friday Night Rally**
```
Friday 3:30 PM IST: NIFTY closes -0.8%
Friday 11:00 PM IST: US rallies +1.5% on jobs data

Monday 8:45 AM IST: Pre-market check runs
- Detects: US +1.5%, Weekend effect
- Predicts: NIFTY gap +1.0%
- Action: BOOST positions by 30%
- Telegram: "🚀 Strong global rally, increase allocations"

Monday 9:20 AM IST: Daily trading runs
- Finds 5 BUY signals
- Normally buys ₹50k each = ₹2.5L total
- With BOOST: ₹65k each = ₹3.25L total
- Captures gap-up opportunity!
```

### **Scenario 2: Asia Weakness**
```
Tuesday 8:45 AM IST: Pre-market check
- US: Flat (+0.1%)
- Nikkei: -1.8% (Japan PMI miss)
- Hang Seng: -1.2% (China concerns)
- Predicts: NIFTY gap -0.8%
- Action: REDUCE positions by 30%
- Telegram: "⚠️ Weak Asian markets, reduce risk"

Tuesday 9:20 AM IST: Daily trading runs
- Finds 3 BUY signals
- Normally buys ₹50k each = ₹1.5L total
- With REDUCE: ₹35k each = ₹1.05L total
- Avoids overexposure before potential selloff
```

### **Scenario 3: VIX Spike (Risk-Off)**
```
Wednesday 8:45 AM IST: Pre-market check
- US: -0.5%
- VIX: 28 (was 18 yesterday) ← Spike!
- Risk Mode: RISK_OFF
- Action: REDUCE positions by 40%
- Telegram: "⚠️ Risk-off environment, high volatility"

Wednesday 9:20 AM: Trade conservatively
- Only take highest-conviction signals (score > 75)
- Smaller positions
```

---

## 🔧 Configuration

All logic in `scripts/global_market_sentiment.py`:

**Adjust sensitivity:**
```python
# Make more aggressive
if gap > 0.3:  # Instead of 0.5
    return 'BOOST', 1.4  # Instead of 1.15

# Make more conservative
if gap > 1.5:  # Instead of 1.0
    return 'BOOST', 1.2  # Instead of 1.3
```

**Change correlation weights:**
```python
# Give more weight to Asian markets
expected_gap = (us_score * 0.4) + (asia_score * 0.5)
```

---

## 📱 Telegram Notifications

You get alerted only when significant:

**BOOST Alert:**
```
🚀 PRE-MARKET ALERT

Global Sentiment: BULLISH
Expected NIFTY Gap: +1.2%

US Overnight:
S&P 500: +1.5%
Nasdaq: +1.8%

Strategy Adjustment:
BOOST - Strong global rally
Position sizes: 130%
```

**REDUCE Alert:**
```
⚠️ PRE-MARKET ALERT

Global Sentiment: BEARISH
Expected NIFTY Gap: -0.9%

US Overnight:
S&P 500: -0.8%
Nasdaq: -1.2%

Strategy Adjustment:
REDUCE - Weak global markets
Position sizes: 70%
```

---

## 📈 Measuring Success

After 30 days, analyze:

**1. Gap prediction accuracy:**
```sql
SELECT
    AVG(ABS(overnight_gap_expected - actual_gap)) as avg_error,
    COUNT(CASE WHEN prediction_accuracy = 'CORRECT' THEN 1 END) * 100.0 / COUNT(*) as accuracy_pct
FROM overnight_accuracy;
```

**2. Strategy performance by action:**
```sql
SELECT
    g.global_sentiment,
    AVG(t.pnl) as avg_pnl,
    COUNT(*) as trades
FROM global_market_indicators g
JOIN trades t ON DATE(t.trade_date) = g.snapshot_date
WHERE t.signal = 'SELL'
GROUP BY g.global_sentiment;
```

**3. Did BOOSTs help?**
```sql
-- Compare days with BOOST vs NORMAL
SELECT
    CASE WHEN overnight_gap_expected > 0.5 THEN 'BOOST_DAY' ELSE 'NORMAL_DAY' END,
    AVG(daily_pnl) as avg_profit
FROM (
    SELECT
        g.snapshot_date,
        g.overnight_gap_expected,
        SUM(t.pnl) as daily_pnl
    FROM global_market_indicators g
    JOIN trades t ON DATE(t.trade_date) = g.snapshot_date
    WHERE t.signal = 'SELL'
    GROUP BY g.snapshot_date, g.overnight_gap_expected
) sub
GROUP BY 1;
```

---

## ⚠️ Limitations

1. **Not 100% accurate** - Markets can gap opposite to prediction
2. **News events** - Sudden India-specific news can override global cues
3. **SGX Nifty access** - Best predictor but may need paid data
4. **Correlation changes** - Adjust weights based on observed accuracy

---

## 🔮 Future Enhancements

1. **SGX Nifty integration** (requires paid data)
2. **Weekend sentiment scraping** (news over Sat-Sun)
3. **FII/DII flow data** (institutional money movement)
4. **Sector-specific gaps** (IT stocks gap more on Nasdaq moves)
5. **Machine learning** - Learn optimal correlation weights over time

---

## 💡 Key Insight

**This gives you a 30-minute head start every morning.**

While other traders react to the opening gap at 9:15 AM, you've already:
- Predicted the gap at 8:45 AM
- Adjusted position sizes
- Prepared for gap-up or gap-down scenarios

**First-mover advantage = Better entries = Higher returns**

---

## 🔧 ACTUAL IMPLEMENTED SYSTEM (GlobalMarketFilter)

**File**: `global_market_filter.py`
**Class**: `GlobalMarketFilter`
**Last Updated**: 2024-11-19 (Refactored as single source of truth)

### Architecture

**Single Source of Truth Principle**:
- ALL regime calculations use `GlobalMarketFilter` class
- Morning 8:30 AM check: Saves to file + database
- /gc Telegram command: Live query only (no save)
- 2 PM regime check: Compares current vs morning baseline

### Regime Scoring System

**Indicators & Weights**:
```python
S&P 500 Futures (ES=F):  35% weight  (±2 points max)
Nikkei 225 (^N225):      25% weight  (±2 points max)
Hang Seng (^HSI):        20% weight  (±1.5 points max)
Gold Futures (GC=F):     10% weight  (±2 points max, INVERSE)
VIX (^VIX):              10% weight  (±3 points max)
```

**Regime Classifications**:
```
Score >= 4:  BULL      (Position sizing: 100%, New entries: YES)
Score 1-4:   NEUTRAL   (Position sizing: 75%, New entries: YES)
Score -2-1:  CAUTION   (Position sizing: 50%, New entries: YES)
Score <= -3: BEAR      (Position sizing: 0%, New entries: HALT)
```

### Daily Workflow

#### 8:30 AM IST - Morning Regime Check
```bash
cron: 30 8 * * 1-5  # 8:30 AM IST
script: run_market_check.sh → global_market_filter.py
```

**Actions**:
1. Fetch all 5 indicators via yfinance
2. Calculate regime score
3. Determine regime (BULL/NEUTRAL/CAUTION/BEAR)
4. **Save to file**: `/home/ubuntu/trading/data/market_regime.json`
5. **Save to database**: `market_regime_history` table
6. Send Telegram alert if regime changed

**File Output** (`market_regime.json`):
```json
{
  "regime": "BULL",
  "score": 5.5,
  "allow_new_entries": true,
  "position_sizing_multiplier": 1.0,
  "details": "S&P: +1.2%, Nikkei: +0.8%, Hang Seng: +0.5%, Gold: -0.3%, VIX: 14.2",
  "timestamp": "2024-11-19 08:30:00"
}
```

**Database Output** (`market_regime_history`):
- Stores all indicator prices and changes
- One record per day (UNIQUE constraint on check_date)
- Used for historical analysis and backtesting

#### 2:00 PM IST - Intraday Deterioration Check
```bash
cron: 0 14 * * 1-5  # 2:00 PM IST
script: regime_2pm_check.py
```

**Purpose**: Alert if regime deteriorates during the day

**Actions**:
1. Read morning regime from `market_regime.json`
2. Calculate LIVE regime score (using GlobalMarketFilter)
3. Compare: `score_change = current_score - morning_score`
4. Alert if:
   - Score drops ≥ 3 points: "SEVERE DETERIORATION"
   - Score drops ≥ 2 points: "MODERATE DETERIORATION"
   - Current regime is BEAR: "BEAR REGIME DETECTED"
5. Recommend `/exitall` if severe

#### Real-Time /gc Command
```bash
Telegram: /gc
Handler: telegram_bot_listener.py → handle_gc()
```

**Actions**:
1. Read morning baseline from `market_regime.json`
2. Create `GlobalMarketFilter()` instance
3. Fetch LIVE data for all 5 indicators
4. Calculate LIVE regime score
5. Fetch India indices via AngelOne API (NEW Nov 19):
   - Nifty 50 (Large-cap)
   - Nifty Mid 150 (Mid-cap)
   - Nifty Small 250 (Small-cap)
6. Format and send response
7. **Does NOT save** to file or database

**Why /gc doesn't save**:
- Keep database clean (one record per day)
- Live queries are for intraday monitoring only
- Historical analysis should use 8:30 AM data

### Database Integration (Nov 19, 2024)

**New Columns Added** to `market_regime_history`:
```sql
-- Price & change columns for all indicators
sp_futures_price NUMERIC(10, 2),
sp_futures_change_pct NUMERIC(5, 2),
nikkei_price NUMERIC(10, 2),
nikkei_change_pct NUMERIC(5, 2),
hang_seng_price NUMERIC(10, 2),
hang_seng_change_pct NUMERIC(5, 2),
gold_price NUMERIC(10, 2),
gold_change_pct NUMERIC(5, 2),
vix_value NUMERIC(5, 2)
```

**Implementation**:
```python
# global_market_filter.py
class GlobalMarketFilter:
    def save_to_database(self, analysis):
        """Save regime check to SQL (8:30 AM only)"""
        with get_db_cursor() as cur:
            cur.execute("""
                INSERT INTO market_regime_history (
                    check_date, regime, score,
                    sp_futures_price, sp_futures_change_pct,
                    ...
                ) VALUES (%s, %s, %s, %s, %s, ...)
                ON CONFLICT (check_date) DO UPDATE SET ...
            """)
```

### Refactoring History (Nov 19, 2024)

**Problem**: Duplicate scoring logic
- `telegram_bot_listener.py` had 177 lines of duplicate scoring
- Different results from morning check
- Hard to maintain

**Solution**: Single Source of Truth
- All regime calculations → `GlobalMarketFilter` class
- `/gc` handler reduced from 177 lines to 85 lines
- Guaranteed consistency across all checks

### India Market Indices (Nov 19, 2024)

**Added to /gc command**:
```python
# Fetch live via AngelOne API
benchmarks = {
    'Nifty 50 (Large)': ('99926000', 'NIFTY 50'),
    'Nifty Mid 150': ('99926023', 'NIFTY MIDCAP 150'),
    'Nifty Small 250': ('99926037', 'NIFTY SMLCAP 250')
}
```

**Purpose**:
- Intraday context for position decisions
- See if large/mid/small caps moving differently
- Helps decide which category to focus on

### Key Files

**Core Implementation**:
- `global_market_filter.py` - GlobalMarketFilter class (single source)
- `run_market_check.sh` - 8:30 AM wrapper script
- `regime_2pm_check.py` - Intraday deterioration check
- `telegram_bot_listener.py` - /gc command handler

**Data Files**:
- `/home/ubuntu/trading/data/market_regime.json` - Current regime state
- Database: `market_regime_history` table

**Helper Scripts**:
- `scripts/db_connection.py` - Database utilities
- `scripts/telegram_bot.py` - Telegram messaging

### Trading Integration

**How strategies use regime**:
```python
# daily_trading_pg.py & swing_trading_pg.py
import json

# Read morning regime
with open('/home/ubuntu/trading/data/market_regime.json', 'r') as f:
    regime_data = json.load(f)

if not regime_data['allow_new_entries']:
    print("🚫 BEAR regime detected - HALTING new entries")
    sys.exit(0)

# Adjust position sizing
multiplier = regime_data['position_sizing_multiplier']
position_size = base_position_size * multiplier
```

### Best Practices

**Do**:
- ✅ Use /gc for intraday checks before new entries
- ✅ Trust the morning 8:30 AM regime for the day
- ✅ Exit positions if 2 PM check shows severe deterioration
- ✅ Check VIX spikes (>25) for risk-off periods

**Don't**:
- ❌ Override BEAR regime (score ≤ -3) without strong reason
- ❌ Enter new positions if regime deteriorated significantly
- ❌ Ignore 2 PM alerts about regime changes
- ❌ Manually edit market_regime.json file

### Configuration

**Adjust regime thresholds** (`global_market_filter.py`):
```python
def analyze_regime(self):
    if self.score >= 4:
        regime = "BULL"
        sizing = 1.0
    elif self.score >= 1:
        regime = "NEUTRAL"
        sizing = 0.75
    # ... etc
```

**Adjust indicator weights**:
```python
# In scoring methods:
if sp_change > 1:
    sp_pts = 2  # Max 2 points for S&P
elif sp_change > 0:
    sp_pts = 1
# ... etc
```

---

## 📊 Summary: Conceptual vs Implemented

| Feature | Conceptual (This Doc) | Implemented (Actual) |
|---------|----------------------|---------------------|
| Gap Prediction | ✓ Described | ✗ Not implemented |
| SGX Nifty | ✓ Mentioned | ✗ Not used |
| Regime Scoring | ✓ Described | ✓ **Fully implemented** |
| Database Logging | ✓ Mentioned | ✓ **market_regime_history** |
| /gc Command | - | ✓ **Live with India indices** |
| 2 PM Check | - | ✓ **Deterioration alerts** |
| Single Source | - | ✓ **GlobalMarketFilter class** |

**Key Takeaway**: The actual system is a **regime-based approach** rather than gap prediction. Focus on regime scoring for position sizing decisions.
