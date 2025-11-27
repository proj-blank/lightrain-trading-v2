# Ratcheting Trailing Stop - Proposal & Research

**Date**: 2025-11-27
**Status**: Under Research
**Strategy**: DAILY (intraday)
**Author**: Trading System Analysis

---

## Executive Summary

Proposal to replace **fixed TP/SL** with **ratcheting trailing stops** to:
1. ✅ Lock profits at milestones (prevent giving back gains on reversals)
2. ✅ Let winners run (no artificial cap on upside)
3. ✅ Remove 3-day force exit for profitable positions

**Initial backtest (6 trades):** -25.6% vs current system
**Conclusion:** Sample too small, need 50-100 trades. Revisit in 2-4 weeks.

---

## The Problem

### Issue 1: Fixed TP Caps Upside
**Current:** Exit at +5% TP regardless of momentum
**Problem:** Stock could run to +15%, but we cap at +5%

**Example:**
```
Entry: Rs 100
Hits TP at Rs 105 (+5%) → EXIT
Stock continues to Rs 115 (+15%)
Missed: +10% additional profit
```

### Issue 2: 3-Day Force Exit Wastes Profits
**Current:** Force exit all positions at day 3 (MAX_HOLD)
**Problem:** Profitable positions with momentum are closed arbitrarily

**Example:**
```
Day 1: Entry Rs 100
Day 2: Rs 108 (+8%, strong momentum)
Day 3: Rs 112 (+12%) → FORCE EXIT due to MAX_HOLD
Day 4: Runs to Rs 120 (+20%)
Missed: +8% by closing too early
```

### Issue 3: Trailing Stops Can Erase Gains
**SWING Strategy Problem:** Pure Chandelier trailing gives back profits

**Example:**
```
Entry: Rs 100
Peak: Rs 115 (+15%)
Chandelier trails to Rs 110
Reversal: Rs 110 → EXIT at +10%
Gave back: 5% from peak (could be worse on sharp reversal)
```

---

## Proposed Solution: Ratcheting Trailing Stop

### Concept: Profit Locking + Trailing

Combine the best of both:
- **Lock minimum profit** at milestones (floor that never goes down)
- **Trail above the floor** to catch extended moves
- **Tighten trail** as profit increases (more aggressive)

### Logic Overview

```
Stage 1: Hit +5% profit → Lock +2%, Trail 2.5% below high
Stage 2: Hit +8% profit → Lock +5%, Trail 2.0% below high
Stage 3: Hit +12% profit → Lock +8%, Trail 1.5% below high

Exit when: Current Price ≤ MAX(Locked Floor, Trailing Stop)
```

### Detailed Parameters

| Profit Tier | Locked Floor | Trail % | Description |
|-------------|--------------|---------|-------------|
| 0% - 5%     | Original SL  | 3.0%    | Initial phase, wide trail |
| 5% - 8%     | +2%          | 2.5%    | Lock small profit, moderate trail |
| 8% - 12%    | +5%          | 2.0%    | Lock meaningful profit, tighter trail |
| 12%+        | +8%          | 1.5%    | Lock major profit, aggressive trail |

### Example Walkthrough

**Trade: Entry Rs 100**

| Day | Price | High  | Profit | Locked Floor | Trail Stop | Final Stop | Action |
|-----|-------|-------|--------|--------------|------------|------------|--------|
| 1   | 102   | 102   | +2%    | 97 (SL)      | 98.94      | 98.94      | HOLD   |
| 2   | 106   | 106   | +6%    | 102 (+2%)    | 103.35     | 103.35     | HOLD   |
| 3   | 110   | 110   | +10%   | 105 (+5%)    | 107.80     | 107.80     | HOLD   |
| 4   | 114   | 114   | +14%   | 108 (+8%)    | 112.29     | 112.29     | HOLD   |
| 5   | 112   | 114   | +12%   | 108 (+8%)    | 112.29     | 112.29     | **EXIT** |

**Result:**
- Exit: Rs 112.29 (+12.29%)
- Peak: Rs 114 (+14%)
- Gave back: 1.71% from peak
- **Locked minimum: +8%** (even if crashed, worst case +8%)

