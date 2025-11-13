-- Global Market Indicators Table
-- Captures overnight/pre-market sentiment from global markets

CREATE TABLE IF NOT EXISTS global_market_indicators (
    id SERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    snapshot_time TIME NOT NULL,

    -- US Market Data (from previous session or futures)
    sp500_close DECIMAL(10, 2),
    sp500_change_pct DECIMAL(5, 2),
    nasdaq_close DECIMAL(10, 2),
    nasdaq_change_pct DECIMAL(5, 2),
    dow_close DECIMAL(10, 2),
    dow_change_pct DECIMAL(5, 2),
    vix_close DECIMAL(10, 2),
    vix_change_pct DECIMAL(5, 2),

    -- US Futures (Pre-market, if available)
    sp500_futures DECIMAL(10, 2),
    sp500_futures_change_pct DECIMAL(5, 2),
    nasdaq_futures DECIMAL(10, 2),
    nasdaq_futures_change_pct DECIMAL(5, 2),

    -- Asian Markets
    nikkei_close DECIMAL(10, 2),
    nikkei_change_pct DECIMAL(5, 2),
    hang_seng_close DECIMAL(10, 2),
    hang_seng_change_pct DECIMAL(5, 2),
    shanghai_close DECIMAL(10, 2),
    shanghai_change_pct DECIMAL(5, 2),

    -- SGX Nifty (Singapore Nifty Futures - Most Important!)
    sgx_nifty DECIMAL(10, 2),
    sgx_nifty_change_pct DECIMAL(5, 2),
    sgx_vs_nifty_premium DECIMAL(5, 2),  -- Gap indicator

    -- India Market (Previous close)
    nifty_prev_close DECIMAL(10, 2),
    nifty_change_pct DECIMAL(5, 2),
    india_vix DECIMAL(10, 2),
    india_vix_change_pct DECIMAL(5, 2),

    -- Derived Sentiment Indicators
    global_sentiment VARCHAR(20),  -- BULLISH, NEUTRAL, BEARISH
    overnight_gap_expected DECIMAL(5, 2),  -- Expected NIFTY gap %
    us_asia_divergence BOOLEAN,  -- US up but Asia down (or vice versa)
    risk_on_off VARCHAR(10),  -- RISK_ON, RISK_OFF

    -- Weekend Effect
    is_monday BOOLEAN DEFAULT FALSE,
    days_since_last_check INTEGER,

    -- FII/DII Flow (if available)
    fii_net_flow DECIMAL(12, 2),  -- Crores
    dii_net_flow DECIMAL(12, 2),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_snapshot UNIQUE (snapshot_date, snapshot_time)
);

-- Indexes
CREATE INDEX idx_global_date ON global_market_indicators(snapshot_date);
CREATE INDEX idx_global_sentiment ON global_market_indicators(global_sentiment);

-- View: Latest Global Sentiment
CREATE OR REPLACE VIEW latest_global_sentiment AS
SELECT *
FROM global_market_indicators
WHERE snapshot_date = CURRENT_DATE
ORDER BY snapshot_time DESC
LIMIT 1;

-- View: Pre-Market Signal Strength
CREATE OR REPLACE VIEW premarket_signal AS
SELECT
    snapshot_date,
    global_sentiment,
    overnight_gap_expected,
    sgx_nifty_change_pct,
    sp500_futures_change_pct,
    nikkei_change_pct,
    hang_seng_change_pct,
    CASE
        WHEN overnight_gap_expected > 1.0 AND global_sentiment = 'BULLISH' THEN 'STRONG_BUY_SIGNAL'
        WHEN overnight_gap_expected > 0.5 AND global_sentiment = 'BULLISH' THEN 'MODERATE_BUY_SIGNAL'
        WHEN overnight_gap_expected < -1.0 AND global_sentiment = 'BEARISH' THEN 'STRONG_CAUTION'
        WHEN overnight_gap_expected < -0.5 AND global_sentiment = 'BEARISH' THEN 'MODERATE_CAUTION'
        ELSE 'NEUTRAL'
    END as trading_bias
FROM global_market_indicators
WHERE snapshot_date = CURRENT_DATE
  AND snapshot_time = (
      SELECT MAX(snapshot_time)
      FROM global_market_indicators
      WHERE snapshot_date = CURRENT_DATE
  );

-- Historical Overnight Performance
CREATE OR REPLACE VIEW overnight_accuracy AS
SELECT
    g.snapshot_date,
    g.overnight_gap_expected as predicted_gap,
    g.global_sentiment as predicted_sentiment,
    (n.nifty_open - g.nifty_prev_close) / g.nifty_prev_close * 100 as actual_gap,
    CASE
        WHEN g.overnight_gap_expected > 0 AND (n.nifty_open - g.nifty_prev_close) > 0 THEN 'CORRECT'
        WHEN g.overnight_gap_expected < 0 AND (n.nifty_open - g.nifty_prev_close) < 0 THEN 'CORRECT'
        ELSE 'WRONG'
    END as prediction_accuracy
FROM global_market_indicators g
LEFT JOIN (
    SELECT
        DATE(created_at) as date,
        MIN(current_price) as nifty_open  -- First price of day
    FROM stock_evaluations
    WHERE ticker = '^NSEI'
    GROUP BY DATE(created_at)
) n ON n.date = g.snapshot_date
WHERE g.snapshot_time >= '08:30:00'  -- Morning pre-market checks only
ORDER BY g.snapshot_date DESC;

COMMENT ON TABLE global_market_indicators IS 'Tracks global market sentiment overnight to predict India market opening gaps';
COMMENT ON COLUMN global_market_indicators.sgx_nifty IS 'Singapore Nifty futures - best predictor of NSE opening';
COMMENT ON COLUMN global_market_indicators.overnight_gap_expected IS 'Expected gap in NIFTY at 9:15 AM open based on global cues';
