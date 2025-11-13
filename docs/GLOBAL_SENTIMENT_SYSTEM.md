# Global Market Sentiment System

## 🌍 Overview

Solves the **overnight gap problem**: US/Asia markets move while India is closed, creating prediction opportunities.

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
