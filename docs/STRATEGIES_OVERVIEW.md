# LightRain Trading System - Complete Strategy Guide

**Last Updated:** December 14, 2025
**System Status:** Production (Fully Automated)

## Overview

LightRain operates 3 independent trading strategies with different time horizons and methodologies:

| Strategy | Capital | Time Horizon | Selection Method | Max Positions |
|----------|---------|--------------|------------------|---------------|
| **DAILY** | ₹5,00,000 | Intraday | Technical + Screening | Dynamic |
| **SWING** | ₹5,00,000 | 3-7 days | Technical + Screening | Dynamic |
| **THUNDER** | ₹5,00,000 | 25-40 days | Fundamental (Dexter) | 6 |

**Total System Capital:** ₹15,00,000

---

## Strategy 1: DAILY (Intraday Trading)

### Overview
High-frequency intraday trading based on morning screening with SmartEntry candle validation.

### Key Parameters
- **Capital:** ₹5,00,000
- **Position Size:** 2% of available capital per position
- **Stop Loss:** 2% (ATR-based)
- **Take Profit:** 3%
- **Market Hours:** 9:15 AM - 3:30 PM IST
- **Screening Time:** 9:20 AM (5 min after open)

### Entry Criteria
1. **Morning Screening** (9:20 AM):
   - RS (Relative Strength) > 60
   - Volume spike detected
   - Price above key moving averages
   - Momentum indicators positive

2. **SmartEntry Candle Validation**:
   - Bullish pattern (e.g., MARUBOZU, HAMMER)
   - Pattern strength >= 55
   - Support/resistance levels identified
   - Sentiment score positive

3. **Re-entry Logic** (2:00 PM):
   - Regime check (GREEN = bullish, RED = bearish)
   - If GREEN: Re-scan for new opportunities
   - If RED: Skip re-entry, manage existing positions

### Exit Rules
- **Stop Loss:** -2% from entry
- **Take Profit:** +3% from entry
- **EOD Exit:** All positions closed by 3:25 PM
- **Trailing:** Ratcheting stop-loss on +2% gain

### Files
- `daily_trading_pg.py` - Main entry logic
- `monitor_daily.py` - Position monitoring + re-entry
- `daily_screening.py` - Morning screening (9:20 AM)
- `regime_2pm_check.py` - Intraday regime validation

### Automation
```bash
# Morning screening (9:20 AM)
20 9 * * 1-5 python3 daily_screening.py

# Position entry (9:25 AM)
25 9 * * 1-5 python3 daily_trading_pg.py

# Monitoring + re-entry (2:00 PM)
0 14 * * 1-5 python3 monitor_daily.py

# End of day exit (3:25 PM)
25 15 * * 1-5 python3 monitor_daily.py
```

### Performance Targets
- Win Rate: 55-60%
- Risk/Reward: 1:1.5 (2% risk, 3% target)
- Max Drawdown: 10%

---

## Strategy 2: SWING (Multi-Day Swing Trading)

### Overview
3-7 day holding period based on technical analysis and price action patterns.

### Key Parameters
- **Capital:** ₹5,00,000
- **Position Size:** 2% of available capital per position
- **Stop Loss:** 3% (wider than DAILY)
- **Take Profit:** 5% (higher target)
- **Screening Frequency:** Daily (9:20 AM)

### Entry Criteria
1. **Technical Screening**:
   - RS (Relative Strength) > 65 (higher than DAILY)
   - Multi-timeframe confirmation (daily + 4H)
   - Price near support levels
   - Volume accumulation pattern

2. **SmartEntry Validation**:
   - Bullish reversal patterns preferred
   - Pattern strength >= 60
   - Breakout confirmation

3. **Sector Rotation**:
   - Favor sectors in uptrend
   - Avoid over-concentration

### Exit Rules
- **Stop Loss:** -3% from entry
- **Take Profit:** +5% from entry
- **Time-based:** Close if no progress after 7 days
- **Profit Lock:** Move stop to breakeven at +3%

### Files
- `swing_trading_pg.py` - Main entry logic
- `monitor_swing_pg.py` - Position monitoring
- `swing_screening.py` - Daily screening

### Automation
```bash
# Morning screening (9:20 AM)
20 9 * * 1-5 python3 swing_screening.py

# Position entry (9:30 AM)
30 9 * * 1-5 python3 swing_trading_pg.py

# Monitoring (2:30 PM)
30 14 * * 1-5 python3 monitor_swing_pg.py

# End of day check (3:30 PM)
30 15 * * 1-5 python3 monitor_swing_pg.py
```

### Performance Targets
- Win Rate: 60-65%
- Risk/Reward: 1:1.67 (3% risk, 5% target)
- Max Drawdown: 12%

---

## Strategy 3: THUNDER (Earnings-Based Fundamental)

