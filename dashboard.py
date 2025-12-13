#!/usr/bin/env python3
"""
LightRain Trading Dashboard
Mobile-friendly Streamlit app
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import sys
import yfinance as yf

sys.path.insert(0, '/home/ubuntu/trading')
from scripts.db_connection import get_db_cursor

# Page config
st.set_page_config(
    page_title="LightRain Trading",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for mobile
st.markdown("""
<style>
    .main {padding: 1rem;}
    .stMetric {background: #f0f2f6; padding: 1rem; border-radius: 0.5rem;}
    .positive {color: #00c853;}
    .negative {color: #ff1744;}
    @media (max-width: 768px) {
        .main {padding: 0.5rem;}
        h1 {font-size: 1.5rem;}
        h2 {font-size: 1.2rem;}
    }
</style>
""", unsafe_allow_html=True)
# Capital allocation (initial)
CAPITAL_INITIAL = {
    "DAILY": 500000,
    "SWING": 500000,
    "THUNDER": 500000
}


# Cache data for 30 seconds
@st.cache_data(ttl=30)
def load_portfolio_summary():
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT
                strategy,
                SUM(CASE WHEN status = 'HOLD' THEN 1 ELSE 0 END) as active_positions,
                SUM(CASE WHEN status = 'HOLD' THEN unrealized_pnl ELSE 0 END) as unrealized_pnl,
                SUM(CASE WHEN status = 'HOLD' THEN entry_price * quantity ELSE 0 END) as invested
            FROM positions
            GROUP BY strategy
        """)
        return pd.DataFrame(cur.fetchall())

@st.cache_data(ttl=30)
def load_active_positions():
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT
                ticker, strategy, entry_date, entry_price, current_price,
                quantity, unrealized_pnl, stop_loss, take_profit,
                CURRENT_DATE - entry_date as days_held
            FROM positions
            WHERE status = 'HOLD'
            ORDER BY entry_date DESC
        """)
        return pd.DataFrame(cur.fetchall())

@st.cache_data(ttl=30)
def load_recent_trades(days=7):
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT
                ticker, strategy, entry_date, exit_date, entry_price,
                current_price as exit_price, quantity, realized_pnl,
                (exit_date - entry_date) as days_held
            FROM positions
            WHERE status = 'CLOSED'
              AND exit_date >= CURRENT_DATE - INTERVAL '%s days'
            ORDER BY exit_date DESC
            LIMIT 20
        """ % days)
        return pd.DataFrame(cur.fetchall())

@st.cache_data(ttl=30)
def load_capital_pnl():
    """Calculate actual P&L from positions and trades tables"""
    with get_db_cursor() as cur:
        # Get P&L from positions table
        cur.execute("""
            SELECT
                strategy,
                SUM(CASE WHEN realized_pnl > 0 THEN realized_pnl ELSE 0 END) as profits_positions,
                SUM(CASE WHEN realized_pnl < 0 THEN ABS(realized_pnl) ELSE 0 END) as losses_positions,
                SUM(CASE WHEN status = 'HOLD' THEN entry_price * quantity ELSE 0 END) as deployed
            FROM positions
            WHERE strategy IN ('DAILY', 'SWING', 'THUNDER')
            GROUP BY strategy
        """)
        positions_data = pd.DataFrame(cur.fetchall())

        # Get P&L from trades table
        cur.execute("""
            SELECT
                strategy,
                SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) as profits_trades,
                SUM(CASE WHEN pnl < 0 THEN ABS(pnl) ELSE 0 END) as losses_trades
            FROM trades
            WHERE strategy IN ('DAILY', 'SWING')
            GROUP BY strategy
        """)
        trades_data = pd.DataFrame(cur.fetchall())

    # Merge
    if not trades_data.empty and not positions_data.empty:
        combined = pd.merge(positions_data, trades_data, on='strategy', how='outer').fillna(0)
    elif not positions_data.empty:
        combined = positions_data
        combined['profits_trades'] = 0
        combined['losses_trades'] = 0
    elif not trades_data.empty:
        combined = trades_data
        combined['profits_positions'] = 0
        combined['losses_positions'] = 0
        combined['deployed'] = 0
    else:
        return pd.DataFrame()

    # Calculate totals
    combined['total_profits'] = combined['profits_positions'] + combined['profits_trades']
    combined['total_losses'] = combined['losses_positions'] + combined['losses_trades']
    combined['net_pnl'] = combined['total_profits'] - combined['total_losses']

    return combined[['strategy', 'total_profits', 'total_losses', 'net_pnl', 'deployed']]

@st.cache_data(ttl=30)
def load_daily_pnl(days=30):
    """Load daily P&L from both positions and trades tables"""
    with get_db_cursor() as cur:
        # Get from positions table
        cur.execute("""
            SELECT
                exit_date as date,
                SUM(realized_pnl) as daily_pnl
            FROM positions
            WHERE status = 'CLOSED'
              AND exit_date >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY exit_date
        """ % days)
        positions_df = pd.DataFrame(cur.fetchall())
        
        # Get from trades table (historical DAILY/SWING)
        cur.execute("""
            SELECT
                DATE(trade_date) as date,
                SUM(pnl) as daily_pnl
            FROM trades
            WHERE DATE(trade_date) >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY DATE(trade_date)
        """ % days)
        trades_df = pd.DataFrame(cur.fetchall())
        
        # Combine both
        if not positions_df.empty and not trades_df.empty:
            combined = pd.concat([positions_df, trades_df])
            result = combined.groupby('date', as_index=False)['daily_pnl'].sum()
            result = result.sort_values('date')
        elif not positions_df.empty:
            result = positions_df.sort_values('date')
        elif not trades_df.empty:
            result = trades_df.sort_values('date')
        else:
            result = pd.DataFrame()
        
        return result

@st.cache_data(ttl=30)
def load_paper_trades_today():
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT ticker, strategy, stock_pattern, current_price,
                   limit_price, would_enter, reason
            FROM paper_trades
            WHERE trade_date = CURRENT_DATE
            ORDER BY strategy, ticker
        """)
        return pd.DataFrame(cur.fetchall())

@st.cache_data(ttl=30)
def get_capital_available():
    """Calculate available capital for each strategy"""
    INITIAL_CAPITAL = 500000
    with get_db_cursor() as cur:
        # Get deployed and losses for each strategy
        cur.execute("""
            SELECT
                strategy,
                SUM(CASE WHEN status = 'HOLD' THEN entry_price * quantity ELSE 0 END) as deployed,
                SUM(CASE WHEN realized_pnl < 0 THEN ABS(realized_pnl) ELSE 0 END) as losses_positions
            FROM positions
            WHERE strategy IN ('DAILY', 'SWING', 'THUNDER')
            GROUP BY strategy
        """)
        pos_data = pd.DataFrame(cur.fetchall())

        # Get losses from trades table
        cur.execute("""
            SELECT
                strategy,
                SUM(CASE WHEN pnl < 0 THEN ABS(pnl) ELSE 0 END) as losses_trades
            FROM trades
            WHERE strategy IN ('DAILY', 'SWING')
            GROUP BY strategy
        """)
        trade_data = pd.DataFrame(cur.fetchall())

    # Merge
    if not trade_data.empty and not pos_data.empty:
        combined = pd.merge(pos_data, trade_data, on='strategy', how='outer').fillna(0)
    elif not pos_data.empty:
        combined = pos_data
        combined['losses_trades'] = 0
    elif not trade_data.empty:
        combined = trade_data
        combined['deployed'] = 0
        combined['losses_positions'] = 0
    else:
        return pd.DataFrame()

    # Calculate available = (initial - total_losses) - deployed
    combined['total_losses'] = combined['losses_positions'] + combined['losses_trades']
    combined['available'] = INITIAL_CAPITAL - combined['total_losses'] - combined['deployed']

    return combined[['strategy', 'available']]

# Helper functions for new features
@st.cache_data(ttl=300)
def get_benchmark_data(days=30):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    benchmarks = {"Nifty 50": "^NSEI", "Nifty Midcap": "^NSEMDCP50", "S&P Futures": "ES=F", "Nikkei": "^N225", "Gold": "GC=F"}
    result = {}
    for name, ticker in benchmarks.items():
        try:
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if not data.empty:
                returns = float(((data["Close"].iloc[-1] / data["Close"].iloc[0]) - 1) * 100)
                result[name] = {"returns": returns, "data": data["Close"].reset_index()}
        except:
            result[name] = {"returns": 0, "data": pd.DataFrame()}
    return result

@st.cache_data(ttl=30)
def get_period_performance(days):
    """Get performance from both positions and trades tables"""
    with get_db_cursor() as cur:
        # Get from positions table
        cur.execute(f"""
            SELECT strategy, 
                   SUM(CASE WHEN status = 'CLOSED' THEN realized_pnl ELSE 0 END) as pnl,
                   COUNT(CASE WHEN status = 'CLOSED' THEN 1 END) as trades
            FROM positions 
            WHERE exit_date >= CURRENT_DATE - INTERVAL '{days} days'
            GROUP BY strategy
        """)
        positions_perf = pd.DataFrame(cur.fetchall())
        
        # Get from trades table (for historical DAILY/SWING)
        cur.execute(f"""
            SELECT strategy,
                   SUM(pnl) as pnl,
                   COUNT(*) as trades
            FROM trades
            WHERE trade_date >= CURRENT_DATE - INTERVAL '{days} days'
            GROUP BY strategy
        """)
        trades_perf = pd.DataFrame(cur.fetchall())
        
        # Combine both
        if not positions_perf.empty and not trades_perf.empty:
            combined = pd.concat([positions_perf, trades_perf])
            result = combined.groupby('strategy', as_index=False).agg({'pnl': 'sum', 'trades': 'sum'})
        elif not positions_perf.empty:
            result = positions_perf
        elif not trades_perf.empty:
            result = trades_perf
        else:
            result = pd.DataFrame(columns=['strategy', 'pnl', 'trades'])
        
        return result

# Header
st.title("📊 LightRain Trading Dashboard")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Auto-refresh every 30 seconds
if st.button("🔄 Refresh", key="refresh_top"):
    st.cache_data.clear()
    st.rerun()

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Overview", "💼 Positions", "📜 Trades", "📊 Performance", "📄 Paper Trades"
])

# TAB 1: Overview
with tab1:
    st.header("Portfolio Overview")

    # Capital summary
    pnl_df = load_capital_pnl()

    if not pnl_df.empty:
        col1, col2, col3, col4 = st.columns(4)

        total_initial = sum(CAPITAL_INITIAL.values())
        total_profits = pnl_df['total_profits'].sum()
        total_losses = pnl_df['total_losses'].sum()
        total_deployed = pnl_df['deployed'].sum() if not pnl_df.empty else 0
        total_available = (1500000 - total_losses - total_deployed)

        with col1:
            st.metric("Total Capital", f"₹{total_initial/100000:.1f}L")
        with col2:
            st.metric("Available", f"₹{total_available/100000:.1f}L")
        with col3:
            pnl_color = "normal" if total_profits - total_losses >= 0 else "inverse"
            st.metric("Total P&L", f"₹{(total_profits - total_losses):,.0f}",
                     delta=f"{((total_profits - total_losses)/total_initial*100):+.2f}%",
                     delta_color=pnl_color)
        with col4:
            active_pos = load_active_positions()
            st.metric("Active Positions", len(active_pos))

    st.divider()

    # Strategy breakdown
    st.subheader("Strategy Breakdown")
    portfolio = load_portfolio_summary()

    if not portfolio.empty:
        for _, row in portfolio.iterrows():
            with st.container():
                col1, col2, col3, col4 = st.columns([2,2,2,2])
                with col1:
                    st.write(f"**{row['strategy']}**")
                with col2:
                    st.write(f"{row['active_positions']} positions")
                with col3:
                    st.write(f"₹{row['invested']/100000:.2f}L invested")
                with col4:
                    pnl = row['unrealized_pnl'] if row['unrealized_pnl'] else 0
                    color = "🟢" if pnl >= 0 else "🔴"
                    st.write(f"{color} ₹{pnl:,.0f}")

        st.divider()

        # Chart: Capital allocation
        fig = go.Figure(data=[
            go.Pie(
                labels=pnl_df['strategy'],
                values=list(CAPITAL_INITIAL.values()),
                hole=0.4,
                marker=dict(colors=['#1f77b4', '#ff7f0e', '#2ca02c'])
            )
        ])
        fig.update_layout(
            title="Capital Allocation",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # NEW FEATURE: Performance by Time Period
        st.subheader("Performance by Time Period")

        col1, col2 = st.columns([2, 1])
        with col1:
            period_option = st.selectbox(
                "Select Period",
                ["Today (1 day)", "Week (7 days)", "Month (30 days)", "Custom"],
                key="period_selector"
            )

        with col2:
            if period_option == "Custom":
                custom_days = st.number_input("Number of Days", min_value=1, max_value=365, value=7, key="custom_days")
                selected_days = custom_days
            else:
                selected_days = {"Today (1 day)": 1, "Week (7 days)": 7, "Month (30 days)": 30}.get(period_option, 7)

        period_perf = get_period_performance(selected_days)

        if not period_perf.empty:
            st.write(f"**Performance for last {selected_days} day(s)**")

            # Display as table
            perf_display = period_perf.copy()
            perf_display.columns = ["Strategy", "P&L (₹)", "Trades"]
            perf_display["P&L (₹)"] = perf_display["P&L (₹)"].apply(lambda x: f"₹{x:,.0f}")

            st.dataframe(
                perf_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Strategy": st.column_config.TextColumn("Strategy", width="medium"),
                    "P&L (₹)": st.column_config.TextColumn("P&L", width="medium"),
                    "Trades": st.column_config.NumberColumn("Trades", width="small"),
                }
            )

            # Summary metrics
            col1, col2 = st.columns(2)
            with col1:
                total_period_pnl = period_perf['pnl'].sum()
                st.metric("Total P&L", f"₹{total_period_pnl:,.0f}")
            with col2:
                total_period_trades = period_perf['trades'].sum()
                st.metric("Total Trades", int(total_period_trades))
        else:
            st.info(f"No closed trades in the last {selected_days} day(s)")

# TAB 2: Active Positions
with tab2:
    st.header("Active Positions")

    positions = load_active_positions()

    if positions.empty:
        st.info("No active positions")
    else:
        # Strategy filter
        strategies = ['All'] + list(positions['strategy'].unique())
        selected_strategy = st.selectbox("Filter by strategy", strategies)

        if selected_strategy != 'All':
            positions = positions[positions['strategy'] == selected_strategy]

        # Format and display
        positions["entry_price"] = positions["entry_price"].apply(lambda x: f"₹{x:.2f}" if x is not None else "N/A")
        positions["current_price"] = positions["current_price"].apply(lambda x: f"₹{x:.2f}" if x is not None else "N/A")
        positions["unrealized_pnl"] = positions["unrealized_pnl"].apply(lambda x: f"₹{x:,.0f}" if x is not None else "N/A")
        positions["stop_loss"] = positions["stop_loss"].apply(lambda x: f"₹{x:.2f}" if x is not None else "N/A")
        positions["take_profit"] = positions["take_profit"].apply(lambda x: f"₹{x:.2f}" if x is not None else "N/A")

        st.dataframe(
            positions,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ticker": st.column_config.TextColumn("Ticker", width="small"),
                "strategy": st.column_config.TextColumn("Strategy", width="small"),
                "entry_date": st.column_config.DateColumn("Entry Date"),
                "days_held": st.column_config.NumberColumn("Days", width="small"),
                "unrealized_pnl": st.column_config.TextColumn("P&L"),
            }
        )

# TAB 3: Recent Trades
with tab3:
    st.header("Recent Trades")

    days = st.slider("Days to show", 1, 30, 7)
    trades = load_recent_trades(days)

    if trades.empty:
        st.info("No trades in selected period")
    else:
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)

        total_trades = len(trades)
        winners = trades[trades['realized_pnl'] > 0]
        losers = trades[trades['realized_pnl'] <= 0]

        with col1:
            st.metric("Total Trades", total_trades)
        with col2:
            win_rate = len(winners) / total_trades * 100 if total_trades > 0 else 0
            st.metric("Win Rate", f"{win_rate:.1f}%")
        with col3:
            total_pnl = trades['realized_pnl'].sum()
            st.metric("Total P&L", f"₹{total_pnl:,.0f}")
        with col4:
            avg_pnl = trades['realized_pnl'].mean()
            st.metric("Avg P&L", f"₹{avg_pnl:,.0f}")

        st.divider()

        # Trades table
        trades['realized_pnl'] = trades['realized_pnl'].apply(
            lambda x: f"₹{x:,.0f}" if pd.notna(x) else "N/A"
        )

        st.dataframe(
            trades,
            use_container_width=True,
            hide_index=True
        )

# TAB 4: Performance
with tab4:
    st.header("Performance Charts")

    pnl_df = load_daily_pnl(30)

    if not pnl_df.empty:
        # Cumulative P&L
        pnl_df['cumulative_pnl'] = pnl_df['daily_pnl'].cumsum()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=pnl_df['date'],
            y=pnl_df['cumulative_pnl'],
            mode='lines+markers',
            name='Cumulative P&L',
            line=dict(color='#1f77b4', width=2),
            fill='tozeroy'
        ))

        fig.update_layout(
            title="Cumulative P&L (Last 30 Days)",
            xaxis_title="Date",
            xaxis=dict(type="date"),
            yaxis_title="P&L (₹)",
            height=400,
            hovermode='x unified'
        )

        st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # Daily P&L bar chart
        fig2 = go.Figure()
        colors = ['#00c853' if x >= 0 else '#ff1744' for x in pnl_df['daily_pnl']]

        fig2.add_trace(go.Bar(
            x=pnl_df['date'],
            y=pnl_df['daily_pnl'],
            marker_color=colors,
            name='Daily P&L'
        ))

        fig2.update_layout(
            title="Daily P&L",
            xaxis=dict(type="date"),
            xaxis_title="Date",
            yaxis_title="P&L (₹)",
            height=300,
            showlegend=False
        )

        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No P&L data available for the selected period")

    st.divider()

    # NEW FEATURE: Benchmark Comparison
    st.subheader("Benchmark Comparison")

    benchmark_days = st.slider("Select Period (Days)", min_value=7, max_value=90, value=30, key="benchmark_slider")

    with st.spinner("Loading benchmark data..."):
        benchmark_data = get_benchmark_data(benchmark_days)

        # Display returns summary
        st.write(f"**Returns Comparison (Last {benchmark_days} days)**")

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            nifty_return = benchmark_data.get("Nifty 50", {}).get("returns", 0)
            st.metric("Nifty 50", f"{nifty_return:.2f}%")

        with col2:
            midcap_return = benchmark_data.get("Nifty Midcap", {}).get("returns", 0)
            st.metric("Nifty Midcap", f"{midcap_return:.2f}%")

        with col3:
            sp_return = benchmark_data.get("S&P Futures", {}).get("returns", 0)
            st.metric("S&P Futures", f"{sp_return:.2f}%")

        with col4:
            nikkei_return = benchmark_data.get("Nikkei", {}).get("returns", 0)
            st.metric("Nikkei", f"{nikkei_return:.2f}%")

        with col5:
            gold_return = benchmark_data.get("Gold", {}).get("returns", 0)
            st.metric("Gold", f"{gold_return:.2f}%")

        # Calculate portfolio returns for comparison
        portfolio_pnl_df = load_daily_pnl(benchmark_days)

        if not portfolio_pnl_df.empty and pnl_df is not None and not pnl_df.empty:
            total_capital = sum(CAPITAL_INITIAL.values())
            total_pnl_period = portfolio_pnl_df['daily_pnl'].sum()
            portfolio_return = (total_pnl_period / total_capital) * 100

            st.metric("Portfolio Return", f"{portfolio_return:.2f}%")

            # Create comparison chart
            fig_benchmark = go.Figure()

            # Add portfolio line (always visible)
            if not portfolio_pnl_df.empty:
                portfolio_pnl_df['cumulative_return'] = (portfolio_pnl_df['daily_pnl'].cumsum() / total_capital) * 100
                fig_benchmark.add_trace(go.Scatter(
                    x=portfolio_pnl_df['date'],
                    y=portfolio_pnl_df['cumulative_return'],
                    mode='lines',
                    name='Portfolio',
                    line=dict(color='#1f77b4', width=3),
                    visible=True
                ))

            # Add benchmark lines (hidden by default)
            colors = ['#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
            for idx, (name, data) in enumerate(benchmark_data.items()):
                if not data["data"].empty:
                    # Calculate cumulative returns from start
                    benchmark_df = data["data"].copy()
                    benchmark_df.columns = ['Date', 'Close']
                    first_close = benchmark_df['Close'].iloc[0]
                    benchmark_df['returns'] = ((benchmark_df['Close'] / first_close) - 1) * 100

                    fig_benchmark.add_trace(go.Scatter(
                        x=benchmark_df['Date'],
                        y=benchmark_df['returns'],
                        mode='lines',
                        name=name,
                        line=dict(color=colors[idx % len(colors)], width=2),
                        visible='legendonly'  # Hidden by default
                    ))

            fig_benchmark.update_layout(
            xaxis=dict(type="date"),
                title="Portfolio vs Benchmarks - Returns Over Time",
                xaxis_title="Date",
                yaxis_title="Returns (%)",
                height=500,
                hovermode='x unified',
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )

            st.plotly_chart(fig_benchmark, use_container_width=True)
            st.caption("Click on legend items to show/hide benchmark lines. Portfolio line is always visible.")
        else:
            st.info("Insufficient portfolio data for comparison chart")

# TAB 5: Paper Trades
with tab5:
    st.header("Paper Trades (Smart Entry)")

    paper = load_paper_trades_today()

    if paper.empty:
        st.info("No paper trades logged today. Check back after 9:30 AM.")
    else:
        st.subheader("What Smart Entry Would Do Today")

        # Summary
        total_paper = len(paper)
        would_enter = paper[paper['would_enter'] == True]
        would_skip = paper[paper['would_enter'] == False]

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Analyzed", total_paper)
        with col2:
            st.metric("Would Enter", len(would_enter))
        with col3:
            st.metric("Would Skip", len(would_skip))

        st.divider()

        # Show entries
        if not would_enter.empty:
            st.subheader("✅ Would Enter")
            st.dataframe(
                would_enter[['ticker', 'strategy', 'stock_pattern', 'current_price', 'limit_price', 'reason']],
                use_container_width=True,
                hide_index=True
            )

        if not would_skip.empty:
            st.subheader("❌ Would Skip")
            st.dataframe(
                would_skip[['ticker', 'strategy', 'stock_pattern', 'reason']],
                use_container_width=True,
                hide_index=True
            )

# Footer
st.divider()
st.caption("LightRain Trading System | Auto-refresh every 30s")
