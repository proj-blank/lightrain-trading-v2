# scripts/clean_portfolio_and_results.py
import re
import os
import pandas as pd

P_PATH = "data/portfolio.csv"
R_PATH = "data/results.csv"

def extract_first_number(s):
    """Try to extract first numeric token from a string. Returns float or None."""
    if pd.isna(s):
        return None
    if isinstance(s, (int, float)):
        return float(s)
    text = str(s)
    # find first float-like number
    m = re.search(r"[-+]?\d*\.\d+|\d+", text)
    if m:
        try:
            return float(m.group(0))
        except:
            return None
    return None

def clean_portfolio():
    if not os.path.exists(P_PATH):
        print("⚠️ portfolio.csv not found; nothing to clean.")
        return

    df = pd.read_csv(P_PATH, dtype=str)  # read as strings to inspect
    if "EntryPrice" not in df.columns:
        print("⚠️ EntryPrice column missing; nothing to clean.")
        return

    # Try numeric conversion first
    df["EntryPrice_clean"] = pd.to_numeric(df["EntryPrice"], errors="coerce")

    # For rows where numeric failed, attempt regex extraction
    mask = df["EntryPrice_clean"].isna()
    if mask.any():
        for ix in df[mask].index:
            raw = df.at[ix, "EntryPrice"]
            val = extract_first_number(raw)
            df.at[ix, "EntryPrice_clean"] = val

    # Drop rows we couldn't fix
    before = len(df)
    df = df.dropna(subset=["EntryPrice_clean"]).copy()
    after = len(df)
    print(f"Cleaned portfolio: dropped {before-after} rows with unparseable EntryPrice.")

    # Replace EntryPrice with cleaned numeric values and ensure correct columns
    df["EntryPrice"] = pd.to_numeric(df["EntryPrice_clean"], errors="coerce")
    df = df[[c for c in ["Ticker", "Status", "EntryPrice"] if c in df.columns]]

    df.to_csv(P_PATH, index=False)
    print("✅ portfolio.csv cleaned and saved.")

def reset_results():
    # remove or recreate blank results.csv
    if os.path.exists(R_PATH):
        try:
            os.remove(R_PATH)
            print("✅ Old results.csv removed.")
        except Exception as e:
            print("⚠️ Could not remove results.csv:", e)
    # create an empty results file with header to avoid EmptyDataError
    import pandas as pd
    pd.DataFrame(columns=[
        "Date", "PortfolioValue", "BenchmarkValue",
        "PortfolioDailyRet", "BenchmarkDailyRet",
        "PortfolioCumRet", "BenchmarkCumRet"
    ]).to_csv(R_PATH, index=False)
    print("✅ Fresh results.csv created with headers.")

if __name__ == "__main__":
    clean_portfolio()
    reset_results()
