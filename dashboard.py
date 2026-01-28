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
from scripts.fee_calculator import calculate_position_fees

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
# Session state for trading mode
if 'trading_mode' not in st.session_state:
    st.session_state.trading_mode = 'PAPER'

# Capital allocation (initial)
CAPITAL_INITIAL = {
    "DAILY": 500000,
    "SWING": 500000,
    "THUNDER": 500000
}

CAPITAL_INITIAL_LIVE = {
    "DAILY": 10000,
    "SWING": 0,
    "THUNDER": 0
}

def get_capital_for_mode(trading_mode):
    if trading_mode == "LIVE":
        return CAPITAL_INITIAL_LIVE
    return CAPITAL_INITIAL

def get_live_prices_angelone(tickers):
    """Get live prices from AngelOne for LIVE mode"""
    try:
        sys.path.insert(0, "/home/ubuntu/trading/scripts")
        from angelone_price_fetcher import get_angelone_ltp
        prices = {}
        for ticker in tickers:
            price = get_angelone_ltp(ticker)
            if price:
                prices[ticker] = price
        return prices
    except Exception as e:
        st.warning(f"Could not fetch live prices: {e}")
        return {}

def update_live_pnl(positions_df, trading_mode):
    """Update PNL with live prices for LIVE mode"""
    if positions_df.empty:
        return positions_df
    if "fees" not in positions_df.columns:
        positions_df["fees"] = 0.0
    if "net_pnl" not in positions_df.columns:
        positions_df["net_pnl"] = 0.0
    
    if trading_mode == "LIVE":
        tickers = positions_df["ticker"].tolist()
        live_prices = get_live_prices_angelone(tickers)
        for idx, row in positions_df.iterrows():
            ticker = row["ticker"]
            if ticker in live_prices:
                live_price = float(live_prices[ticker])
                entry_price = float(row["entry_price"])
                quantity = int(row["quantity"])
                positions_df.at[idx, "current_price"] = live_price
                gross_pnl = (live_price - entry_price) * quantity
                positions_df.at[idx, "unrealized_pnl"] = gross_pnl
                fee_info = calculate_position_fees(entry_price, live_price, quantity)
                positions_df.at[idx, "fees"] = fee_info["fees"]
                positions_df.at[idx, "net_pnl"] = fee_info["net_pnl"]
    else:
        for idx, row in positions_df.iterrows():
            entry_price = float(row["entry_price"])
            quantity = int(row["quantity"])
            current_price = row.get("current_price")
            if current_price is None or pd.isna(current_price):
                current_price = entry_price
            else:
                current_price = float(current_price)
            fee_info = calculate_position_fees(entry_price, current_price, quantity)
            positions_df.at[idx, "fees"] = fee_info["fees"]
            positions_df.at[idx, "net_pnl"] = fee_info["net_pnl"]
    return positions_df



# Cache data for 30 seconds
@st.cache_data(ttl=30)
def load_portfolio_summary(trading_mode):
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT
                strategy,
                SUM(CASE WHEN status = 'HOLD' THEN 1 ELSE 0 END) as active_positions,
                SUM(CASE WHEN status = 'HOLD' THEN unrealized_pnl ELSE 0 END) as unrealized_pnl,
                SUM(CASE WHEN status = 'HOLD' THEN entry_price * quantity ELSE 0 END) as invested,
                SUM(CASE WHEN status = 'CLOSED' THEN realized_pnl ELSE 0 END) as realized_pnl
            FROM positions
            WHERE trading_mode = %s
            GROUP BY strategy
        """, (trading_mode,))
        return pd.DataFrame(cur.fetchall())

@st.cache_data(ttl=30)
def load_active_positions(trading_mode):
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT
                ticker, strategy, entry_date, entry_price, current_price,
                quantity, unrealized_pnl, stop_loss, take_profit,
                CURRENT_DATE - entry_date as days_held
            FROM positions
            WHERE status = 'HOLD'
              AND trading_mode = %s
            ORDER BY entry_date DESC
        """, (trading_mode,))
        return pd.DataFrame(cur.fetchall())