---

## Backtest Results (Nov 27, 2025)

### Sample
- **Trades:** 6 (Nov 20-27, 2025)
- **Strategy:** DAILY
- **Timeframe:** 7 days

### Performance Comparison

| Metric | Current (Fixed TP/SL) | Ratcheting Trail | Difference |
|--------|----------------------|------------------|------------|
| Total P&L | ₹6,655 | ₹4,949 | **-₹1,706 (-25.6%)** |
| Avg P&L | ₹1,109 | ₹825 | -₹284 |
| Avg P&L % | 1.03% | 0.82% | -0.21% |
| Win Rate | 50.0% | 50.0% | 0% |
| Better Trades | - | 2 (33.3%) | - |
| Worse Trades | - | 4 (66.7%) | - |

### Individual Trade Analysis

| Ticker | Entry Date | Current P&L | Ratchet P&L | Difference | Notes |
|--------|------------|-------------|-------------|------------|-------|
| SUNPHARMA.NS | Nov 24 | ₹2,117 | ₹2,344 | **+₹227** | Ratchet better |
| HINDALCO.NS | Nov 25 | ₹3,035 | ₹3,504 | **+₹469** | Ratchet better |
| TATASTEEL.NS | Nov 25 | ₹3,334 | ₹2,653 | **-₹681** | Gave back from peak |
| RELIANCE.NS | Nov 20 | -₹115 | -₹1,142 | **-₹1,027** | Hit stop too early |
| SBIN.NS | Nov 20 | -₹1,535 | -₹1,839 | **-₹304** | Hit stop too early |
| HEROMOTOCO.NS | Nov 20 | -₹181 | -₹570 | **-₹390** | Hit stop too early |

### Key Observations

1. **Winners:** Ratcheting gave back profits (TATASTEEL -₹681)
2. **Losers:** Ratcheting hit stops faster (RELIANCE -₹1,027 worse)
3. **Sample size:** Too small (6 trades) for statistical significance
4. **Market conditions:** All trades from 1 week (not diverse)

### Conclusion

⚠️ **INCONCLUSIVE** - Need 50-100 trades minimum for valid backtest

Possible reasons for underperformance:
- Parameters too tight (trail % or profit tiers)
- Small sample bias (unlucky week)
- Fixed TP/SL optimal for this specific market regime

---

## Implementation Details

### Code Location
- **Backtest Script:** `/home/ubuntu/trading/backtest_ratcheting_stop.py`
- **Results:** `/tmp/ratcheting_backtest_results.csv`

### Ratcheting Logic (Python)

```python
def calculate_ratcheting_stop(entry_price, highest_price, stop_loss):
    """
    Calculate ratcheting trailing stop

    Returns: (final_stop, locked_profit_pct, trail_pct)
    """
    # Current profit %
    pnl_pct = ((highest_price - entry_price) / entry_price) * 100

    # Determine tier
    if pnl_pct >= 12:
        locked_pct = 8.0
        trail_pct = 1.5
    elif pnl_pct >= 8:
        locked_pct = 5.0
        trail_pct = 2.0
    elif pnl_pct >= 5:
        locked_pct = 2.0
        trail_pct = 2.5
    else:
        locked_pct = None
        trail_pct = 3.0

    # Calculate floors
    if locked_pct:
        locked_floor = entry_price * (1 + locked_pct / 100)
    else:
        locked_floor = stop_loss

    trailing_stop = highest_price * (1 - trail_pct / 100)

    # Final stop = MAX(locked floor, trailing)
    final_stop = max(locked_floor, trailing_stop)

    return final_stop, locked_pct, trail_pct
```

### Integration Points

**Files to modify:**
1. `monitor_daily.py` - Add ratcheting logic to TP/SL checks
2. `daily_trading_pg.py` - Remove MAX_HOLD force exit for profitable positions
3. `scripts/risk_manager.py` - Add ratcheting stop calculation function

**Database changes:**
- Add `highest_price_reached` column to `positions` table
- Track profit tier transitions for analysis

