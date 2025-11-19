# LightRain Trading System - Database Schema

**Last Updated**: 2024-11-19
**Purpose**: PostgreSQL database tables, columns, relationships, and common queries

---

## Table of Contents
1. [Database Connection](#database-connection)
2. [Core Tables](#core-tables)
3. [Tracking Tables](#tracking-tables)
4. [Support Tables](#support-tables)
5. [Common Queries](#common-queries)
6. [Database Functions](#database-functions)

---

## 1. Database Connection

### Connection Details
- **Database**: `lightrain`
- **Host**: `lightrain.crj4y7ulwktj.ap-south-1.rds.amazonaws.com` (AWS RDS Mumbai)
- **Port**: `5432`
- **User**: `brosshack`
- **SSL**: Required (AWS RDS)

### Python Connection (via db_connection.py)
```python
from scripts.db_connection import get_db_cursor, get_db_connection

# Using cursor (returns dict results)
with get_db_cursor() as cur:
    cur.execute("SELECT * FROM positions WHERE status = 'HOLD'")
    positions = cur.fetchall()

# Using connection (for transactions)
with get_db_connection() as conn:
    cur = conn.cursor()
    cur.execute("UPDATE capital_tracker SET ...")
    conn.commit()
```

### Direct psql Connection
```bash
# From AWS server
psql -h lightrain.crj4y7ulwktj.ap-south-1.rds.amazonaws.com \
     -U brosshack \
     -d lightrain

# Quick query
psql -h $DB_HOST -U $DB_USER -d lightrain -c "SELECT COUNT(*) FROM positions"
```

---

## 2. Core Tables

### 2.1 `positions` - Active and Historical Positions

**Purpose**: Tracks all trading positions (open and closed)

```sql
CREATE TABLE positions (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    strategy VARCHAR(10) NOT NULL CHECK (strategy IN ('DAILY', 'SWING')),
    status VARCHAR(10) NOT NULL CHECK (status IN ('HOLD', 'CLOSED')),
    entry_price DECIMAL(12, 2) NOT NULL,
    current_price DECIMAL(12, 2),
    quantity INTEGER NOT NULL,
    stop_loss DECIMAL(12, 2) NOT NULL,
    take_profit DECIMAL(12, 2) NOT NULL,
    highest_price DECIMAL(12, 2),
    category VARCHAR(20),  -- 'Large-cap', 'Mid-cap', 'Microcap'
    entry_date DATE NOT NULL,
    exit_date DATE,
    unrealized_pnl DECIMAL(12, 2) DEFAULT 0,
    realized_pnl DECIMAL(12, 2),
    days_held INTEGER DEFAULT 0,
    ai_agrees BOOLEAN,
    ai_confidence DECIMAL(5, 2),
    ai_reasoning TEXT,
    ai_analyzed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT unique_active_position UNIQUE (ticker, strategy, status) 
        WHERE status = 'HOLD'
);

-- Indexes for performance
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_strategy ON positions(strategy, status);
CREATE INDEX idx_positions_entry_date ON positions(entry_date DESC);
CREATE INDEX idx_positions_ticker ON positions(ticker);
```

**Key Columns Explained**:
- `ticker`: Stock symbol (e.g., 'RELIANCE.NS')
- `strategy`: Either 'DAILY' or 'SWING'
- `status`: 'HOLD' (active) or 'CLOSED' (exited)
- `entry_price`: Price when position opened
- `current_price`: Latest market price (updated every 5 min)
- `unrealized_pnl`: Current profit/loss (for HOLD positions)
- `realized_pnl`: Final profit/loss (when CLOSED)
- `highest_price`: Tracks highest price reached (for trailing stops)
- `ai_*`: AI validation data (SWING strategy only)

**Example Queries**:

```sql
-- Get all active positions
SELECT * FROM positions WHERE status = 'HOLD' ORDER BY entry_date DESC;

-- Get DAILY strategy positions only
SELECT * FROM positions 
WHERE status = 'HOLD' AND strategy = 'DAILY';

-- Calculate unrealized P&L for all positions
SELECT ticker, strategy, 
       entry_price, current_price,
       (current_price - entry_price) * quantity as unrealized_pnl,
       ((current_price - entry_price) / entry_price) * 100 as pnl_pct
FROM positions
WHERE status = 'HOLD';

-- Get positions approaching TP
SELECT ticker, entry_price, current_price, take_profit,
       ((take_profit - current_price) / current_price) * 100 as distance_to_tp_pct
FROM positions
WHERE status = 'HOLD'
  AND current_price >= (take_profit * 0.95)  -- Within 5% of TP
ORDER BY distance_to_tp_pct;

-- Get today's closed positions
SELECT ticker, strategy, entry_price, current_price, realized_pnl
FROM positions
WHERE status = 'CLOSED' 
  AND exit_date = CURRENT_DATE;

-- Count positions by category
SELECT category, strategy, COUNT(*) as count,
       SUM(unrealized_pnl) as total_unrealized_pnl
FROM positions
WHERE status = 'HOLD'
GROUP BY category, strategy;
```

---

### 2.2 `capital_tracker` - Capital Management

**Purpose**: Tracks available capital, locked profits, and losses per strategy

```sql
CREATE TABLE capital_tracker (
    id SERIAL PRIMARY KEY,
    strategy VARCHAR(10) UNIQUE NOT NULL CHECK (strategy IN ('DAILY', 'SWING')),
    current_trading_capital DECIMAL(15, 2) NOT NULL DEFAULT 0,
    total_profits_locked DECIMAL(15, 2) DEFAULT 0,
    total_losses DECIMAL(15, 2) DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure capital never goes negative
    CONSTRAINT positive_capital CHECK (current_trading_capital >= 0)
);

-- Initialize with starting capital
INSERT INTO capital_tracker (strategy, current_trading_capital) VALUES
    ('DAILY', 1300000.00),  -- ₹13 Lakh
    ('SWING', 1000000.00);  -- ₹10 Lakh
```

**Key Columns Explained**:
- `current_trading_capital`: Cash available for new trades
- `total_profits_locked`: Cumulative profits (withdrawn from trading pool)
- `total_losses`: Cumulative losses (already deducted)

**Capital Flow Logic**:
```python
# Entry: Debit capital
investment = entry_price * quantity
current_trading_capital -= investment

# Exit (Profit): Credit investment + lock profit
current_trading_capital += investment
total_profits_locked += profit

# Exit (Loss): Credit remaining + record loss
current_trading_capital += (investment - loss)
total_losses += loss
```

**Example Queries**:

```sql
-- Get capital status for all strategies
SELECT strategy,
       current_trading_capital,
       total_profits_locked,
       total_losses,
       (current_trading_capital + total_profits_locked - total_losses) as net_capital
FROM capital_tracker;

-- Calculate deployed capital (in positions)
SELECT ct.strategy,
       ct.current_trading_capital as available,
       COALESCE(SUM(p.entry_price * p.quantity), 0) as deployed,
       (ct.current_trading_capital + COALESCE(SUM(p.entry_price * p.quantity), 0)) as total_capital
FROM capital_tracker ct
LEFT JOIN positions p ON p.strategy = ct.strategy AND p.status = 'HOLD'
GROUP BY ct.strategy, ct.current_trading_capital;

-- Check if enough capital for new trade
SELECT strategy, current_trading_capital
FROM capital_tracker
WHERE strategy = 'DAILY'
  AND current_trading_capital >= 50000;  -- Required investment

-- Update capital after profit
UPDATE capital_tracker
SET total_profits_locked = total_profits_locked + 10000,
    current_trading_capital = current_trading_capital + 50000,  -- Return investment
    last_updated = CURRENT_TIMESTAMP
WHERE strategy = 'DAILY';
```

---

### 2.3 `trades` - Trade Audit Log

**Purpose**: Immutable log of all trade executions (BUY/SELL)

```sql
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    strategy VARCHAR(10) NOT NULL,
    signal VARCHAR(10) NOT NULL CHECK (signal IN ('BUY', 'SELL')),
    price DECIMAL(12, 2) NOT NULL,
    quantity INTEGER NOT NULL,
    pnl DECIMAL(12, 2),
    category VARCHAR(20),
    notes TEXT,
    trade_date DATE DEFAULT CURRENT_DATE,
    trade_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trades_date ON trades(trade_date DESC);
CREATE INDEX idx_trades_strategy ON trades(strategy, trade_date DESC);
CREATE INDEX idx_trades_ticker ON trades(ticker);
```

**Key Columns Explained**:
- `signal`: 'BUY' (entry) or 'SELL' (exit)
- `pnl`: Profit/loss (NULL for BUY, populated for SELL)
- `notes`: Reason for trade (e.g., "TP Hit @ ₹520", "SL Hit", "MAX-HOLD")

**Example Queries**:

```sql
-- Get today's trades
SELECT * FROM trades 
WHERE trade_date = CURRENT_DATE 
ORDER BY trade_time DESC;

-- Calculate today's P&L by strategy
SELECT strategy,
       COUNT(*) FILTER (WHERE signal = 'SELL') as exits,
       SUM(pnl) FILTER (WHERE signal = 'SELL') as total_pnl
FROM trades
WHERE trade_date = CURRENT_DATE
GROUP BY strategy;

-- Get all trades for a specific ticker
SELECT trade_date, signal, price, quantity, pnl, notes
FROM trades
WHERE ticker = 'RELIANCE.NS'
ORDER BY trade_time DESC;

-- Win rate calculation (last 30 days)
SELECT strategy,
       COUNT(*) FILTER (WHERE signal = 'SELL') as total_exits,
       COUNT(*) FILTER (WHERE signal = 'SELL' AND pnl > 0) as wins,
       COUNT(*) FILTER (WHERE signal = 'SELL' AND pnl <= 0) as losses,
       ROUND(
           COUNT(*) FILTER (WHERE signal = 'SELL' AND pnl > 0)::NUMERIC / 
           NULLIF(COUNT(*) FILTER (WHERE signal = 'SELL'), 0) * 100, 
           2
       ) as win_rate_pct
FROM trades
WHERE trade_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY strategy;

-- Average P&L per trade
SELECT strategy,
       COUNT(*) FILTER (WHERE signal = 'SELL') as trades,
       AVG(pnl) FILTER (WHERE signal = 'SELL') as avg_pnl,
       AVG(pnl) FILTER (WHERE signal = 'SELL' AND pnl > 0) as avg_win,
       AVG(pnl) FILTER (WHERE signal = 'SELL' AND pnl < 0) as avg_loss
FROM trades
WHERE trade_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY strategy;
```

---

## 3. Tracking Tables

### 3.1 `eod_history` - Daily Portfolio Snapshots

**Purpose**: End-of-day portfolio state for historical tracking

```sql
CREATE TABLE eod_history (
    id SERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    strategy VARCHAR(10) NOT NULL,
    total_positions INTEGER DEFAULT 0,
    total_capital_deployed DECIMAL(15, 2) DEFAULT 0,
    unrealized_pnl DECIMAL(15, 2) DEFAULT 0,
    realized_pnl_today DECIMAL(15, 2) DEFAULT 0,
    available_cash DECIMAL(15, 2) DEFAULT 0,
    total_profits_locked DECIMAL(15, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(snapshot_date, strategy)
);

CREATE INDEX idx_eod_date ON eod_history(snapshot_date DESC);
```

**Example Queries**:

```sql
-- Get last 7 days portfolio snapshots
SELECT snapshot_date, strategy, 
       total_positions, unrealized_pnl, realized_pnl_today
FROM eod_history
WHERE snapshot_date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY snapshot_date DESC, strategy;

-- Track capital growth over time
SELECT snapshot_date,
       (available_cash + total_capital_deployed + total_profits_locked) as total_capital
FROM eod_history
WHERE strategy = 'DAILY'
ORDER BY snapshot_date;

-- Best/worst days
SELECT snapshot_date, strategy, realized_pnl_today
FROM eod_history
WHERE snapshot_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY realized_pnl_today DESC
LIMIT 10;
```

---

### 3.2 `circuit_breaker_holds` - User Overrides

**Purpose**: Track positions where user overrode circuit breaker alerts

```sql
CREATE TABLE circuit_breaker_holds (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    strategy VARCHAR(10) NOT NULL,
    user_action VARCHAR(20) NOT NULL,  -- 'HOLD', 'EXIT', 'EXTEND'
    loss_pct DECIMAL(5, 2),
    hold_until TIMESTAMP,
    notes TEXT,
    alert_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

### 3.3 `screened_stocks` - Stock Universe

**Purpose**: Daily list of stocks to analyze

```sql
CREATE TABLE screened_stocks (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) UNIQUE NOT NULL,
    category VARCHAR(20) NOT NULL,  -- 'Large-cap', 'Mid-cap', 'Microcap'
    last_updated DATE DEFAULT CURRENT_DATE
);

CREATE INDEX idx_screened_updated ON screened_stocks(last_updated);
```

**Example Queries**:

```sql
-- Get today's universe
SELECT category, COUNT(*) 
FROM screened_stocks 
WHERE last_updated = CURRENT_DATE 
GROUP BY category;

-- Get all large-cap stocks for today
SELECT ticker FROM screened_stocks
WHERE category = 'Large-cap'
  AND last_updated = CURRENT_DATE;
```

---

### 3.4 `rs_cache` - Relative Strength Cache

**Purpose**: Cache RS ratings to avoid recalculation

```sql
CREATE TABLE rs_cache (
    ticker VARCHAR(20) PRIMARY KEY,
    rs_rating INTEGER CHECK (rs_rating BETWEEN 1 AND 99),
    weighted_return DECIMAL(10, 4),
    return_3m DECIMAL(10, 4),
    return_6m DECIMAL(10, 4),
    return_9m DECIMAL(10, 4),
    return_12m DECIMAL(10, 4),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rs_rating ON rs_cache(rs_rating DESC);
```

**Example Queries**:

```sql
-- Get top 20 stocks by RS rating
SELECT ticker, rs_rating, weighted_return
FROM rs_cache
WHERE last_updated > CURRENT_TIMESTAMP - INTERVAL '24 hours'
ORDER BY rs_rating DESC
LIMIT 20;

-- Get RS rating for specific stock
SELECT rs_rating FROM rs_cache
WHERE ticker = 'RELIANCE.NS'
  AND last_updated > CURRENT_TIMESTAMP - INTERVAL '24 hours';
```

---

### 3.5 `market_regime_history` - Global Market Regime Tracking

**Purpose**: Historical log of daily 8:30 AM global market regime checks with detailed indicator weights

**Last Updated**: 2024-11-19 (Added indicator price/change columns)

```sql
CREATE TABLE market_regime_history (
    id SERIAL PRIMARY KEY,
    check_date DATE UNIQUE NOT NULL,
    regime VARCHAR(20) NOT NULL,  -- 'BULL', 'NEUTRAL', 'CAUTION', 'BEAR'
    score NUMERIC(5, 2) NOT NULL,
    position_sizing_multiplier NUMERIC(3, 2),
    allow_new_entries BOOLEAN DEFAULT TRUE,

    -- S&P Futures (35% weight)
    sp_futures_price NUMERIC(10, 2),
    sp_futures_change_pct NUMERIC(5, 2),

    -- Nikkei 225 (25% weight)
    nikkei_price NUMERIC(10, 2),
    nikkei_change_pct NUMERIC(5, 2),

    -- Hang Seng (20% weight)
    hang_seng_price NUMERIC(10, 2),
    hang_seng_change_pct NUMERIC(5, 2),

    -- Gold - inverse indicator (10% weight)
    gold_price NUMERIC(10, 2),
    gold_change_pct NUMERIC(5, 2),

    -- VIX - volatility (10% weight)
    vix_value NUMERIC(5, 2),

    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_regime_date ON market_regime_history(check_date DESC);
CREATE INDEX idx_regime_score ON market_regime_history(score DESC);
```

**Key Columns Explained**:
- `regime`: Current market regime classification
- `score`: Composite score from all indicators (-10 to +10 range)
- `position_sizing_multiplier`: How much to scale position sizes (0.5 = 50%, 1.0 = 100%)
- `allow_new_entries`: FALSE when regime is BEAR (score ≤ -3)
- `sp_futures_price/change_pct`: S&P 500 futures closing price and daily change
- `nikkei_price/change_pct`: Nikkei 225 closing price and daily change
- `hang_seng_price/change_pct`: Hang Seng closing price and daily change
- `gold_price/change_pct`: Gold futures closing price and daily change (inverse indicator)
- `vix_value`: VIX closing value (volatility index)

**Regime Scoring Thresholds**:
```
Score >= 4:  BULL      (Position sizing: 100%, New entries: Yes)
Score 1-4:   NEUTRAL   (Position sizing: 75%, New entries: Yes)
Score -2-1:  CAUTION   (Position sizing: 50%, New entries: Yes)
Score <= -3: BEAR      (Position sizing: 0%, New entries: HALT)
```

**Weight Distribution**:
- S&P Futures: 35% (±2 points max)
- Nikkei 225: 25% (±2 points max)
- Hang Seng: 20% (±1.5 points max)
- Gold (inverse): 10% (±2 points max)
- VIX: 10% (±3 points max)

**Example Queries**:

```sql
-- Get last 7 days regime history
SELECT check_date, regime, score,
       sp_futures_change_pct, nikkei_change_pct,
       hang_seng_change_pct, vix_value
FROM market_regime_history
WHERE check_date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY check_date DESC;

-- Track regime changes over time
SELECT check_date, regime, score,
       LAG(regime) OVER (ORDER BY check_date) as prev_regime,
       LAG(score) OVER (ORDER BY check_date) as prev_score,
       score - LAG(score) OVER (ORDER BY check_date) as score_change
FROM market_regime_history
WHERE check_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY check_date DESC;

-- Get today's regime for trading decisions
SELECT regime, score, allow_new_entries, position_sizing_multiplier
FROM market_regime_history
WHERE check_date = CURRENT_DATE;

-- Count days in each regime (last 60 days)
SELECT regime, COUNT(*) as days,
       ROUND(AVG(score), 2) as avg_score
FROM market_regime_history
WHERE check_date >= CURRENT_DATE - INTERVAL '60 days'
GROUP BY regime
ORDER BY days DESC;

-- Identify volatile periods (VIX > 25)
SELECT check_date, regime, score, vix_value,
       sp_futures_change_pct, nikkei_change_pct
FROM market_regime_history
WHERE vix_value > 25
  AND check_date >= CURRENT_DATE - INTERVAL '90 days'
ORDER BY vix_value DESC;

-- Track indicator contributions
SELECT check_date,
       sp_futures_change_pct as sp_chg,
       nikkei_change_pct as nikkei_chg,
       hang_seng_change_pct as hs_chg,
       gold_change_pct as gold_chg,
       vix_value,
       score
FROM market_regime_history
WHERE check_date >= CURRENT_DATE - INTERVAL '14 days'
ORDER BY check_date DESC;
```

**Data Population**:
- Populated by `global_market_filter.py` at 8:30 AM IST daily
- Uses `save_to_database()` method in GlobalMarketFilter class
- One record per day (enforced by UNIQUE constraint on check_date)
- `/gc` Telegram command does NOT save to this table (live query only)

---

## 4. Support Tables

### 4.1 `performance_metrics` - Strategy Performance

```sql
CREATE TABLE performance_metrics (
    id SERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,
    strategy VARCHAR(10) NOT NULL,
    total_positions INTEGER DEFAULT 0,
    total_capital_deployed DECIMAL(12, 2),
    unrealized_pnl DECIMAL(12, 2),
    realized_pnl DECIMAL(12, 2),
    win_rate DECIMAL(5, 2),
    avg_win DECIMAL(12, 2),
    avg_loss DECIMAL(12, 2),
    sharpe_ratio DECIMAL(10, 4),
    max_drawdown DECIMAL(12, 2),
    
    UNIQUE(metric_date, strategy)
);
```

---

## 5. Common Queries

### Portfolio Overview

```sql
-- Complete portfolio status
SELECT 
    p.strategy,
    COUNT(*) as positions,
    SUM(p.entry_price * p.quantity) as capital_deployed,
    SUM(p.unrealized_pnl) as unrealized_pnl,
    ROUND(AVG(((p.current_price - p.entry_price) / p.entry_price) * 100), 2) as avg_pnl_pct
FROM positions p
WHERE p.status = 'HOLD'
GROUP BY p.strategy;
```

### Daily Performance

```sql
-- Today's performance summary
WITH today_exits AS (
    SELECT strategy,
           COUNT(*) as exits,
           SUM(pnl) as total_pnl,
           COUNT(*) FILTER (WHERE pnl > 0) as wins,
           COUNT(*) FILTER (WHERE pnl <= 0) as losses
    FROM trades
    WHERE trade_date = CURRENT_DATE AND signal = 'SELL'
    GROUP BY strategy
),
today_entries AS (
    SELECT strategy, COUNT(*) as entries
    FROM trades
    WHERE trade_date = CURRENT_DATE AND signal = 'BUY'
    GROUP BY strategy
)
SELECT 
    COALESCE(e.strategy, x.strategy) as strategy,
    COALESCE(e.entries, 0) as entries,
    COALESCE(x.exits, 0) as exits,
    COALESCE(x.total_pnl, 0) as realized_pnl,
    COALESCE(x.wins, 0) as wins,
    COALESCE(x.losses, 0) as losses
FROM today_entries e
FULL OUTER JOIN today_exits x ON e.strategy = x.strategy;
```

### Position Health Check

```sql
-- Positions approaching TP or SL
SELECT ticker, strategy,
       entry_price, current_price,
       stop_loss, take_profit,
       ROUND(((current_price - stop_loss) / current_price) * 100, 2) as distance_to_sl_pct,
       ROUND(((take_profit - current_price) / current_price) * 100, 2) as distance_to_tp_pct,
       CASE 
           WHEN current_price <= stop_loss * 1.02 THEN 'NEAR SL'
           WHEN current_price >= take_profit * 0.98 THEN 'NEAR TP'
           ELSE 'OK'
       END as status
FROM positions
WHERE status = 'HOLD';
```

### Capital Allocation

```sql
-- Capital allocation by category
SELECT 
    p.category,
    COUNT(*) as positions,
    SUM(p.entry_price * p.quantity) as deployed,
    ROUND(
        SUM(p.entry_price * p.quantity) / 
        (SELECT SUM(entry_price * quantity) FROM positions WHERE status = 'HOLD') * 100,
        2
    ) as allocation_pct
FROM positions p
WHERE p.status = 'HOLD'
GROUP BY p.category;
```

---

## 6. Database Functions (from db_connection.py)

### Position Management

```python
# Get active positions
positions = get_active_positions(strategy='DAILY')

# Add new position
position_id = add_position(
    ticker='RELIANCE.NS',
    strategy='DAILY',
    entry_price=2450.00,
    quantity=20,
    stop_loss=2352.00,
    take_profit=2573.00,
    category='Large-cap'
)

# Update current price
update_position_price('RELIANCE.NS', 'DAILY', 2480.00)

# Close position
close_position('RELIANCE.NS', 'DAILY', exit_price=2500.00, realized_pnl=1000.00)
```

### Capital Management

```python
# Get capital info
capital = get_capital('DAILY')
# Returns: {'current_trading_capital': 1300000, 'total_profits_locked': 50000, ...}

# Debit capital (on entry)
debit_capital('DAILY', amount=50000)

# Credit capital (on exit)
credit_capital('DAILY', amount=50000)

# Update capital with P&L
update_capital('DAILY', pnl=5000)  # Positive = profit, Negative = loss
```

### Trade Logging

```python
# Log a trade
trade_id = log_trade(
    ticker='RELIANCE.NS',
    strategy='DAILY',
    signal='BUY',
    price=2450.00,
    quantity=20,
    notes='Entry signal score: 75/100'
)

# Get today's trades
trades = get_today_trades(strategy='DAILY')
```

### Query Functions

```python
# Get available cash
cash = get_available_cash('DAILY')

# Get specific position
position = get_position('RELIANCE.NS', 'DAILY')

# Check circuit breaker hold
is_hold = is_position_on_hold('RELIANCE.NS', 'DAILY')
```

---

## Database Maintenance

### Backup
```bash
# Full backup
pg_dump -h $DB_HOST -U $DB_USER lightrain > backup_$(date +%Y%m%d).sql

# Positions only
pg_dump -h $DB_HOST -U $DB_USER -t positions lightrain > positions_backup.sql
```

### Restore
```bash
psql -h $DB_HOST -U $DB_USER lightrain < backup_20241113.sql
```

### Clean Old Data
```sql
-- Archive closed positions older than 1 year
DELETE FROM positions 
WHERE status = 'CLOSED' 
  AND exit_date < CURRENT_DATE - INTERVAL '1 year';

-- Clean old RS cache
DELETE FROM rs_cache 
WHERE last_updated < CURRENT_TIMESTAMP - INTERVAL '7 days';
```

---

**Next**: See **03-SCREENING-SCORING.md** for how stocks are selected and scored.

**Last Updated**: 2024-11-13  
**Version**: 2.0
