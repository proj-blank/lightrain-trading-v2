-- LightRain Trading System - PostgreSQL Schema
-- Industry-grade database design for scalable trading operations

-- Table 1: Portfolio Positions (Current Holdings)
CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    strategy VARCHAR(10) NOT NULL CHECK (strategy IN ('DAILY', 'SWING')),
    status VARCHAR(10) NOT NULL CHECK (status IN ('HOLD', 'CLOSED')),
    entry_price DECIMAL(12, 2) NOT NULL,
    current_price DECIMAL(12, 2),
    quantity INTEGER NOT NULL,
    stop_loss DECIMAL(12, 2) NOT NULL,
    take_profit DECIMAL(12, 2) NOT NULL,
    category VARCHAR(20) CHECK (category IN ('Large-cap', 'Mid-cap', 'Microcap')),
    entry_date DATE NOT NULL,
    exit_date DATE,
    unrealized_pnl DECIMAL(12, 2),
    realized_pnl DECIMAL(12, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, strategy, status, entry_date)
);

-- Table 2: Trade History (All Executed Trades)
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    trade_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ticker VARCHAR(20) NOT NULL,
    strategy VARCHAR(10) NOT NULL CHECK (strategy IN ('DAILY', 'SWING')),
    signal VARCHAR(10) NOT NULL CHECK (signal IN ('BUY', 'SELL')),
    price DECIMAL(12, 2) NOT NULL,
    quantity INTEGER NOT NULL,
    pnl DECIMAL(12, 2),
    notes TEXT,
    category VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 3: Capital Tracker (Account Balance Management)
CREATE TABLE IF NOT EXISTS capital_tracker (
    id SERIAL PRIMARY KEY,
    strategy VARCHAR(10) NOT NULL CHECK (strategy IN ('DAILY', 'SWING')),
    current_trading_capital DECIMAL(12, 2) NOT NULL,
    total_profits_locked DECIMAL(12, 2) DEFAULT 0,
    total_losses DECIMAL(12, 2) DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(strategy)
);

-- Table 4: Circuit Breaker Holds (User Responses)
CREATE TABLE IF NOT EXISTS circuit_breaker_holds (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    strategy VARCHAR(10) NOT NULL CHECK (strategy IN ('DAILY', 'SWING')),
    alert_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    hold_until TIMESTAMP,
    user_action VARCHAR(20) CHECK (user_action IN ('HOLD', 'EXIT', 'SMART_STOP')),
    loss_pct DECIMAL(5, 2),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 5: Performance Metrics (Daily Snapshots)
CREATE TABLE IF NOT EXISTS performance_metrics (
    id SERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,
    strategy VARCHAR(10) NOT NULL CHECK (strategy IN ('DAILY', 'SWING')),
    total_positions INTEGER,
    total_capital_deployed DECIMAL(12, 2),
    unrealized_pnl DECIMAL(12, 2),
    realized_pnl DECIMAL(12, 2),
    win_rate DECIMAL(5, 2),
    avg_win DECIMAL(12, 2),
    avg_loss DECIMAL(12, 2),
    sharpe_ratio DECIMAL(5, 2),
    max_drawdown DECIMAL(5, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(metric_date, strategy)
);

-- Table 6: RS Rating Cache (Performance Optimization)
CREATE TABLE IF NOT EXISTS rs_cache (
    ticker VARCHAR(20) PRIMARY KEY,
    rs_rating INTEGER CHECK (rs_rating BETWEEN 1 AND 99),
    weighted_return DECIMAL(10, 4),
    return_3m DECIMAL(10, 4),
    return_6m DECIMAL(10, 4),
    return_9m DECIMAL(10, 4),
    return_12m DECIMAL(10, 4),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for Performance
CREATE INDEX idx_positions_ticker ON positions(ticker);
CREATE INDEX idx_positions_strategy ON positions(strategy);
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_trades_ticker ON trades(ticker);
CREATE INDEX idx_trades_date ON trades(trade_date);
CREATE INDEX idx_trades_strategy ON trades(strategy);
CREATE INDEX idx_circuit_breaker_ticker ON circuit_breaker_holds(ticker);
CREATE INDEX idx_performance_date ON performance_metrics(metric_date);
CREATE INDEX idx_rs_cache_rating ON rs_cache(rs_rating);

-- Insert Initial Capital
INSERT INTO capital_tracker (strategy, current_trading_capital, total_profits_locked, total_losses)
VALUES
    ('DAILY', 500000, 0, 0),
    ('SWING', 1000000, 0, 0)
ON CONFLICT (strategy) DO NOTHING;

-- Views for Quick Analytics
CREATE OR REPLACE VIEW v_active_positions AS
SELECT
    ticker, strategy, entry_price, current_price, quantity,
    (current_price - entry_price) * quantity as unrealized_pnl,
    ((current_price - entry_price) / entry_price) * 100 as pnl_pct,
    stop_loss, take_profit, category, entry_date,
    CURRENT_DATE - entry_date as days_held
FROM positions
WHERE status = 'HOLD';

CREATE OR REPLACE VIEW v_trade_summary AS
SELECT
    strategy,
    COUNT(*) as total_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
    ROUND(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)::DECIMAL / COUNT(*) * 100, 2) as win_rate,
    ROUND(AVG(CASE WHEN pnl > 0 THEN pnl END), 2) as avg_win,
    ROUND(AVG(CASE WHEN pnl < 0 THEN pnl END), 2) as avg_loss,
    ROUND(SUM(pnl), 2) as total_pnl
FROM trades
WHERE signal = 'SELL' AND pnl IS NOT NULL
GROUP BY strategy;