@st.cache_data(ttl=30)
def load_recent_trades(trading_mode, days=7):
    with get_db_cursor() as cur:
        cur.execute(f"""
            SELECT
                ticker, strategy, entry_date, exit_date, entry_price,
                current_price as exit_price, quantity, realized_pnl,
                (exit_date - entry_date) as days_held
            FROM positions
            WHERE status = 'CLOSED'
              AND trading_mode = %s
              AND exit_date >= CURRENT_DATE - INTERVAL '{days} days'
            ORDER BY exit_date DESC
            LIMIT 20
        """, (trading_mode,))
        return pd.DataFrame(cur.fetchall())

@st.cache_data(ttl=30)
def load_capital_pnl(trading_mode):
    """Calculate actual P&L from positions table only (single source of truth)"""
    with get_db_cursor() as cur:
        # Get P&L from positions table ONLY (avoid double-counting with trades table)
        cur.execute("""
            SELECT
                strategy,
                SUM(CASE WHEN status = 'CLOSED' AND realized_pnl > 0 THEN realized_pnl ELSE 0 END) as total_profits,
                SUM(CASE WHEN status = 'CLOSED' AND realized_pnl < 0 THEN ABS(realized_pnl) ELSE 0 END) as total_losses,
                SUM(CASE WHEN status = 'HOLD' THEN entry_price * quantity ELSE 0 END) as deployed
            FROM positions
            WHERE strategy IN ('DAILY', 'SWING', 'THUNDER')
              AND trading_mode = %s
            GROUP BY strategy
        """, (trading_mode,))
        result = pd.DataFrame(cur.fetchall())

    if result.empty:
        return pd.DataFrame()

    # Calculate net P&L
    result['net_pnl'] = result['total_profits'] - result['total_losses']

    return result[['strategy', 'total_profits', 'total_losses', 'net_pnl', 'deployed']]

@st.cache_data(ttl=30)
def load_daily_pnl(trading_mode, days=30):
    """Load daily P&L from positions table only (single source of truth)"""
    with get_db_cursor() as cur:
        # Get from positions table ONLY (avoid double-counting with trades table)
        cur.execute(f"""
            SELECT
                exit_date as date,
                SUM(realized_pnl) as daily_pnl
            FROM positions
            WHERE status = 'CLOSED'
              AND trading_mode = %s
              AND exit_date >= CURRENT_DATE - INTERVAL '{days} days'
            GROUP BY exit_date
            ORDER BY exit_date
        """, (trading_mode,))
        result = pd.DataFrame(cur.fetchall())

        return result

@st.cache_data(ttl=30)
def get_capital_available(trading_mode):
    """Calculate available capital for each strategy using get_available_cash"""
    from scripts.db_connection import get_available_cash

    strategies = ['DAILY', 'SWING', 'THUNDER']
    result = []

    for strategy in strategies:
        available = get_available_cash(strategy, trading_mode)
        result.append({'strategy': strategy, 'available': available})

    return pd.DataFrame(result)

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
def get_period_performance(trading_mode, days):
    """Get performance from positions table only (single source of truth)"""
    with get_db_cursor() as cur:
        # Get from positions table ONLY (avoid double-counting with trades table)
        cur.execute(f"""
            SELECT strategy,
                   SUM(CASE WHEN status = 'CLOSED' THEN realized_pnl ELSE 0 END) as pnl,
                   COUNT(CASE WHEN status = 'CLOSED' THEN 1 END) as trades
            FROM positions
            WHERE exit_date >= CURRENT_DATE - INTERVAL '{days} days'
              AND trading_mode = %s
            GROUP BY strategy
        """, (trading_mode,))
        result = pd.DataFrame(cur.fetchall())

        if result.empty:
            result = pd.DataFrame(columns=['strategy', 'pnl', 'trades'])

        return result

# Header
# Trading Mode Toggle
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    st.title("📊 LightRain Trading Dashboard")
with col2:
    mode = st.radio("Mode", options=['PAPER', 'LIVE'], horizontal=True)
    st.session_state.trading_mode = mode
with col3:
    if st.button("🔄 Refresh", key="refresh_top", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

mode_emoji = "📝" if st.session_state.trading_mode == 'PAPER' else "💵"
st.markdown(f"### {mode_emoji} {st.session_state.trading_mode} Mode")

# Auto-refresh every 30 seconds
# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Overview", "💼 Positions", "📜 Trades", "📊 Performance"
])

