# scripts/data_loader.py
import yfinance as yf
import pandas as pd
import os

def load_watchlist(file_path="data/watchlist.csv"):
    """
    Loads tickers from watchlist.csv.
    Assumes the CSV has a column named 'Ticker'.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"❌ Watchlist file not found: {file_path}")

    df = pd.read_csv(file_path)
    if "Ticker" not in df.columns:
        raise ValueError("❌ 'Ticker' column missing in watchlist.csv")

    tickers = df["Ticker"].dropna().unique().tolist()
    return tickers

def load_data(period="6mo", interval="1d", file_path="data/watchlist.csv"):
    """
    Downloads historical stock data for all tickers in watchlist.csv.
    Returns a dictionary {ticker: DataFrame}
    """
    tickers = load_watchlist(file_path)
    data = {}
    for ticker in tickers:
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        if not df.empty:
            data[ticker] = df
    return data
