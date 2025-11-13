# LightRain Trading System - Screening & Scoring

**Last Updated**: 2024-11-13  
**Purpose**: Detailed explanation of stock selection, technical scoring, and entry criteria

---

## Table of Contents
1. [Overview](#overview)
2. [DAILY Screening Process](#daily-screening-process)
3. [SWING Screening Process](#swing-screening-process)
4. [Technical Indicators Explained](#technical-indicators-explained)
5. [Scoring Methodology](#scoring-methodology)
6. [RS Rating System](#rs-rating-system)
7. [Real Examples](#real-examples)

---

## 1. Overview

The LightRain system uses a **two-stage filtering process**:

### Stage 1: Universe Selection
- **NSE Universe**: 351 stocks across Large-cap, Mid-cap, Microcap
- **Source**: `stocks_screening.py` populates `screened_stocks` table daily at 8:30 AM
- **Categories**:
  - Large-cap: ~50 stocks (Nifty 50 + liquid stocks)
  - Mid-cap: ~150 stocks (Nifty Midcap 150)
  - Micro-cap: ~151 stocks (high-growth potential)

### Stage 2: Technical Scoring
- **DAILY**: Score 0-100 based on 9 technical indicators
- **SWING**: Score 0-100 with additional filters
- **Threshold**: Min 60 (DAILY), Min 65 (SWING)
- **RS Rating**: Min 60/99 (DAILY), Min 65/99 (SWING)

**Signal Generation Flow**:
```
Universe (351 stocks)
    │
    ├─► Download 6-month OHLCV data
    │
    ├─► Calculate RS Rating (rank 1-99)
    │   └─► Filter: >= 60 (DAILY), >= 65 (SWING)
    │
    ├─► Calculate 9 Technical Indicators
    │   ├─ RSI
    │   ├─ MACD
    │   ├─ Bollinger Bands
    │   ├─ Volume
    │   ├─ Trend Strength
    │   ├─ ATR/Volatility
    │   ├─ ROC (Rate of Change)
    │   ├─ CCI (Commodity Channel Index)
    │   └─ Donchian Channels
    │
    ├─► Generate Weighted Score (0-100)
    │   └─► Filter: >= 60 (DAILY), >= 65 (SWING)
    │
    ├─► AI Validation (SWING only)
    │   └─► Claude analyzes weekly chart
    │
    └─► ENTRY SIGNAL (BUY/HOLD/SELL)
```

---

## 2. DAILY Screening Process

### Run Time: 9:00 AM IST
### Script: `daily_screening.py` + `daily_trading_pg.py`

### Step-by-Step Process

**Step 1: Load Universe**
```python
# From screened_stocks table
stocks = db.execute("""
    SELECT ticker, category 
    FROM screened_stocks 
    WHERE last_updated = CURRENT_DATE
""")
# Returns: ~351 stocks
```

**Step 2: Download Price Data**
```python
# 6 months of daily candles (min 60 days required)
df = yf.download(ticker, period="6mo", interval="1d")
```

**Step 3: RS Rating Filter (Pre-filter)**
```python
rs_rating = calculate_rs_rating(ticker)
# Based on 3M, 6M, 9M, 12M returns vs. universe
# Weighted: 40% (3M) + 30% (6M) + 20% (9M) + 10% (12M)

if rs_rating < 60:
    skip_ticker()  # Reject weak stocks early
```

**Why RS first?** Saves computation time by filtering out 40% of stocks before expensive indicator calculations.

**Step 4: Technical Analysis (9 Indicators)**

Each indicator contributes to overall score with specific weights:

| Indicator | Weight | Purpose |
|-----------|--------|---------|
| RSI | 20% | Overbought/oversold momentum |
| MACD | 25% | Trend direction & crossovers |
| Bollinger Bands | 15% | Volatility & price extremes |
| Volume | 10% | Confirmation of price moves |
| Trend Strength | 10% | Overall trend direction |
| ATR/Volatility | 5% | Risk assessment |
| ROC | 5% | Price momentum |
| CCI | 5% | Cyclical trends |
| Donchian | 5% | Breakout detection |
| **TOTAL** | **100%** | |

**Step 5: Calculate Weighted Score**
```python
# Each indicator returns signal (BUY/SELL/HOLD) + score (0-100)
signals = []
scores = []

# Example for RSI (20% weight)
if rsi < 30:
    signals.append("BUY")
    scores.append(80)  # Strong buy signal

# Weighted aggregation
weights = [0.20, 0.25, 0.15, 0.10, 0.10, 0.05, 0.05, 0.05, 0.05]
total_score = sum(score * weight for score, weight in zip(scores, weights))
```

**Step 6: Generate Final Signal**
```python
buy_count = signals.count("BUY")
sell_count = signals.count("SELL")

if buy_count > sell_count and total_score >= 60:
    return "BUY", total_score
elif sell_count > buy_count:
    return "SELL", total_score
else:
    return "HOLD", total_score
```

**Step 7: Entry Execution**

Only if:
- ✅ Signal = BUY
- ✅ Score >= 60
- ✅ RS Rating >= 60
- ✅ Sufficient capital available
- ✅ No circuit breaker flags

---

## 3. SWING Screening Process

### Run Time: 9:25 AM IST
### Script: `swing_trading_pg.py`

### Key Differences from DAILY

| Aspect | DAILY | SWING |
|--------|-------|-------|
| **Min Score** | 60/100 | 65/100 |
| **Min RS** | 60/99 | 65/99 |
| **Data Period** | 6 months daily | 6 months daily + weekly analysis |
| **AI Validation** | No | Yes (optional) |
| **Entry Filters** | None | RSI < 70, Pullback 0.5-3% |
| **Market Regime** | Not checked | Nifty trend checked |

### SWING-Specific Filters

**Filter 1: RSI Overbought Filter**
```python
if current_rsi > 70:
    return "HOLD", 0, {"rejection": "RSI Overbought"}
```
**Reason**: Avoid buying at tops in multi-day holds.

**Filter 2: Pullback Filter**
```python
high_5d = df['High'].tail(5).max()
pullback_pct = ((high_5d - current_price) / high_5d) * 100

if pullback_pct < 0.5:
    # Too close to highs
    score -= 15  # -15 points penalty
elif pullback_pct > 4.0:
    # Too far from highs
    score -= 10  # -10 points penalty
# Sweet spot: 0.5-3% pullback (no penalty)
```
**Reason**: Better risk/reward on slight pullbacks vs. all-time highs.

**Filter 3: Market Regime Filter**
```python
nifty = yf.download('^NSEI', period='1mo')
nifty_sma20 = nifty['Close'].rolling(20).mean()

if nifty_current < nifty_sma20:
    # Bearish market
    score -= 10  # More selective in downtrends
```
**Reason**: Align with broader market direction.

### AI Validation (SWING Only)

**When**: After technical score >= 65

**What Claude Analyzes**:
- Weekly chart pattern
- Support/resistance levels
- Trend strength
- Volume profile
- Risk/reward ratio
- Breakout potential

**Example Prompt to Claude**:
```
Analyze this stock for swing trade (3-10 days):
- Weekly chart shows: [price data]
- Current price: ₹520
- 20-week SMA: ₹485
- Volume: Above average
- RS Rating: 72/99

Should I enter? What's the target and stop loss?
```

**AI Response Format**:
```json
{
  "ai_agrees": true,
  "ai_confidence": 0.85,
  "ai_reasoning": "Strong weekly uptrend. Broke resistance at ₹500 with volume. Support at ₹480. Target: ₹570 (8-10%). Stop: ₹490 (5%). Risk/reward: 1:2 favorable."
}
```

**AI Not Required**: Trade executes even if AI skipped, but stores `ai_agrees=NULL`.

---

## 4. Technical Indicators Explained

### 4.1 RSI (Relative Strength Index) - 20% Weight

**What it measures**: Momentum (overbought/oversold)

**Calculation**:
```python
def calculate_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi
```

**Interpretation**:
- **< 30**: Oversold (BUY signal, score: 80)
- **30-40**: Moderately oversold (BUY, score: 60)
- **40-60**: Neutral (HOLD, score: 50)
- **60-70**: Moderately overbought (SELL, score: 60)
- **> 70**: Overbought (SELL, score: 80)

**Why 20% weight?** Most reliable single indicator for intraday momentum.

**Example**:
```
Stock: RELIANCE.NS
RSI: 28.5 → Oversold
Signal: BUY
Score: 80
Contribution: 80 * 0.20 = 16 points
```

---

### 4.2 MACD (Moving Average Convergence Divergence) - 25% Weight

**What it measures**: Trend direction and strength

**Calculation**:
```python
def calculate_macd(df):
    ema12 = df['Close'].ewm(span=12).mean()
    ema26 = df['Close'].ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    histogram = macd - signal
    return macd, signal, histogram
```

**Interpretation**:
- **Bullish Crossover**: MACD crosses above signal (BUY, score: 85)
- **Bullish Continuation**: MACD > signal, histogram > 0 (BUY, score: 65)
- **Bearish Crossover**: MACD crosses below signal (SELL, score: 85)
- **Bearish Continuation**: MACD < signal, histogram < 0 (SELL, score: 65)
- **Neutral**: No clear trend (HOLD, score: 50)

**Why 25% weight?** Best trend-following indicator. Crossovers are high-probability signals.

**Example**:
```
Stock: TCS.NS
MACD: 15.3
Signal: 12.8
Histogram: 2.5 (positive)
Previous: MACD was below signal
→ BULLISH CROSSOVER
Signal: BUY
Score: 85
Contribution: 85 * 0.25 = 21.25 points
```

---

### 4.3 Bollinger Bands - 15% Weight

**What it measures**: Volatility and price extremes

**Calculation**:
```python
def calculate_bollinger_bands(df, period=20, std_dev=2):
    middle = df['Close'].rolling(period).mean()
    std = df['Close'].rolling(period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    return upper, middle, lower
```

**Interpretation**:
```python
bb_position = (current_price - lower) / (upper - lower)

# Position 0.0 = at lower band (oversold)
# Position 0.5 = at middle band (neutral)
# Position 1.0 = at upper band (overbought)
```

- **< 0.2**: Near lower band (BUY, score: 75)
- **0.2-0.4**: Below middle (BUY, score: 60)
- **0.4-0.6**: At middle (HOLD, score: 50)
- **0.6-0.8**: Above middle (SELL, score: 60)
- **> 0.8**: Near upper band (SELL, score: 75)

**Why 15% weight?** Good for mean reversion plays.

**Example**:
```
Stock: INFY.NS
Price: ₹1450
BB Upper: ₹1500
BB Middle: ₹1440
BB Lower: ₹1380
Position: (1450-1380)/(1500-1380) = 0.58 (58%)
→ Slightly above middle
Signal: HOLD
Score: 50
Contribution: 50 * 0.15 = 7.5 points
```

---

### 4.4 Volume Analysis - 10% Weight

**What it measures**: Strength of price moves

**Calculation**:
```python
def analyze_volume(df):
    avg_volume = df['Volume'].rolling(20).mean()
    current_volume = df['Volume'].iloc[-1]
    volume_ratio = current_volume / avg_volume
    
    is_high_volume = volume_ratio > 1.5  # 50% above average
    return {
        'volume_ratio': volume_ratio,
        'is_high_volume': is_high_volume
    }
```

**Interpretation**:
- **High volume + Price up**: Strong buying (BUY, score: 70)
- **High volume + Price down**: Strong selling (SELL, score: 70)
- **Low volume**: Weak signal (HOLD, score: 45)

**Why 10% weight?** Volume confirms price moves but shouldn't dominate.

**Example**:
```
Stock: SBIN.NS
Current Volume: 15M shares
20-day Avg: 10M shares
Ratio: 1.5 (50% above average)
Price Change: +2.3% (up from yesterday)
→ HIGH VOLUME + PRICE UP
Signal: BUY
Score: 70
Contribution: 70 * 0.10 = 7 points
```

---

### 4.5 Trend Strength - 10% Weight

**What it measures**: Overall trend direction

**Calculation**:
```python
def calculate_trend_strength(df):
    sma20 = df['Close'].rolling(20).mean()
    sma50 = df['Close'].rolling(50).mean()
    current_price = df['Close'].iloc[-1]
    
    # Score 0-100 based on:
    # - Price vs SMA20
    # - Price vs SMA50
    # - SMA20 vs SMA50 (alignment)
    # - Slope of SMAs
    
    if current_price > sma20 > sma50:
        # Strong uptrend
        return 80
    elif current_price < sma20 < sma50:
        # Strong downtrend
        return 20
    else:
        # Mixed/sideways
        return 50
```

**Interpretation**:
- **> 65**: Strong uptrend (BUY, score: trend_strength)
- **35-65**: Sideways (HOLD, score: 50)
- **< 35**: Strong downtrend (SELL, score: 100-trend_strength)

**Why 10% weight?** Confirms overall direction.

---

### 4.6 ATR/Volatility - 5% Weight

**What it measures**: Price volatility (risk)

**Calculation**:
```python
def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = abs(df['High'] - df['Close'].shift())
    low_close = abs(df['Low'] - df['Close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    atr_pct = (atr / df['Close']) * 100
    return atr, atr_pct
```

**Interpretation**:
```python
if atr_pct < 2.0:
    volatility = "LOW"      # Stable (score: 60)
elif atr_pct < 4.0:
    volatility = "MODERATE" # Normal (score: 50)
else:
    volatility = "HIGH"     # Risky (score: 40)
```

**Why 5% weight?** Volatility is risk factor, not directional signal.

---

### 4.7 ROC (Rate of Change) - 5% Weight

**What it measures**: Price momentum

**Calculation**:
```python
def calculate_roc(df, period=12):
    roc = ((df['Close'] - df['Close'].shift(period)) / 
           df['Close'].shift(period)) * 100
    return roc
```

**Interpretation**:
- **> 5%**: Strong upward momentum (BUY, score: 60+)
- **2-5%**: Moderate momentum (BUY, score: 65)
- **-2 to 2%**: Flat (HOLD, score: 50)
- **-5 to -2%**: Moderate decline (SELL, score: 65)
- **< -5%**: Strong decline (SELL, score: 60+)

---

### 4.8 CCI (Commodity Channel Index) - 5% Weight

**What it measures**: Cyclical extremes

**Calculation**:
```python
def calculate_cci(df, period=20):
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    sma = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: abs(x - x.mean()).mean())
    cci = (tp - sma) / (0.015 * mad)
    return cci
```

**Interpretation**:
- **< -100**: Oversold (BUY, score: 80)
- **-100 to -50**: Moderately oversold (BUY, score: 65)
- **-50 to 50**: Neutral (HOLD, score: 50)
- **50 to 100**: Moderately overbought (SELL, score: 65)
- **> 100**: Overbought (SELL, score: 80)

---

### 4.9 Donchian Channels - 5% Weight

**What it measures**: Breakouts from trading ranges

**Calculation**:
```python
def calculate_donchian(df, period=20):
    upper = df['High'].rolling(period).max()
    lower = df['Low'].rolling(period).min()
    middle = (upper + lower) / 2
    return upper, middle, lower
```

**Interpretation**:
- **Breakout above upper**: Strong buy (BUY, score: 85)
- **Near upper (98%)**: Approaching breakout (BUY, score: 70)
- **Breakout below lower**: Strong sell (SELL, score: 85)
- **Near lower (102%)**: Approaching breakdown (SELL, score: 70)
- **Inside channel**: Range-bound (HOLD, score: 50)

---

## 5. Scoring Methodology

### How Final Score is Calculated

**Step 1: Individual Indicator Scores**

Each indicator returns:
- **Signal**: BUY / SELL / HOLD
- **Score**: 0-100 (confidence level)

Example:
```python
# RSI Analysis
rsi = 28.5
→ Signal: BUY
→ Score: 80 (strong oversold)

# MACD Analysis
macd_crossover = True
→ Signal: BUY
→ Score: 85 (bullish crossover)

# ... repeat for all 9 indicators
```

**Step 2: Apply Weights**

```python
# DAILY strategy weights
weights = {
    'RSI': 0.20,
    'MACD': 0.25,
    'Bollinger': 0.15,
    'Volume': 0.10,
    'Trend': 0.10,
    'Volatility': 0.05,
    'ROC': 0.05,
    'CCI': 0.05,
    'Donchian': 0.05
}

# Calculate weighted score
scores = [80, 85, 75, 70, 65, 60, 70, 65, 50]  # From each indicator
total_score = sum(score * weight for score, weight in zip(scores, weights.values()))
```

**Step 3: Majority Vote + Score Check**

```python
signals = ['BUY', 'BUY', 'BUY', 'BUY', 'BUY', 'HOLD', 'BUY', 'BUY', 'HOLD']

buy_count = 7
sell_count = 0
hold_count = 2

if buy_count > sell_count and total_score >= 60:
    final_signal = "BUY"
elif sell_count > buy_count:
    final_signal = "SELL"
else:
    final_signal = "HOLD"
```

**Result**:
```
Final Signal: BUY
Final Score: 73.5/100
Entry Allowed: ✅ (score >= 60)
```

---

### Score Interpretation

| Score Range | Meaning | Action |
|-------------|---------|--------|
| **85-100** | Extremely strong signal | High confidence entry |
| **70-84** | Strong signal | Good entry |
| **60-69** | Moderate signal | Acceptable entry (DAILY only) |
| **65-100** | - | Acceptable for SWING |
| **50-59** | Weak signal | Skip |
| **< 50** | Very weak | Skip |

**Why 60 threshold for DAILY?**
- More opportunities needed (1-day hold)
- Lower threshold = more trades
- TP/SL protect from weak signals

**Why 65 threshold for SWING?**
- Multi-day exposure needs stronger conviction
- Higher threshold = more selective
- Better risk/reward required

---

## 6. RS Rating System

### What is Relative Strength (RS) Rating?

**Definition**: Ranks a stock's performance vs. entire universe (1-99 scale)

**Calculation**:
```python
def calculate_rs_rating(ticker):
    # Get returns for multiple periods
    returns = {
        '3m': (price_now - price_3m_ago) / price_3m_ago,
        '6m': (price_now - price_6m_ago) / price_6m_ago,
        '9m': (price_now - price_9m_ago) / price_9m_ago,
        '12m': (price_now - price_12m_ago) / price_12m_ago
    }
    
    # Weighted average (emphasize recent)
    weighted_return = (
        returns['3m'] * 0.40 +
        returns['6m'] * 0.30 +
        returns['9m'] * 0.20 +
        returns['12m'] * 0.10
    )
    
    # Calculate all stocks
    all_weighted_returns = [calculate for all 351 stocks]
    
    # Rank (percentile)
    rank = percentile_rank(weighted_return, all_weighted_returns)
    # Returns 1-99 (99 = top 1% performer)
    
    return int(rank)
```

**Why RS Rating?**
- Filters out weak performers BEFORE expensive calculations
- Momentum persistence: Strong stocks stay strong
- William O'Neil's CAN SLIM methodology (proven)

**Example**:
```
Stock: RELIANCE.NS

Returns:
  3M: +15% (strong)
  6M: +22% (very strong)
  9M: +18% (strong)
  12M: +25% (strong)

Weighted: (15*0.4) + (22*0.3) + (18*0.2) + (25*0.1) = 18.7%

Universe ranking: Top 25%
RS Rating: 75/99 ✅ (passes filter)
```

### RS Rating Thresholds

| Strategy | Min RS | Percentile | Reasoning |
|----------|--------|------------|-----------|
| DAILY | 60 | Top 40% | Moderately selective |
| SWING | 65 | Top 35% | More selective |

**Impact**: Filters ~40-50% of stocks before technical analysis.

---

## 7. Real Examples

### Example 1: Strong BUY Signal (DAILY)

**Stock**: RELIANCE.NS  
**Date**: 2024-11-13 9:15 AM  
**Price**: ₹2,450

**Step 1: RS Rating**
```
3M Return: +12%
6M Return: +18%
9M Return: +15%
12M Return: +20%
Weighted: 15.1%
RS Rating: 72/99 ✅ (passes >= 60)
```

**Step 2: Technical Indicators**

| Indicator | Value | Signal | Score | Weight | Contribution |
|-----------|-------|--------|-------|--------|--------------|
| RSI | 35.2 | BUY | 60 | 20% | 12.0 |
| MACD | Bullish cross | BUY | 85 | 25% | 21.25 |
| Bollinger | 0.25 position | BUY | 75 | 15% | 11.25 |
| Volume | 1.8x avg + up | BUY | 70 | 10% | 7.0 |
| Trend | 72 (uptrend) | BUY | 72 | 10% | 7.2 |
| Volatility | 2.5% ATR | HOLD | 60 | 5% | 3.0 |
| ROC | +3.5% | BUY | 65 | 5% | 3.25 |
| CCI | -75 | BUY | 65 | 5% | 3.25 |
| Donchian | Near upper | BUY | 70 | 5% | 3.5 |
| **TOTAL** | | | | | **71.7** |

**Step 3: Final Decision**
```
BUY signals: 8/9
SELL signals: 0/9
HOLD signals: 1/9
Total Score: 71.7/100 ✅

ENTRY ALLOWED ✅
```

**Position Details**:
```python
Entry Price: ₹2,450
Quantity: 20 shares (based on allocation)
Investment: ₹49,000
Stop Loss: ₹2,352 (-4%)
Take Profit: ₹2,573 (+5%)
Risk/Reward: 1:1.25
```

---

### Example 2: Rejected Entry (SWING)

**Stock**: BATAINDIA.NS  
**Date**: 2024-11-13 9:30 AM  
**Price**: ₹1,685

**Step 1: RS Rating**
```
RS Rating: 58/99 ❌
REJECTED: Below 65 threshold
(No further analysis performed)
```

**Reason**: Weak relative performance. Not in top 35% of universe.

---

### Example 3: Filter Rejection (SWING)

**Stock**: TITAN.NS  
**Date**: 2024-11-13 9:30 AM  
**Price**: ₹3,520

**Step 1: RS Rating**
```
RS Rating: 78/99 ✅
```

**Step 2: Technical Score**
```
Preliminary Score: 68/100 ✅
```

**Step 3: SWING Filters**

**RSI Filter**:
```
RSI: 73.5
❌ REJECTED: RSI > 70 (overbought)
Reason: "Too extended for multi-day hold"
```

**Result**: HOLD (no entry)

**Why this makes sense**: For SWING trades, entering at RSI 73 means high risk of pullback over 3-10 days. Better to wait for RSI 50-65 range.

---

### Example 4: AI Validation (SWING)

**Stock**: COFORGE.NS  
**Date**: 2024-11-13 9:30 AM  
**Price**: ₹6,250

**Technical Analysis**:
```
RS Rating: 82/99 ✅
Technical Score: 72/100 ✅
RSI: 58 ✅ (< 70)
Pullback: 1.8% from 5-day high ✅
```

**AI Analysis** (Claude):
```json
{
  "ai_agrees": true,
  "ai_confidence": 0.88,
  "ai_reasoning": "Strong weekly uptrend confirmed. Broke ₹6,200 resistance with volume. Support at ₹6,000 (3% below). Weekly RSI: 65 (room to run). Target: ₹6,750 (8%). Stop: ₹5,950 (4.8%). Risk/reward: 1:1.67. Entry favorable.",
  "suggested_target": 6750,
  "suggested_stop": 5950
}
```

**Final Decision**:
```
ENTRY ALLOWED ✅

Entry Price: ₹6,250
Quantity: 8 shares
Investment: ₹50,000
Stop Loss: ₹5,950 (AI suggested)
Take Profit: ₹6,750 (AI suggested, 8%)
Risk/Reward: 1:1.67
AI Confidence: 88%
```

**Database Record**:
```sql
INSERT INTO positions (..., ai_agrees, ai_confidence, ai_reasoning) VALUES
  (..., true, 0.88, 'Strong weekly uptrend confirmed...');
```

---

### Example 5: Low Volume Rejection

**Stock**: WHEELS.NS (Microcap)  
**Date**: 2024-11-13 9:15 AM  
**Price**: ₹145

**Analysis**:
```
RS Rating: 67/99 ✅
RSI: 42 ✅
MACD: Bullish ✅

Volume Analysis:
  Current: 50,000 shares
  20-day avg: 200,000 shares
  Ratio: 0.25 (75% below average) ❌

Score Impact: Volume contributes only 20/100 (10% weight = 2 points)
Total Score: 58/100 ❌
```

**Result**: HOLD (score < 60)

**Reason**: Low volume = weak conviction. Unlikely to move significantly intraday.

---

## Summary: What Makes a Good Entry?

### DAILY Strategy Checklist
- ✅ RS Rating >= 60
- ✅ Technical Score >= 60
- ✅ At least 5/9 indicators show BUY
- ✅ Sufficient capital available
- ✅ No circuit breaker holds

### SWING Strategy Checklist
- ✅ RS Rating >= 65
- ✅ Technical Score >= 65
- ✅ RSI < 70 (not overbought)
- ✅ Preferably 0.5-3% pullback from 5-day high
- ✅ Nifty trend not extremely bearish
- ✅ At least 6/9 indicators show BUY
- ✅ (Optional) AI agrees with >= 70% confidence
- ✅ Sufficient capital available

**Key Insight**: System combines multiple filters to ensure only high-probability setups are traded. Better to miss trades than take bad ones.

---

**Next**: See **04-DAILY-STRATEGY.md** for execution details and position management.

**Last Updated**: 2024-11-13  
**Version**: 2.0
