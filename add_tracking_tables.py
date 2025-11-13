#!/usr/bin/env python3
"""
Add market regime tracking and portfolio performance tables to PostgreSQL
"""
import sys
sys.path.insert(0, '/home/ubuntu/trading')

from scripts.db_connection import get_db_cursor

print("=" * 70)
print("Adding Market Regime & Performance Tracking Tables")
print("=" * 70)

with get_db_cursor() as cur:
    # 1. Market Regime History Table
    print("\n1. Creating market_regime_history table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS market_regime_history (
            id SERIAL PRIMARY KEY,
            date DATE NOT NULL,
            regime VARCHAR(20) NOT NULL,
            score DECIMAL(10, 2),
            position_sizing_multiplier DECIMAL(5, 2),
            allow_new_entries BOOLEAN,
            sp500_price DECIMAL(12, 2),
            sp500_change_pct DECIMAL(10, 4),
            nasdaq_price DECIMAL(12, 2),
            nasdaq_change_pct DECIMAL(10, 4),
            vix_value DECIMAL(10, 2),
            vix_level VARCHAR(20),
            india_vix_value DECIMAL(10, 2),
            india_vix_level VARCHAR(20),
            nifty_price DECIMAL(12, 2),
            nifty_change_pct DECIMAL(10, 4),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date)
        );
    """)
    print("✅ market_regime_history table created")

    # 2. Daily Portfolio Snapshot Table
    print("\n2. Creating daily_portfolio_snapshot table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_portfolio_snapshot (
            id SERIAL PRIMARY KEY,
            date DATE NOT NULL,
            strategy VARCHAR(10) NOT NULL,
            total_positions INTEGER,
            total_capital_deployed DECIMAL(12, 2),
            available_cash DECIMAL(12, 2),
            unrealized_pnl DECIMAL(12, 2),
            unrealized_pnl_pct DECIMAL(10, 4),
            realized_pnl_today DECIMAL(12, 2),
            realized_pnl_mtd DECIMAL(12, 2),
            total_trading_capital DECIMAL(12, 2),
            total_profits_locked DECIMAL(12, 2),
            total_losses DECIMAL(12, 2),
            market_regime VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, strategy)
        );
    """)
    print("✅ daily_portfolio_snapshot table created")

    # 3. Check existing performance_metrics table
    print("\n3. Checking performance_metrics table...")
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name = 'performance_metrics'
    """)
    exists = cur.fetchone()

    if exists:
        print("✅ performance_metrics table exists")
        # Show its structure
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'performance_metrics'
            ORDER BY ordinal_position
        """)
        print("\n   Columns:")
        for row in cur.fetchall():
            print(f"     - {row['column_name']}: {row['data_type']}")
    else:
        print("⚠️  performance_metrics table not found, creating...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id SERIAL PRIMARY KEY,
                strategy VARCHAR(10) NOT NULL,
                date DATE NOT NULL,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                losing_trades INTEGER DEFAULT 0,
                total_pnl DECIMAL(12, 2) DEFAULT 0,
                win_rate DECIMAL(5, 2),
                avg_win DECIMAL(12, 2),
                avg_loss DECIMAL(12, 2),
                max_drawdown DECIMAL(12, 2),
                sharpe_ratio DECIMAL(10, 4),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(strategy, date)
            );
        """)
        print("✅ performance_metrics table created")

    # 4. Create indexes for faster queries
    print("\n4. Creating indexes...")
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_regime_date ON market_regime_history(date DESC);
        CREATE INDEX IF NOT EXISTS idx_snapshot_date ON daily_portfolio_snapshot(date DESC, strategy);
        CREATE INDEX IF NOT EXISTS idx_performance_date ON performance_metrics(strategy, date DESC);
    """)
    print("✅ Indexes created")

    # 5. Show all tracking tables
    print("\n5. Listing all tracking tables...")
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name IN ('market_regime_history', 'daily_portfolio_snapshot', 'performance_metrics', 'trades')
        ORDER BY table_name
    """)
    print("\n   Available tracking tables:")
    for row in cur.fetchall():
        print(f"     ✓ {row['table_name']}")

print("\n" + "=" * 70)
print("✅ Tracking tables ready!")
print("=" * 70)

print("\nNow you can track:")
print("  📊 Market regime history")
print("  💰 Daily portfolio snapshots")
print("  📈 Performance metrics over time")
print("  💼 All trades (already exists)")
