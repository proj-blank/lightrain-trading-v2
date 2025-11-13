# scripts/performance_tracker.py
import os
import pandas as pd
from datetime import datetime

results_path = "data/results.csv"

def update_results(portfolio, stock_data):
    """
    Track daily portfolio vs benchmark (NIFTY) with defensive parsing.
    Skips portfolio rows with non-numeric EntryPrice.
    """

    # ----- 1) Portfolio Value (baseline) -----
    portfolio_value = 100000.0

    for _, row in portfolio.iterrows():
        # Only consider active positions
        status = str(row.get("Status", "")).upper()
        if status != "HOLD":
            continue

        ticker = row.get("Ticker")
        if not ticker or ticker not in stock_data:
            continue

        # latest close (safe scalar)
        try:
            latest_price = stock_data[ticker]["Close"].iloc[-1]
            # ensure python float
            if hasattr(latest_price, "item"):
                latest_price = float(latest_price.item())
            else:
                latest_price = float(latest_price)
        except Exception:
            print(f"⚠️ Could not read latest price for {ticker}, skipping.")
            continue

        # safe parse entry_price
        entry_price_raw = row.get("EntryPrice")
        entry_price = pd.to_numeric(entry_price_raw, errors="coerce")

        if pd.isna(entry_price):
            # skip corrupt entries (do not let them corrupt results)
            print(f"⚠️ Non-numeric EntryPrice for {ticker}: {entry_price_raw} — skipping position in performance calc.")
            continue

        entry_price = float(entry_price)
        # accumulate PnL (this is simple PnL style; change to position size if you track shares)
        portfolio_value += (latest_price - entry_price)

    # ----- 2) Benchmark (NIFTY 50) -----
    try:
        if "NIFTY" in stock_data and not stock_data["NIFTY"].empty:
            benchmark_value = stock_data["NIFTY"]["Close"].iloc[-1]
            if hasattr(benchmark_value, "item"):
                benchmark_value = float(benchmark_value.item())
            else:
                benchmark_value = float(benchmark_value)
        else:
            # fallback if not provided
            benchmark_value = 10000.0
    except Exception:
        benchmark_value = 10000.0

    # ----- 3) Append / create results dataframe -----
    new_row = {
        "Date": datetime.today().strftime("%Y-%m-%d"),
        "PortfolioValue": portfolio_value,
        "BenchmarkValue": benchmark_value,
    }

    if not os.path.exists(results_path) or os.path.getsize(results_path) == 0:
        df = pd.DataFrame([new_row])
    else:
        df = pd.read_csv(results_path)

        # make sure previously stored numeric columns are numeric
        for col in ["PortfolioValue", "BenchmarkValue"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    # ----- 4) Compute returns safely -----
    # Ensure numeric before pct_change to avoid string division errors
    df["PortfolioValue"] = pd.to_numeric(df["PortfolioValue"], errors="coerce")
    df["BenchmarkValue"] = pd.to_numeric(df["BenchmarkValue"], errors="coerce")

    # compute daily returns; use fill_method=None to avoid future warnings
    df["PortfolioDailyRet"] = df["PortfolioValue"].pct_change(fill_method=None).fillna(0)
    df["BenchmarkDailyRet"] = df["BenchmarkValue"].pct_change(fill_method=None).fillna(0)

    # cumulative returns (as decimal, e.g. 0.05 = +5%)
    df["PortfolioCumRet"] = (1 + df["PortfolioDailyRet"]).cumprod() - 1
    df["BenchmarkCumRet"] = (1 + df["BenchmarkDailyRet"]).cumprod() - 1

    # ----- 5) Save -----
    df.to_csv(results_path, index=False)
    print("📈 Results updated.")
