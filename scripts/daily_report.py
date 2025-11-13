# scripts/daily_report.py
"""
Generate daily trading report with:
- Portfolio summary
- Open positions with P&L
- Today's signals
- Performance metrics
"""

import pandas as pd
import os
from datetime import datetime
from scripts.risk_manager import calculate_position_metrics
from scripts.data_loader import load_data


def generate_daily_report(portfolio_path="data/portfolio.csv",
                         trades_path="data/trades.csv",
                         results_path="data/results.csv"):
    """Generate comprehensive daily trading report."""

    report = []
    report.append("=" * 70)
    report.append(f"📊 MICROCAP INDIA - DAILY TRADING REPORT")
    report.append(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 70)

    # 1. Portfolio Summary
    if os.path.exists(portfolio_path):
        portfolio = pd.read_csv(portfolio_path)
        stock_data = load_data()

        if not portfolio.empty and 'HOLD' in portfolio['Status'].values:
            metrics = calculate_position_metrics(portfolio, stock_data)

            report.append(f"\n💼 PORTFOLIO SUMMARY")
            report.append("-" * 70)
            report.append(f"Active Positions: {metrics['total_positions']}")
            report.append(f"Total Exposure: ₹{metrics['total_exposure']:,.2f}")
            report.append(f"Unrealized P&L: ₹{metrics['total_unrealized_pnl']:,.2f}")

            if metrics['total_exposure'] > 0:
                pnl_pct = (metrics['total_unrealized_pnl'] / metrics['total_exposure']) * 100
                report.append(f"Portfolio Return: {pnl_pct:+.2f}%")

            # Position details
            report.append(f"\n📈 OPEN POSITIONS:")
            report.append("-" * 70)

            for pos in metrics['positions']:
                status_emoji = "🟢" if pos['pnl'] > 0 else "🔴" if pos['pnl'] < 0 else "⚪"
                report.append(
                    f"{status_emoji} {pos['ticker']:15} | "
                    f"Qty: {pos['qty']:>4} | "
                    f"Entry: ₹{pos['entry']:>8.2f} | "
                    f"Current: ₹{pos['current']:>8.2f} | "
                    f"P&L: ₹{pos['pnl']:>8.2f} ({pos['pnl_pct']:+.2f}%)"
                )
        else:
            report.append(f"\n💼 PORTFOLIO SUMMARY")
            report.append("-" * 70)
            report.append("No active positions")

    # 2. Recent Trades
    if os.path.exists(trades_path):
        trades = pd.read_csv(trades_path)

        if not trades.empty:
            # Get today's trades
            today = datetime.now().strftime("%Y-%m-%d")
            today_trades = trades[trades['Date'] == today]

            if not today_trades.empty:
                report.append(f"\n📝 TODAY'S TRADES:")
                report.append("-" * 70)

                for _, trade in today_trades.iterrows():
                    signal_emoji = "🟢" if trade['Signal'] == 'BUY' else "🔴"
                    pnl_str = f"P&L: ₹{trade['PnL']:,.2f}" if pd.notna(trade['PnL']) else ""

                    report.append(
                        f"{signal_emoji} {trade['Signal']:4} | "
                        f"{trade['Ticker']:15} | "
                        f"Price: ₹{trade['Price']:>8.2f} | "
                        f"Qty: {trade['Quantity']:>4} | "
                        f"{pnl_str}"
                    )
            else:
                report.append(f"\n📝 TODAY'S TRADES:")
                report.append("-" * 70)
                report.append("No trades today")

            # Last 5 trades
            report.append(f"\n📜 RECENT TRADE HISTORY (Last 5):")
            report.append("-" * 70)

            for _, trade in trades.tail(5).iterrows():
                signal_emoji = "🟢" if trade['Signal'] == 'BUY' else "🔴"
                pnl_str = f"| P&L: ₹{trade['PnL']:,.2f}" if pd.notna(trade['PnL']) else ""

                report.append(
                    f"{trade['Date']} | {signal_emoji} {trade['Signal']:4} | "
                    f"{trade['Ticker']:15} | ₹{trade['Price']:>8.2f} {pnl_str}"
                )

    # 3. Performance Metrics
    if os.path.exists(results_path):
        results = pd.read_csv(results_path)

        if not results.empty:
            latest = results.iloc[-1]

            report.append(f"\n📊 PERFORMANCE METRICS:")
            report.append("-" * 70)

            # Portfolio performance
            portfolio_return = latest.get('PortfolioCumRet', 0) * 100 if 'PortfolioCumRet' in latest else 0
            benchmark_return = latest.get('BenchmarkCumRet', 0) * 100 if 'BenchmarkCumRet' in latest else 0

            report.append(f"Portfolio Cumulative Return: {portfolio_return:+.2f}%")
            report.append(f"Benchmark (NIFTY) Return: {benchmark_return:+.2f}%")
            report.append(f"Alpha (Outperformance): {portfolio_return - benchmark_return:+.2f}%")

    # 4. Trade Statistics
    if os.path.exists(trades_path):
        trades = pd.read_csv(trades_path)

        if not trades.empty:
            # Calculate win rate
            completed_trades = trades[trades['PnL'].notna()]

            if not completed_trades.empty:
                wins = len(completed_trades[completed_trades['PnL'] > 0])
                losses = len(completed_trades[completed_trades['PnL'] < 0])
                total = len(completed_trades)
                win_rate = (wins / total * 100) if total > 0 else 0

                avg_win = completed_trades[completed_trades['PnL'] > 0]['PnL'].mean() if wins > 0 else 0
                avg_loss = completed_trades[completed_trades['PnL'] < 0]['PnL'].mean() if losses > 0 else 0
                total_pnl = completed_trades['PnL'].sum()

                report.append(f"\n📈 TRADING STATISTICS:")
                report.append("-" * 70)
                report.append(f"Total Trades: {total}")
                report.append(f"Wins: {wins} | Losses: {losses}")
                report.append(f"Win Rate: {win_rate:.1f}%")
                report.append(f"Avg Win: ₹{avg_win:,.2f} | Avg Loss: ₹{avg_loss:,.2f}")
                report.append(f"Total P&L: ₹{total_pnl:,.2f}")

                if avg_loss != 0:
                    profit_factor = abs(avg_win / avg_loss) if avg_loss < 0 else 0
                    report.append(f"Profit Factor: {profit_factor:.2f}")

    # Footer
    report.append("\n" + "=" * 70)
    report.append("✅ Report Generated Successfully")
    report.append("=" * 70)

    return "\n".join(report)


def save_report(report_text, output_dir="reports"):
    """Save report to file."""
    os.makedirs(output_dir, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{output_dir}/daily_report_{today}.txt"

    with open(filename, "w") as f:
        f.write(report_text)

    print(f"📄 Report saved to: {filename}")
    return filename


def print_report():
    """Print report to console."""
    report = generate_daily_report()
    print(report)
    return report


if __name__ == "__main__":
    # Generate and print report
    report = print_report()

    # Save to file
    save_report(report)