### Overview
Earnings catalyst trading with fundamental analysis (Dexter). Enters 25-40 days before earnings for high-quality stocks only.

### Key Parameters
- **Capital:** ₹5,00,000
- **Max Positions:** 6 total
- **Max Per Stock:** 2 positions
- **Max Per Sector:** 50% (₹2,50,000)
- **Min Dexter Score:** 75/100
- **Earnings Window:** 25-40 days before announcement
- **Profit Target:** 5% (automatic exit)

### Entry Criteria
1. **Earnings Calendar**:
   - Filter stocks with earnings in 25-40 days
   - Prefer large-caps and quality mid-caps

2. **Dexter Fundamental Analysis**:
   ```
   Dexter Score = Weighted Average of:
   - Revenue Growth (25%)
   - Earnings Growth (25%)
   - Operating Margin (15%)
   - Debt/Equity Ratio (15%)
   - ROE (10%)
   - Cash Flow (10%)

   Score >= 75 required for entry
   ```

3. **Sector Allocation**:
   - **CRITICAL:** Max 50% of capital per sector
   - Calculate current deployment from `positions` table
   - **BLOCK sectors at/above 50% limit**
   - If only overallocated sectors available → SKIP entry

4. **Position Sizing**:
   - Quality-based: Higher Dexter score = larger position
   - Range: ₹50K - ₹1.2L per position
   - Confidence multiplier (HIGH/MEDIUM/LOW)

### Exit Rules
- **Profit Target:** +5% automatic exit
- **Post-Earnings:** Hold through earnings, reassess after results
- **No Stop Loss:** High conviction, fundamentals-based

### Sector Allocation Example
```
Current State:
Total Capital: ₹5,00,000
Max Per Sector: ₹2,50,000 (50%)

Deployed:
- Technology: ₹2,67,000 (53%) → BLOCKED ✗
- Banking: ₹0 (0%) → AVAILABLE ✓
- Energy: ₹0 (0%) → AVAILABLE ✓

Action:
- Skip: HCLTECH, WIPRO (Technology sector blocked)
- Enter: HDFCBANK (Banking), RELIANCE (Energy)
```

### Files
- `thunder_pipeline.py` - Main pipeline (earnings scan + Dexter + entry)
- `thunder_entry.py` - Position entry with quality sizing
- `thunder_dexter_analyzer.py` - Fundamental analysis engine
- `thunder_exit.py` - Profit-taking logic
- `monitor_thunder.py` - Position monitoring
- `earnings_calendar.py` - Earnings date management

### Automation
```bash
# Pipeline (10:30 AM) - profit check + new entries
30 10 * * 1-5 python3 thunder_pipeline.py

# Monitoring (3:45 PM)
45 15 * * 1-5 python3 monitor_thunder.py

# Exit check (4:00 PM)
0 16 * * 1-5 python3 thunder_exit.py
```

### Performance Targets
- Win Rate: 70%+
- Avg Gain: 5-8%
- Max Drawdown: 8%
- Holding Period: 30-45 days avg

---

## Database Architecture

### Consolidated Tables (All Strategies)

#### `positions` Table
Primary table for all active positions across all 3 strategies.

```sql
CREATE TABLE positions (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    strategy VARCHAR(20) NOT NULL, -- 'DAILY', 'SWING', or 'THUNDER'
    entry_date DATE NOT NULL,
    entry_price DECIMAL(10,2) NOT NULL,
    quantity INTEGER NOT NULL,
    current_price DECIMAL(10,2),
    unrealized_pnl DECIMAL(15,2),
    stop_loss DECIMAL(10,2),
    take_profit DECIMAL(10,2),
    status VARCHAR(20) DEFAULT 'HOLD', -- 'HOLD' or 'CLOSED'
    category VARCHAR(20), -- 'Large-cap', 'Mid-cap', 'Microcap'
    exit_date DATE,
    realized_pnl DECIMAL(15,2)
);
```

**Strategy Differentiation:**
- DAILY positions: `strategy = 'DAILY'`
- SWING positions: `strategy = 'SWING'`
- THUNDER positions: `strategy = 'THUNDER'`

#### `trades` Table
Historical trades (closed positions) for DAILY and SWING.

```sql
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20),
    strategy VARCHAR(20),
    entry_date DATE,
    exit_date DATE,
    entry_price DECIMAL(10,2),
    exit_price DECIMAL(10,2),
    quantity INTEGER,
    pnl DECIMAL(15,2),
    pnl_percentage DECIMAL(5,2)
);
```

### Capital Calculation (Unified Formula)

