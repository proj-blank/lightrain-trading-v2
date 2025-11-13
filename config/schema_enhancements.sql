-- Enhancement: Stock Evaluation Metrics Table
-- Stores all factors used in stock selection decision

CREATE TABLE IF NOT EXISTS stock_evaluations (
    id SERIAL PRIMARY KEY,
    evaluation_date DATE NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    strategy VARCHAR(10) NOT NULL CHECK (strategy IN ('DAILY', 'SWING')),

    -- Price & Volume
    current_price DECIMAL(12, 2) NOT NULL,
    volume BIGINT,
    avg_volume_20d BIGINT,

    -- Technical Indicators
    rsi_14 DECIMAL(5, 2),
    macd DECIMAL(10, 4),
    macd_signal DECIMAL(10, 4),
    bb_position DECIMAL(5, 2),  -- Position within Bollinger Bands (0-1)
    atr DECIMAL(10, 2),

    -- Relative Strength
    rs_rating INTEGER,  -- IBD-style 1-99
    rs_3m DECIMAL(10, 2),
    rs_6m DECIMAL(10, 2),
    rs_12m DECIMAL(10, 2),

    -- Signal Scores
    technical_score INTEGER,  -- Your combined indicator score
    sentiment_score DECIMAL(5, 2),  -- -1 to +1
    fundamental_score INTEGER,  -- 0-100 (future)
    final_score DECIMAL(10, 2),  -- Weighted combination

    -- Market Regime
    market_regime VARCHAR(20),  -- NORMAL, HIGH_VOL, BEAR
    nifty_trend VARCHAR(10),  -- UP, DOWN, SIDEWAYS
    vix_level DECIMAL(10, 2),
    nifty_5d_change DECIMAL(5, 2),  -- % change

    -- News & Sentiment
    has_negative_news BOOLEAN DEFAULT FALSE,
    has_positive_news BOOLEAN DEFAULT FALSE,
    news_summary TEXT,

    -- Decision
    signal VARCHAR(10),  -- BUY, SKIP, HOLD
    decision_reason TEXT,  -- Why bought or skipped
    was_executed BOOLEAN DEFAULT FALSE,

    -- Position Sizing (if executed)
    recommended_quantity INTEGER,
    recommended_allocation DECIMAL(12, 2),
    sentiment_boost_applied DECIMAL(5, 2),  -- % allocation boost

    -- Stock Category
    category VARCHAR(20),
    sector VARCHAR(50),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_evaluation UNIQUE (evaluation_date, ticker, strategy)
);

-- Indexes for fast queries
CREATE INDEX idx_evaluations_date ON stock_evaluations(evaluation_date);
CREATE INDEX idx_evaluations_ticker ON stock_evaluations(ticker);
CREATE INDEX idx_evaluations_strategy ON stock_evaluations(strategy);
CREATE INDEX idx_evaluations_signal ON stock_evaluations(signal);
CREATE INDEX idx_evaluations_executed ON stock_evaluations(was_executed);
CREATE INDEX idx_evaluations_score ON stock_evaluations(final_score);

-- View: Today's Buy Signals
CREATE OR REPLACE VIEW todays_buy_signals AS
SELECT
    ticker,
    strategy,
    final_score,
    rs_rating,
    technical_score,
    sentiment_score,
    market_regime,
    signal,
    decision_reason,
    was_executed
FROM stock_evaluations
WHERE evaluation_date = CURRENT_DATE
  AND signal = 'BUY'
ORDER BY final_score DESC;

-- View: Performance Analysis by Market Regime
CREATE OR REPLACE VIEW regime_performance AS
SELECT
    e.market_regime,
    COUNT(*) as total_evaluations,
    SUM(CASE WHEN e.signal = 'BUY' THEN 1 ELSE 0 END) as buy_signals,
    SUM(CASE WHEN e.was_executed THEN 1 ELSE 0 END) as executed_trades,
    AVG(e.final_score) as avg_score,
    AVG(e.sentiment_score) as avg_sentiment,
    AVG(e.rs_rating) as avg_rs
FROM stock_evaluations e
GROUP BY e.market_regime;

-- View: Stock Performance Tracking
CREATE OR REPLACE VIEW stock_signal_performance AS
SELECT
    e.ticker,
    e.evaluation_date,
    e.signal,
    e.final_score,
    e.current_price as entry_price,
    t.price as exit_price,
    t.pnl,
    CASE
        WHEN t.pnl > 0 THEN 'WIN'
        WHEN t.pnl < 0 THEN 'LOSS'
        ELSE 'PENDING'
    END as outcome
FROM stock_evaluations e
LEFT JOIN trades t ON e.ticker = t.ticker
    AND e.strategy = t.strategy
    AND DATE(t.trade_date) >= e.evaluation_date
    AND t.signal = 'SELL'
WHERE e.was_executed = TRUE
ORDER BY e.evaluation_date DESC;

COMMENT ON TABLE stock_evaluations IS 'Stores all factors evaluated during stock selection process for analysis and improvement';
COMMENT ON COLUMN stock_evaluations.sentiment_score IS 'Sentiment score from -1 (very negative) to +1 (very positive)';
COMMENT ON COLUMN stock_evaluations.market_regime IS 'Market condition: NORMAL, HIGH_VOL (VIX>25), or BEAR (NIFTY down >5% in 5d)';
COMMENT ON COLUMN stock_evaluations.decision_reason IS 'Human-readable explanation of why stock was bought or skipped';
