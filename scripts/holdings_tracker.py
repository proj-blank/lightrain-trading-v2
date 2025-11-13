import os
import pandas as pd
from datetime import datetime

HOLDINGS_FILE = "data/holdings.csv"

def update_holdings(portfolio, stock_data, current_date=None):
    """
    Logs per-day unrealized PnL for each ticker in the portfolio.
    """
    rows = []
    date_str = current_date.strftime("%Y-%m-%d") if current_date else datetime.today().strftime("%Y-%m-%d")

    for _, row in portfolio.iterrows():
        ticker = row.get("Ticker")
        entry_price = float(row.get("EntryPrice", 0))
        qty = int(row.get("Quantity", 1))

        if ticker not in stock_data:
            continue

        df = stock_data[ticker]
        if current_date is not None:
            df = df[df.index <= current_date]
        if df.empty:
            continue

        latest_price = float(df["Close"].iloc[-1])
        pnl_unrealized = (latest_price - entry_price) * qty

        rows.append({
            "Date": date_str,
            "Ticker": ticker,
            "EntryPrice": entry_price,
            "LastPrice": latest_price,
            "Quantity": qty,
            "UnrealizedPnL": pnl_unrealized
        })

    if not rows:
        return

    df_new = pd.DataFrame(rows)

    if not os.path.exists(HOLDINGS_FILE) or os.path.getsize(HOLDINGS_FILE) == 0:
        df_new.to_csv(HOLDINGS_FILE, index=False)
    else:
        df = pd.read_csv(HOLDINGS_FILE)
        df = df[df["Date"] != date_str]  # avoid duplicate date
        df = pd.concat([df, df_new], ignore_index=True)
        df.to_csv(HOLDINGS_FILE, index=False)

    print(f"📊 Holdings updated for {date_str}.")
