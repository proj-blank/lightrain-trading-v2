# scripts/watchlist_builder.py
"""
Build a quality watchlist of Indian microcap stocks with screening criteria:
- Market cap range: ₹500 Cr - ₹5000 Cr
- Minimum liquidity (avg volume)
- Price > ₹10 (avoid penny stocks)
- Listed on NSE
"""

import pandas as pd
import yfinance as yf
import time
from typing import List, Dict, Optional

# Sample list of Indian microcap candidates (you can expand this)
# These are some known microcap stocks on NSE
MICROCAP_CANDIDATES = [
    # Infrastructure & Construction
    "RPPINFRA.NS", "URJA.NS", "MAHAPEXLTD.NS",

    # Technology & IT
    "KELLTONTEC.NS", "DIGISPICE.NS", "CREATIVEYE.NS",

    # Industrial & Manufacturing
    "GOLDTECH.NS", "ALPHAGEO.NS", "MEP.NS",

    # Specialty Chemicals & Materials
    "PENINLAND.NS", "ARIES.NS",

    # Real Estate & Housing
    "ORIENTLTD.NS", "LAKPRE.NS",

    # Healthcare & Pharma
    "AARTIDRUGS.NS", "SUVEN.NS",

    # Auto Components
    "Gabriel.NS", "WHEELS.NS",

    # Textiles
    "GOKEX.NS", "MODIRUBBER.NS",

    # Others
    "RAJRATAN.NS", "MIDHANI.NS", "CENTEXT.NS",
    "METALFORGE.NS", "APCL.NS", "RADIOCITY.NS"
]


