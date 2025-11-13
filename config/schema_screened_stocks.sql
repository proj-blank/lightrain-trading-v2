-- Screened Stocks Table
-- Stores NSE universe (351 stocks) updated daily for trading strategies

CREATE TABLE IF NOT EXISTS screened_stocks (
    ticker VARCHAR(20) PRIMARY KEY,
    category VARCHAR(20) NOT NULL,  -- Large-cap, Mid-cap, Micro-cap
    last_updated DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_category CHECK (category IN ('Large-cap', 'Mid-cap', 'Micro-cap'))
);

-- Index for faster queries by category
CREATE INDEX IF NOT EXISTS idx_screened_category ON screened_stocks(category);
CREATE INDEX IF NOT EXISTS idx_screened_updated ON screened_stocks(last_updated);

-- View: Today's screened stocks
CREATE OR REPLACE VIEW v_todays_screened_stocks AS
SELECT
    ticker,
    category,
    last_updated
FROM screened_stocks
WHERE last_updated = CURRENT_DATE
ORDER BY
    CASE category
        WHEN 'Large-cap' THEN 1
        WHEN 'Mid-cap' THEN 2
        WHEN 'Micro-cap' THEN 3
    END,
    ticker;

-- View: Count by category
CREATE OR REPLACE VIEW v_screened_stats AS
SELECT
    category,
    COUNT(*) as stock_count,
    MAX(last_updated) as last_updated
FROM screened_stocks
GROUP BY category
ORDER BY
    CASE category
        WHEN 'Large-cap' THEN 1
        WHEN 'Mid-cap' THEN 2
        WHEN 'Micro-cap' THEN 3
    END;

COMMENT ON TABLE screened_stocks IS 'NSE universe (351 stocks) for daily/swing strategies to score and trade';
COMMENT ON COLUMN screened_stocks.ticker IS 'Stock symbol with .NS suffix (e.g., RELIANCE.NS)';
COMMENT ON COLUMN screened_stocks.category IS 'Market cap classification from NSE indices';