```python
def get_available_cash(strategy):
    """
    Calculate available capital for a strategy

    Formula:
    Available = (Initial Capital - Total Losses) - Deployed Capital

    Where:
    - Initial Capital = ₹500,000 per strategy
    - Total Losses = SUM(ABS(realized_pnl)) WHERE realized_pnl < 0
    - Deployed = SUM(entry_price * quantity) WHERE status = 'HOLD'
    """
    INITIAL_CAPITAL = 500000

    # Get total losses from positions + trades
    losses_positions = db.query("""
        SELECT COALESCE(SUM(ABS(realized_pnl)), 0) as losses
        FROM positions
        WHERE strategy = %s AND realized_pnl < 0
    """, (strategy,))

    losses_trades = db.query("""
        SELECT COALESCE(SUM(ABS(pnl)), 0) as losses
        FROM trades
        WHERE strategy = %s AND pnl < 0
    """, (strategy,))

    total_losses = losses_positions + losses_trades

    # Get deployed capital
    deployed = db.query("""
        SELECT COALESCE(SUM(entry_price * quantity), 0) as deployed
        FROM positions
        WHERE strategy = %s AND status = 'HOLD'
    """, (strategy,))

    return (INITIAL_CAPITAL - total_losses) - deployed
```

---

## Monitoring & Dashboard

### Dashboard URL
http://13.235.86.250:8501

### Tabs
1. **Overview** - System-wide P&L across all strategies
2. **DAILY** - Active DAILY positions + recent trades
3. **SWING** - Active SWING positions + recent trades
4. **THUNDER** - Active THUNDER positions + sector allocation
5. **Analysis** - Performance metrics, win rates, drawdowns

### Telegram Bot

Commands:
- `/cap` - Show capital allocation across all strategies
- `/positions` - List all active positions
- `/pnl` - Show today's P&L
- `/stats` - Strategy performance stats

---

## File Structure

```
trading/
├── daily_trading_pg.py          # DAILY entry
├── swing_trading_pg.py          # SWING entry
├── thunder_pipeline.py          # THUNDER main pipeline
├── thunder_entry.py             # THUNDER entry logic
├── thunder_dexter_analyzer.py   # Fundamental analysis
├── monitor_daily.py             # DAILY monitoring
├── monitor_swing_pg.py          # SWING monitoring
├── monitor_thunder.py           # THUNDER monitoring
├── earnings_calendar.py         # Earnings date management
├── scripts/
│   ├── db_connection.py         # Database utilities
│   ├── telegram_bot.py          # Telegram alerts
│   └── smart_entry_validator.py # Candle pattern analysis
├── docs/
│   ├── STRATEGIES_OVERVIEW.md   # This file
│   ├── DAILY_STRATEGY_GUIDE.md
│   ├── SWING_STRATEGY_GUIDE.md
│   └── THUNDER_STRATEGY_GUIDE.md
└── logs/
    ├── daily_trading.log
    ├── swing_trading.log
    └── thunder_pipeline.log
```

---

## Risk Management

### Position Sizing
- **DAILY/SWING:** 2% of available capital per position
- **THUNDER:** Quality-based (₹50K-₹1.2L based on Dexter score)

### Diversification
- **DAILY/SWING:** Max 10 concurrent positions (soft limit)
- **THUNDER:** Max 6 positions, max 2 per stock, max 50% per sector

### Capital Allocation
```
Total: ₹15,00,000

DAILY:    ₹5,00,000 (33%)
SWING:    ₹5,00,000 (33%)
THUNDER:  ₹5,00,000 (33%)
```

### Correlation
- DAILY and SWING may overlap stocks (different timeframes)
- THUNDER typically different stocks (earnings-focused)
- Overall low correlation between strategies

---

## Performance Summary (December 2025)

| Strategy | Trades | Win Rate | Total P&L | ROI |
|----------|--------|----------|-----------|-----|
| DAILY | 142 | 58% | ₹14,106 | +2.82% |
| SWING | 89 | 62% | ₹11,055 | +2.21% |
| THUNDER | 4 | 100% | ₹9,409 | +1.88% |
| **Total** | **235** | **60%** | **₹34,570** | **+2.30%** |

---

## Troubleshooting

### Issue: Capital calculation incorrect
**Solution:** Check `db_connection.py:get_available_cash()` - should query `positions` + `trades` tables, NOT `capital_tracker` (deprecated).

### Issue: THUNDER skipping all entries
**Check:** Are all sectors at 50%+ allocation? This is correct behavior - wait for next day.

### Issue: Position not showing in dashboard
**Check:**
1. Was it inserted into `positions` table with correct `strategy` value?
2. Is `status = 'HOLD'`?
3. Refresh dashboard (auto-refreshes every 30s)

---

## Related Documentation

- [THUNDER Sector Allocation Rules](../THUNDER_SECTOR_ALLOCATION_RULES.txt)
- [Database Consolidation Changes](../CONSOLIDATION_CHANGES_20251212.txt)
- [Dexter Quick Start](DEXTER_QUICK_START.md)
- [Cron Schedule](../CRON_SCHEDULE.md)

---

**System Status:** ✅ All strategies automated and running
**Next Review:** Weekly performance review every Monday