def get_stock_info(ticker: str) -> Optional[Dict]:
    """Fetch stock information and metrics."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # Get market cap (in INR crore)
        market_cap = info.get('marketCap', 0)
        market_cap_cr = market_cap / 1e7 if market_cap else 0

        # Get current price
        current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))

        # Get average volume (3 months)
        avg_volume = info.get('averageVolume', info.get('averageVolume3Month', 0))

        # Get fundamental metrics
        pe_ratio = info.get('trailingPE', 0)
        pb_ratio = info.get('priceToBook', 0)
        debt_to_equity = info.get('debtToEquity', 0)

        return {
            'ticker': ticker,
            'name': info.get('longName', ticker),
            'sector': info.get('sector', 'Unknown'),
            'industry': info.get('industry', 'Unknown'),
            'market_cap_cr': round(market_cap_cr, 2),
            'price': round(current_price, 2),
            'avg_volume': avg_volume,
            'pe_ratio': round(pe_ratio, 2) if pe_ratio else None,
            'pb_ratio': round(pb_ratio, 2) if pb_ratio else None,
            'debt_to_equity': round(debt_to_equity, 2) if debt_to_equity else None,
        }
    except Exception as e:
        print(f"⚠️ Error fetching {ticker}: {e}")
        return None


def apply_screening_criteria(stock_info: Dict) -> tuple[bool, str]:
    """
    Apply screening criteria to filter quality microcaps.

    Returns:
        (passes: bool, reason: str)
    """
    # Market cap filter: ₹500 Cr - ₹5000 Cr
    if stock_info['market_cap_cr'] < 500:
        return False, f"Market cap too low: ₹{stock_info['market_cap_cr']:.0f} Cr"
    if stock_info['market_cap_cr'] > 5000:
        return False, f"Market cap too high: ₹{stock_info['market_cap_cr']:.0f} Cr"

    # Price filter: > ₹10 (avoid penny stocks)
    if stock_info['price'] < 10:
        return False, f"Price too low: ₹{stock_info['price']:.2f}"

    # Liquidity filter: avg volume > 10,000
    if stock_info['avg_volume'] < 10000:
        return False, f"Low liquidity: {stock_info['avg_volume']:,} avg volume"

    # Fundamental filters (optional - can be relaxed)
    # if stock_info['pe_ratio'] and stock_info['pe_ratio'] > 100:
    #     return False, f"P/E too high: {stock_info['pe_ratio']:.2f}"

    return True, "Passed all criteria"


def build_watchlist(candidates: List[str] = None,
                   max_stocks: int = 30,
                   output_path: str = "data/watchlist_new.csv") -> pd.DataFrame:
    """
    Build a screened watchlist of quality microcaps.

    Args:
        candidates: List of ticker symbols to screen
        max_stocks: Maximum number of stocks in final watchlist
        output_path: Path to save the watchlist CSV

    Returns:
        DataFrame with screened stocks
    """
    if candidates is None:
        candidates = MICROCAP_CANDIDATES

    print(f"🔍 Screening {len(candidates)} microcap candidates...\n")

    qualified_stocks = []

    for i, ticker in enumerate(candidates, 1):
        print(f"[{i}/{len(candidates)}] Checking {ticker}...", end=" ")

        stock_info = get_stock_info(ticker)

        if stock_info is None:
            print("❌ Failed to fetch data")
            time.sleep(1)
            continue

        passes, reason = apply_screening_criteria(stock_info)

        if passes:
            qualified_stocks.append(stock_info)
            print(f"✅ {reason} | MCap: ₹{stock_info['market_cap_cr']:.0f}Cr | Price: ₹{stock_info['price']:.2f}")
        else:
            print(f"⛔ {reason}")

        time.sleep(0.5)  # Rate limiting

        if len(qualified_stocks) >= max_stocks:
            print(f"\n✅ Reached target of {max_stocks} stocks")
            break

    # Create DataFrame
    df = pd.DataFrame(qualified_stocks)

    if not df.empty:
        # Sort by market cap (smaller microcaps first)
        df = df.sort_values('market_cap_cr')

        # Save to CSV
        df.to_csv(output_path, index=False)
        print(f"\n✅ Saved {len(df)} qualified stocks to {output_path}")

        # Print summary
        print(f"\n📊 Watchlist Summary:")
        print(f"   Total Stocks: {len(df)}")
        print(f"   Market Cap Range: ₹{df['market_cap_cr'].min():.0f} - ₹{df['market_cap_cr'].max():.0f} Cr")
        print(f"   Price Range: ₹{df['price'].min():.2f} - ₹{df['price'].max():.2f}")
        print(f"   Sectors: {df['sector'].nunique()}")

        # Show sector distribution
        print(f"\n   Sector Distribution:")
        for sector, count in df['sector'].value_counts().head(5).items():
            print(f"     • {sector}: {count} stocks")

        return df
    else:
        print("⚠️ No stocks qualified!")
        return pd.DataFrame()


def add_to_main_watchlist(new_watchlist_path: str = "data/watchlist_new.csv",
                          main_watchlist_path: str = "data/watchlist.csv"):
    """Add new stocks to main watchlist, avoiding duplicates."""
    try:
        # Load new watchlist
        new_df = pd.read_csv(new_watchlist_path)

        # Load existing watchlist
        if pd.io.common.file_exists(main_watchlist_path):
            main_df = pd.read_csv(main_watchlist_path)
            existing_tickers = set(main_df['Ticker'].values)
        else:
            main_df = pd.DataFrame(columns=['Ticker'])
            existing_tickers = set()

        # Find new tickers
        new_tickers = [t for t in new_df['ticker'].values if t not in existing_tickers]

        if new_tickers:
            # Add new tickers to main watchlist
            new_rows = pd.DataFrame({'Ticker': new_tickers})
            main_df = pd.concat([main_df, new_rows], ignore_index=True)
            main_df.to_csv(main_watchlist_path, index=False)

            print(f"✅ Added {len(new_tickers)} new stocks to {main_watchlist_path}")
            print(f"   New tickers: {', '.join(new_tickers[:10])}{'...' if len(new_tickers) > 10 else ''}")
        else:
            print("ℹ️ No new stocks to add (all already in watchlist)")

    except Exception as e:
        print(f"❌ Error updating watchlist: {e}")


if __name__ == "__main__":
    # Build new watchlist
    watchlist_df = build_watchlist(max_stocks=30)

    # Optionally add to main watchlist
    if not watchlist_df.empty:
        print("\n" + "="*60)
        response = input("Add these stocks to main watchlist? (y/n): ")
        if response.lower() == 'y':
            add_to_main_watchlist()
