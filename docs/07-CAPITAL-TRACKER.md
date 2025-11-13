# 07 - Capital Tracker

Complete guide to capital flows, profit locking, loss tracking, and cash management.

---

## Table of Contents
1. [Capital Structure](#capital-structure)
2. [Capital Flow](#capital-flow)
3. [Profit Locking](#profit-locking)
4. [Loss Tracking](#loss-tracking)
5. [Cash Management](#cash-management)

---

## Capital Structure

### Total System Capital
```
Total Capital: ₹500,000

Allocation by Category:
- Large-cap:  ₹300,000 (60%)
- Mid-cap:    ₹100,000 (20%)
- Microcap:   ₹100,000 (20%)
```

### Position Limits
```
Large-cap:  Max 6 positions  × ₹50,000 = ₹300,000
Mid-cap:    Max 5 positions  × ₹20,000 = ₹100,000
Microcap:   Max 8 positions  × ₹12,500 = ₹100,000
```

---

## Capital Flow

### Entry Flow
```
1. Check available cash
2. Calculate position size (category + volatility)
3. Deduct from available_cash
4. Record position in database
5. Update capital_tracker table
```

### Exit Flow
```
1. Calculate P&L: (exit_price - entry_price) × quantity
2. Add proceeds to available_cash
3. Update locked_profits or realized_losses
4. Record trade in trades_log table
5. Update capital_tracker
```

### Database Schema
```sql
CREATE TABLE capital_tracker (
    capital_id SERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    snapshot_time TIME NOT NULL,
    total_capital NUMERIC(12,2) NOT NULL,
    available_cash NUMERIC(12,2) NOT NULL,
    invested_capital NUMERIC(12,2) NOT NULL,
    locked_profits NUMERIC(12,2) DEFAULT 0,
    realized_losses NUMERIC(12,2) DEFAULT 0,
    daily_pnl NUMERIC(12,2) DEFAULT 0
);
```

---

## Profit Locking

### Concept
When positions hit take-profit levels, a portion of the profit is locked and added to available cash immediately.

### Locking Mechanism
```python
# Example: Position hits TP1 (+10%)
Entry: 100 shares @ ₹1,000 = ₹100,000
TP1: Sell 30 shares @ ₹1,100 = ₹33,000

Profit locked = (₹1,100 - ₹1,000) × 30 = ₹3,000
Available cash += ₹33,000
Locked profits += ₹3,000
Remaining position: 70 shares
```

### Profit Types
1. **Locked Profits**: Realized gains from partial exits (TP levels)
2. **Unrealized Profits**: Paper gains on open positions
3. **Daily P&L**: Today's change in portfolio value

### Database Updates
```sql
-- On partial exit (TP hit)
UPDATE capital_tracker
SET locked_profits = locked_profits + :profit_amount,
    available_cash = available_cash + :proceeds
WHERE snapshot_date = CURRENT_DATE;
```

---

## Loss Tracking

### Realized Losses
Losses from positions closed below entry price (stop loss hits).

### Loss Recording
```python
# Example: Stop loss hit at -5%
Entry: 100 shares @ ₹1,000 = ₹100,000
Exit: 100 shares @ ₹950 = ₹95,000

Loss = ₹100,000 - ₹95,000 = -₹5,000
Available cash += ₹95,000
Realized losses += ₹5,000
```

### Daily Loss Limit
- **Max daily loss**: ₹10,000 (2% of total capital)
- **Action**: Stop trading for the day if limit hit
- **Reset**: Next trading day

### Circuit Breaker Protection
Prevents realized losses by:
1. Holding positions during temporary drops
2. Allowing recovery time
3. Only exiting on hard stop (-5%) or manual override

---

## Cash Management

### Available Cash Calculation
```sql
SELECT 
    total_capital - invested_capital + locked_profits - realized_losses 
    AS available_cash
FROM capital_tracker
WHERE snapshot_date = CURRENT_DATE
ORDER BY snapshot_time DESC LIMIT 1;
```

### Cash States
1. **Total Capital**: Starting capital (₹500,000)
2. **Invested Capital**: Currently deployed in positions
3. **Available Cash**: Free cash for new positions
4. **Locked Profits**: Realized gains
5. **Realized Losses**: Realized losses

### Cash Flow Formula
```
Available Cash = Total Capital 
                - Invested Capital 
                + Locked Profits 
                - Realized Losses
```

---

## Capital Snapshots

### EOD Snapshot
Taken daily at market close (3:30 PM IST):

```python
{
    'snapshot_date': '2024-11-13',
    'snapshot_time': '15:30:00',
    'total_capital': 500000,
    'available_cash': 150000,
    'invested_capital': 350000,
    'locked_profits': 12000,
    'realized_losses': 8000,
    'daily_pnl': 4000
}
```

### Intraday Updates
Capital tracker updates on:
- Position entry (cash decreases)
- Position exit (cash increases)
- Partial exit (TP levels)
- Stop loss hit (loss recorded)

---

## Profit/Loss Calculation

### Unrealized P&L
```sql
SELECT 
    ticker,
    (current_price - entry_price) * quantity AS unrealized_pnl,
    ((current_price - entry_price) / entry_price * 100) AS pnl_pct
FROM positions
WHERE status = 'HOLD';
```

### Realized P&L
```sql
SELECT 
    SUM(exit_value - entry_value) AS total_realized_pnl
FROM trades_log
WHERE exit_date = CURRENT_DATE;
```

### Total P&L
```
Total P&L = Locked Profits - Realized Losses + Unrealized P&L
```

---

## Category-wise Capital

### Allocation Tracking
```sql
SELECT 
    category,
    SUM(entry_price * quantity) AS invested,
    COUNT(*) AS positions
FROM positions
WHERE status = 'HOLD'
GROUP BY category;
```

### Example Output
```
Category    | Invested  | Positions
------------|-----------|----------
Large-cap   | ₹280,000  | 5
Mid-cap     | ₹85,000   | 4
Microcap    | ₹95,000   | 7
------------|-----------|----------
Total       | ₹460,000  | 16
Available   | ₹40,000   | -
```

---

## Capital Rebalancing

### When to Rebalance
1. Category over/under-allocated by >20%
2. Large profit accumulation in one category
3. Consecutive losses in one category

### Rebalancing Process
```
1. Calculate current allocation per category
2. Compare to target allocation (60/20/20)
3. Adjust position sizing for new entries
4. No forced exits (let positions run)
```

### Example Rebalancing
```
Current State:
- Large-cap: ₹350,000 (70%) → Over-allocated
- Mid-cap: ₹75,000 (15%) → Under-allocated
- Microcap: ₹75,000 (15%) → Under-allocated

Action:
- Pause large-cap entries
- Increase mid-cap allocation temporarily
- Increase microcap allocation temporarily
```

---

## Performance Metrics

### Daily Metrics
```sql
SELECT 
    snapshot_date,
    daily_pnl,
    (daily_pnl / total_capital * 100) AS daily_return_pct,
    locked_profits,
    realized_losses
FROM capital_tracker
ORDER BY snapshot_date DESC
LIMIT 30;
```

### Cumulative Metrics
```sql
SELECT 
    SUM(locked_profits) AS total_profits,
    SUM(realized_losses) AS total_losses,
    SUM(locked_profits) - SUM(realized_losses) AS net_pnl,
    ((SUM(locked_profits) - SUM(realized_losses)) / 500000 * 100) AS roi_pct
FROM capital_tracker
WHERE snapshot_date >= '2024-01-01';
```

---

## Capital Safety Rules

### Rule 1: Never Over-Leverage
- Maximum invested: 90% of total capital
- Always keep 10% cash buffer

### Rule 2: Respect Category Limits
- Large-cap: ≤ ₹320,000 (60% + 10% buffer)
- Mid-cap: ≤ ₹110,000 (20% + 10% buffer)
- Microcap: ≤ ₹110,000 (20% + 10% buffer)

### Rule 3: Stop on Daily Loss
- If daily_pnl < -₹10,000: Stop trading
- Resume next day

### Rule 4: Lock Profits Regularly
- Take 30% profit at TP1
- Take 40% profit at TP2
- Let 30% run (trailing SL)

---

## Telegram Commands

### Capital Queries
- `/cap`: Show current capital breakdown
- `/pnl`: Show total P&L (all positions)
- `/daily`: Show daily positions + P&L
- `/swing`: Show swing positions + P&L

### Example Output (`/cap`)
```
💰 CAPITAL TRACKER

Total Capital:    ₹500,000
Available Cash:   ₹125,000
Invested:         ₹375,000
Locked Profits:   ₹18,500
Realized Losses:  ₹6,200

Net P&L: +₹12,300 (+2.46%)
Daily P&L: +₹4,500 (+0.90%)

Category Allocation:
  Large-cap:  ₹285,000 (57%)
  Mid-cap:    ₹90,000  (18%)
  Microcap:   ₹100,000 (20%)
```

---

## Key Files

### Capital Management
- `scripts/db_connection.py`: Capital CRUD operations
- `eod_summary.py`: End-of-day capital snapshot
- `telegram_bot_listener.py`: Real-time capital queries

### Database Tables
- `capital_tracker`: Daily capital snapshots
- `positions`: Active positions (invested capital)
- `trades_log`: Realized P&L history

---

**Next**: [08-MONITORING-CRON.md](08-MONITORING-CRON.md) - Automation and monitoring setup