---

## Parameter Tuning Guide

If ratcheting underperforms, try adjusting:

### Option 1: Wider Trails (Give More Room)
```python
Tier 1 (5%+):  Lock +2%, Trail 3.5% (was 2.5%)
Tier 2 (8%+):  Lock +5%, Trail 3.0% (was 2.0%)
Tier 3 (12%+): Lock +8%, Trail 2.5% (was 1.5%)
```

### Option 2: Higher Profit Tiers (Lock Later)
```python
Tier 1: 7%+ profit  → Lock +3%, Trail 2.5%
Tier 2: 10%+ profit → Lock +6%, Trail 2.0%
Tier 3: 15%+ profit → Lock +10%, Trail 1.5%
```

### Option 3: Fewer Tiers (Simpler)
```python
< 8% profit:  Original SL, Trail 3%
>= 8% profit: Lock +4%, Trail 2%
```

### Option 4: ATR-Based Trail (Like SWING)
```python
Trail Distance = 2.5 * ATR (instead of fixed %)
Adjusts for volatility automatically
```

---

## Next Steps

### Phase 1: Data Collection (2-4 weeks)
- ✅ Backtest script created
- ⏳ Collect 50-100 DAILY trades
- ⏳ Diverse market conditions (up/down/sideways)

### Phase 2: Re-Analysis
- Run backtest on larger sample
- Analyze by:
  - Market regime (BULL/NEUTRAL/CAUTION)
  - Stock category (Large/Mid/Micro cap)
  - Win/loss distribution
- Tune parameters if needed

### Phase 3: Paper Trading (Optional)
- Run both systems in parallel
- Current system: Execute real trades
- Ratcheting: Log hypothetical exits
- Compare for 2-4 weeks

### Phase 4: Decision
If ratcheting shows **consistent 10%+ improvement**:
1. Implement in `monitor_daily.py`
2. Add feature flag for A/B testing
3. Monitor for 1 week
4. Roll out fully if stable

If ratcheting shows **no improvement or worse**:
1. Keep current fixed TP/SL
2. Consider alternatives (partial profit taking, MA-based exits)

---

## Alternative Approaches (If Ratcheting Fails)

### 1. Partial Profit Taking
- Hit +5% TP → Sell 50%, trail remaining 50%
- Guarantees profit, lets half position run

### 2. MA-Based Trailing
- Exit when price crosses below 20 EMA
- Trend-following, no arbitrary %

### 3. Volatility-Adjusted Trail
- Low volatility stocks: 1.5% trail
- High volatility stocks: 3.0% trail
- Based on ATR percentile

### 4. Time-Based TP Adjustment
- Days 1-2: Fixed TP +5%
- Day 3+: If profitable, switch to 2% trail

---

## References & Resources

**Professional Trading Strategies:**
- **Chandelier Stop:** Alexander Elder (used in SWING)
- **Parabolic SAR:** J. Welles Wilder
- **ATR Trailing Stops:** Trend following classic

**Similar Systems:**
- Turtle Traders: ATR-based trailing
- Trend Following Funds: 2-3% trails from highs
- Momentum Strategies: Ratcheting stops at 5%/10%/15% tiers

**Books:**
- "Come Into My Trading Room" - Alexander Elder
- "Way of the Turtle" - Curtis Faith
- "Following the Trend" - Andreas Clenow

---

## Status & Timeline

**Current Status:** 🟡 Research Phase
**Next Review:** Dec 10-15, 2025 (after 50+ trades)
**Decision Date:** Dec 20, 2025 (if data sufficient)

**Contact:** Review with trading team after data collection complete

---

## Appendix: Full Backtest Code

See: `/home/ubuntu/trading/backtest_ratcheting_stop.py`

**Usage:**
```bash
cd ~/trading
python3 backtest_ratcheting_stop.py
```

**Output:**
- Console summary
- Detailed CSV: `/tmp/ratcheting_backtest_results.csv`

---

**Document Version:** 1.0
**Last Updated:** 2025-11-27
**Next Update:** After sufficient data collected (50-100 trades)
