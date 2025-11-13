"""
scripts/universe.py
Build a microcap universe for India.
Options:
 - load NIFTY Microcap 250 constituents (if you provide a CSV)
 - or compute market-cap <= cutoff using yfinance
"""

import yfinance as yf
import pandas as pd
import time
from typing import List, Optional

def read_candidates(path: str = "candidates.txt") -> List[str]:
    with open(path, "r") as f:
        lines = [l.strip() for l in f.readlines()]
    return [l for l in lines if l]

def get_marketcap_yf(symbol_yahoo: str) -> Optional[float]:
    try:
        t = yf.Ticker(symbol_yahoo)
        fast = getattr(t, "fast_info", None)
        if fast:
            mc = fast.get("market_cap") or fast.get("marketCap")
            if mc:
                return float(mc)
        info = t.info or {}
        mc = info.get("marketCap") or info.get("market_cap")
        if mc:
            return float(mc)
    except Exception:
        return None
    return None

def build_microcap_universe(candidates: List[str], exchange: str = "NSE", cutoff_crore: float = 5000.0) -> pd.DataFrame:
    rows = []
    thresh = cutoff_crore * 1e7
    for s in candidates:
        yahoo = f"{s}.NS" if exchange.upper()=="NSE" else f"{s}.BO"
        mc = get_marketcap_yf(yahoo)
        rows.append({"symbol": s, "yahoo": yahoo, "marketcap": mc})
        time.sleep(0.4)  # be polite
    df = pd.DataFrame(rows)
    df = df.dropna(subset=["marketcap"])
    df["marketcap_crore"] = df["marketcap"] / 1e7
    micro = df[df["marketcap"] <= thresh].sort_values("marketcap").reset_index(drop=True)
    return micro

def save_universe(df: pd.DataFrame, path: str = "results/microcap_universe.csv"):
    df.to_csv(path, index=False)
    return path