# TAB 1: Overview
with tab1:
    st.header("Portfolio Overview")

    # Capital summary
    pnl_df = load_capital_pnl(st.session_state.trading_mode)

    if not pnl_df.empty:
        col1, col2, col3, col4 = st.columns(4)

        total_initial = sum(get_capital_for_mode(st.session_state.trading_mode).values())
        total_realized_profits = float(pnl_df['total_profits'].sum())
        total_realized_losses = float(pnl_df['total_losses'].sum())
        total_deployed = float(pnl_df['deployed'].sum()) if not pnl_df.empty else 0
        total_available = total_initial - total_deployed

        # Get active positions and calculate unrealized PNL FIRST
        active_pos = load_active_positions(st.session_state.trading_mode)
        active_pos = update_live_pnl(active_pos, st.session_state.trading_mode)
        total_unrealized = 0
        total_fees = 0
        if not active_pos.empty:
            if "unrealized_pnl" in active_pos.columns:
                total_unrealized = float(active_pos["unrealized_pnl"].fillna(0).sum())
            if "fees" in active_pos.columns:
                total_fees = float(active_pos["fees"].fillna(0).sum())
        
        # Total PNL = realized + unrealized (gross)
        gross_pnl = (total_realized_profits - total_realized_losses) + total_unrealized
        net_pnl = gross_pnl - total_fees

        # Format amounts based on size
        def fmt_amt(val):
            if abs(val) >= 100000:
                return f"₹{val/100000:.1f}L"
            elif abs(val) >= 1000:
                return f"₹{val/1000:.1f}K"
            else:
                return f"₹{val:,.0f}"
        
        with col1:
            st.metric("Total Capital", fmt_amt(total_initial))
        with col2:
            st.metric("Available", fmt_amt(total_available))
        with col3:
            st.metric("Active Positions", len(active_pos))
        with col4:
            st.metric("Deployed", fmt_amt(total_deployed))
        
        # Second row for P&L breakdown
        col5, col6, col7 = st.columns(3)
        with col5:
            gross_color = "normal" if gross_pnl >= 0 else "inverse"
            st.metric("Gross P&L", f"₹{gross_pnl:,.0f}", delta_color=gross_color)
        with col6:
            st.metric("Fees", f"₹{total_fees:,.0f}")
        with col7:
            net_color = "normal" if net_pnl >= 0 else "inverse"
            st.metric("Net P&L", f"₹{net_pnl:,.0f}",
                     delta=f"{(net_pnl/total_initial*100):+.2f}%",
                     delta_color=net_color)

    st.divider()

    # Strategy breakdown
    st.subheader("Strategy Breakdown")
    portfolio = load_portfolio_summary(st.session_state.trading_mode)

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
                    unrealized = row['unrealized_pnl'] if row['unrealized_pnl'] else 0
                    realized = row.get('realized_pnl', 0) if row.get('realized_pnl') else 0
                    color = "🟢" if unrealized >= 0 else "🔴"
                    st.write(f"{color} ₹{unrealized:,.0f} (R: ₹{realized:,.0f})")

        st.divider()

        # Chart: Position count over time (line chart)
        with get_db_cursor() as cur:
            cur.execute("""
                WITH date_series AS (
                    SELECT generate_series(
                        CURRENT_DATE - INTERVAL '30 days',
                        CURRENT_DATE,
                        '1 day'::interval
                    )::date AS date
                ),
                daily_positions AS (
                    SELECT 
                        ds.date,
                        p.strategy,
                        COUNT(DISTINCT p.id) as position_count
                    FROM date_series ds
                    LEFT JOIN positions p ON 
                        p.entry_date <= ds.date AND 
                        (p.exit_date IS NULL OR p.exit_date >= ds.date) AND
                        p.status = 'HOLD' AND
                        p.trading_mode = %s
                    WHERE p.strategy IS NOT NULL
                    GROUP BY ds.date, p.strategy
                    ORDER BY ds.date, p.strategy
                )
                SELECT * FROM daily_positions
            """, (st.session_state.trading_mode,))
            pos_history = pd.DataFrame(cur.fetchall())
        
        if not pos_history.empty:
            # Create line chart
            fig_line = go.Figure()
            
            strategies = ['DAILY', 'SWING', 'THUNDER']
            colors = {'DAILY': '#1f77b4', 'SWING': '#ff7f0e', 'THUNDER': '#2ca02c'}
            
            for strategy in strategies:
                strategy_data = pos_history[pos_history['strategy'] == strategy]
                if not strategy_data.empty:
                    fig_line.add_trace(go.Scatter(
                        x=strategy_data['date'],
                        y=strategy_data['position_count'],
                        mode='lines+markers',
                        name=strategy,
                        line=dict(color=colors[strategy], width=2),
                        marker=dict(size=6)
                    ))
            
            fig_line.update_layout(
                title="Active Positions Over Time (Last 30 Days)",
                xaxis_title="Date",
                yaxis_title="Number of Positions",
                height=350,
                margin=dict(l=20, r=20, t=40, b=20),
                hovermode='x unified'
            )
            st.plotly_chart(fig_line, use_container_width=True)
        
        # Table: Active stocks per strategy today
        st.subheader("Active Positions Today")
        
        active_positions = load_active_positions(st.session_state.trading_mode)
        
        active_positions = update_live_pnl(active_positions, st.session_state.trading_mode)
        if not active_positions.empty:
            for strategy in ['DAILY', 'SWING', 'THUNDER']:
                strategy_pos = active_positions[active_positions['strategy'] == strategy]
                
                if not strategy_pos.empty:
                    with st.expander(f"📊 {strategy} ({len(strategy_pos)} positions)", expanded=True):
                        # Format table
                        display_df = strategy_pos[['ticker', 'entry_date', 'entry_price', 'current_price', 'quantity', 'unrealized_pnl', 'days_held']].copy()
                        display_df['ticker'] = display_df['ticker'].str.replace('.NS', '')
                        display_df.columns = ['Ticker', 'Entry Date', 'Entry ₹', 'Current ₹', 'Qty', 'P&L', 'Days']
                        
                        # Color code P&L
                        st.dataframe(
                            display_df,
                            use_container_width=True,
                            hide_index=True
                        )
        else:
            st.info("No active positions")

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

        period_perf = get_period_performance(st.session_state.trading_mode, selected_days)

        if not period_perf.empty:
            st.write(f"**Performance for last {selected_days} day(s)**")

            # Display as table
            perf_display = period_perf.copy()
            perf_display.columns = ["Strategy", "Realized P&L (₹)", "Closed Trades"]
            perf_display["Realized P&L (₹)"] = perf_display["Realized P&L (₹)"].apply(lambda x: f"₹{x:,.0f}")

            st.dataframe(
                perf_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Strategy": st.column_config.TextColumn("Strategy", width="medium"),
                    "Realized P&L (₹)": st.column_config.TextColumn("Realized P&L", width="medium"),
                    "Closed Trades": st.column_config.NumberColumn("Closed Trades", width="small"),
                }
            )

            # Summary metrics
            col1, col2 = st.columns(2)
            with col1:
                total_period_pnl = period_perf['pnl'].sum()
                st.metric("Total P&L", f"₹{total_period_pnl:,.0f}")
            with col2:
                total_period_trades = period_perf['trades'].sum()
                st.metric("Closed Trades", int(total_period_trades))
        else:
            st.info(f"No closed trades in the last {selected_days} day(s)")

# TAB 2: Active Positions
with tab2:
    st.header("Active Positions")

    positions = load_active_positions(st.session_state.trading_mode)

    positions = update_live_pnl(positions, st.session_state.trading_mode)
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
        positions["fees"] = positions["fees"].apply(lambda x: f"₹{x:.0f}" if x is not None else "N/A")
        positions["net_pnl"] = positions["net_pnl"].apply(lambda x: f"₹{x:,.0f}" if x is not None else "N/A")
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
    trades = load_recent_trades(st.session_state.trading_mode, days)

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

    pnl_df = load_daily_pnl(st.session_state.trading_mode, 30)

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
        portfolio_pnl_df = load_daily_pnl(st.session_state.trading_mode, benchmark_days)

        if not portfolio_pnl_df.empty and pnl_df is not None and not pnl_df.empty:
            total_capital = sum(get_capital_for_mode(st.session_state.trading_mode).values())
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


# Footer
st.divider()
st.caption(f"LightRain Trading | {st.session_state.trading_mode} Mode | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


# ============================================================================
# LIVE PRICE AND FEE FUNCTIONS
# ============================================================================
