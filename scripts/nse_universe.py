#!/usr/bin/env python3
"""
NSE Universe - Index-based stock selection for daily screening

Sources:
- Large-caps: Nifty 50 (50 stocks)
- Mid-caps: Nifty Midcap 150 top stocks (100 stocks)
- Micro-caps: Nifty Smallcap 250 liquid stocks (200 stocks)

Total: ~350 liquid, tradable stocks
Updated: Nov 2024
"""

# Nifty 50 - India's top 50 companies by market cap
NIFTY_50 = [
    'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK',
    'HINDUNILVR', 'ITC', 'SBIN', 'BHARTIARTL', 'KOTAKBANK',
    'BAJFINANCE', 'LT', 'ASIANPAINT', 'AXISBANK', 'MARUTI',
    'HCLTECH', 'SUNPHARMA', 'TITAN', 'ULTRACEMCO', 'WIPRO',
    'ONGC', 'NTPC', 'POWERGRID', 'M&M', 'NESTLEIND',
    'TATAMOTORS', 'TATASTEEL', 'TECHM', 'BAJAJFINSV', 'ADANIENT',
    'HINDALCO', 'COALINDIA', 'INDUSINDBK', 'JSWSTEEL', 'DIVISLAB',
    'DRREDDY', 'EICHERMOT', 'GRASIM', 'HEROMOTOCO', 'BRITANNIA',
    'CIPLA', 'APOLLOHOSP', 'ADANIPORTS', 'BPCL', 'TATACONSUM',
    'BAJAJ-AUTO', 'SHRIRAMFIN', 'SBILIFE', 'HDFCLIFE', 'LTIM'
]

# Nifty Midcap 150 - Top 100 liquid mid-caps
NIFTY_MIDCAP_150 = [
    # IT/Tech
    'PERSISTENT', 'COFORGE', 'LTTS', 'CYIENT', 'MPHASIS',
    'ZOMATO', 'PAYTM', 'NYKAA', 'POLICYBZR',

    # Financial Services
    'BAJAJHLDNG', 'MUTHOOTFIN', 'CHOLAFIN', 'SBICARD', 'POONAWALLA',
    'LICHSGFIN', 'RECLTD', 'PFC', 'IRFC', 'ANGELONE',

    # Pharma/Healthcare
    'ZYDUSLIFE', 'LALPATHLAB', 'METROPOLIS', 'AUROPHARMA', 'BIOCON',
    'TORNTPHARM', 'ALKEM', 'LUPIN', 'IPCALAB', 'LAURUSLABS',

    # Consumer
    'TRENT', 'JUBLFOOD', 'DIXON', 'CROMPTON', 'RELAXO',
    'VGUARD', 'BATAINDIA', 'PAGEIND', 'MARICO', 'GODREJCP',

    # Auto/Auto Ancillary
    'TVSMOTOR', 'BALKRISIND', 'MOTHERSON', 'BOSCHLTD', 'EXIDEIND',
    'MRF', 'APOLLOTYRE', 'CEAT', 'ESCORTS', 'ASHOKLEY',

    # Infrastructure/Construction
    'GODREJPROP', 'OBEROIRLTY', 'DLF', 'PRESTIGE', 'BRIGADE',
    'CUMMINSIND', 'VOLTAS', 'BLUEDART', 'VBL', 'CONCOR',

    # Industrials/Manufacturing
    'ABB', 'SIEMENS', 'HAVELLS', 'POLYCAB', 'KEI',
    'THERMAX', 'SCHAEFFLER', 'SKFINDIA', 'TIMKEN', 'CRISIL',

    # Materials/Chemicals
    'PIDILITIND', 'AARTI', 'DEEPAKNTR', 'SRF', 'ATUL',
    'TATACHEMICAL', 'GNFC', 'CHAMBLFERT', 'COROMANDEL', 'NAVINFLUOR',

    # Cement/Building Materials
    'AMBUJACEM', 'ACC', 'SHREECEM', 'JKCEMENT', 'RAMCOCEM',
    'HEIDELBERG', 'ORIENT', 'JKLAKSHMI',

    # Metals/Mining
    'VEDL', 'NMDC', 'MOIL', 'NATIONALUM', 'HINDZINC',

    # Energy/Power
    'TATAPOWER', 'ADANIPOWER', 'TORNTPOWER', 'NHPC', 'SJVN'
]

# Nifty Smallcap 250 - Top 200 liquid small/micro caps
NIFTY_SMALLCAP_250 = [
    # IT/Tech
    'KPITTECH', 'MASTEK', 'SONATSOFTW', 'ZENITHSTL', 'RATEGAIN',
    'ROUTE', 'HAPPSTMNDS', 'DATAPATTNS', 'INTELLECT', 'NEWGEN',

    # Chemicals/Specialty
    'FLUOROCHEM', 'FINEORG', 'GALAXYSURF', 'ROSSARI', 'ALKYLAMINE',
    'CLEAN', 'TATVA', 'VINATI', 'POLYMED', 'TATACHEM',
    'SHARDACROP', 'SUMICHEM', 'GRAVITA', 'GOCLCORP', 'SYMPHONY',

    # Pharma
    'AARTIDRUGS', 'SUVEN', 'CAPLIPOINT', 'JBCHEPHARM', 'NATCOPHAR',
    'STRIDES', 'SYNGENE', 'DISHMAN', 'SEQUENT', 'IOLCP',

    # Engineering/Manufacturing
    'ASTRAMICRO', 'RATNAMANI', 'ELECON', 'GREAVESCOT', 'KALYANKJIL',
    'TIINDIA', 'AJANTPHARM', 'FINCABLES', 'HLEGLAS', 'ORIENTELEC',
    'APLAPOLLO', 'CENTURYPLY', 'KAJARIACER', 'GRINDWELL', 'ORIENTCEM',

    # Consumer/Retail
    'GOCOLORS', 'SMSLIFE', 'SAFARI', 'VIP', 'JUBLPHARMA',
    'VAIBHAVGBL', 'RAYMOND', 'ADITYA', 'SWARAJENG', 'SHAILY',

    # Auto Components
    'ENDURANCE', 'JTEKTINDIA', 'FEDERALBNK', 'GUJGAS', 'RAINBOW',
    'MAXHEALTH', 'SHOPERSTOP', 'TATAINVEST', 'MANAPPURAM', 'MFSL',

    # Textiles
    'GOKEX', 'CHENNPETRO', 'MANINFRA', 'GPIL', 'KKCL',

    # Infrastructure
    'IRB', 'ASHOKA', 'SADBHAV', 'JYOTHYLAB', 'SNOWMAN',
    'BLUEDART', 'MAHLOG', 'AEGISLOG', 'ALLCARGO', 'TCI',

    # Metals/Mining
    'RATNAMANI', 'WELCORP', 'SARDAEN', 'APL', 'MOIL',

    # Electrical/Electronics
    'KIRIINDUS', 'FIEM', 'SUPPETRO', 'RENUKA', 'JMFINANCIL',

    # Microcaps with good liquidity
    'DIGISPICE', 'RPPINFRA', 'URJA', 'PENINLAND', 'KELLTONTEC',
    'RAJRATAN', 'WHEELS', 'BALRAMCHIN', 'APLLTD',

    # Additional liquid smallcaps
    'PNBHOUSING', 'CANFINHOME', 'IIFL', 'AAVAS', 'HFCL',
    'STARHEALTH', 'MAPMYINDIA', 'RBLBANK', 'JUBILANT', 'CUB',
    'IDFCFIRSTB', 'INDHOTEL', 'LEMONTREE', 'EIH', 'CHALET',
    'NATIONALUM', 'SAIL', 'JSWENERGY', 'GMRINFRA', 'ADANIGREEN',
    'IDEA', 'TTML', 'MTNL', 'SUZLON', 'RPOWER',
    'DCMSHRIRAM', 'CHAMBLFERT', 'GSFC', 'FACT', 'RCF',
    'CHOLAHLDNG', 'MAHINDCIE', 'SUNDARMFIN', 'SHRIRAMCIT', 'M&MFIN',
    'SUNTV', 'PVRINOX', 'PVR', 'NAVNETEDUL', 'Career',
    'HUDCO', 'NCC', 'NBCC', 'KNR', 'RVNL',
    'BEL', 'HAL', 'BEML', 'COCHINSHIP', 'GRSE',
    'HONAUT', 'ATUL', 'MANORG', 'KANSAINER', 'BALRAMCHIN',
    'SUPREMEIND', 'NILKAMAL', 'SYMPHONY', 'AMBER', 'FIEMIND',
    'SOLARINDS', 'CREDITACC', 'JBMA', 'MAHSCOOTER', 'BAJAJELEC',
    'FINEORG', 'ANDHRAPAP', 'ANDHRACEMT', 'ARIES', 'ASTERDM',
    'CAPLIPOINT', 'DATAMATICS', 'DCAL', 'DCBBANK', 'DELTACORP',
    'DISHTV', 'EIHOTEL', 'EQUITAS', 'ESABINDIA', 'FINCABLES',
    'GALLANTT', 'GESHIP', 'GILLETTE', 'GPPL', 'GREAVESCOT',
    'GREENPANEL', 'GULFOILLUB', 'HEIDELBERG', 'HEG', 'HERANBA',
    'HESTERBIO', 'HIKAL', 'HLEGLAS', 'HSIL', 'IEX',
    'IFBIND', 'IFCI', 'IIFLSEC', 'IL&FSTRANS', 'INCREDIBLE'
]

def get_nse_universe():
    """
    Get complete NSE universe categorized by market cap.

    Returns:
        dict: {'large_caps': [...], 'mid_caps': [...], 'micro_caps': [...]}
    """
    return {
        'large_caps': [f"{symbol}.NS" for symbol in NIFTY_50],
        'mid_caps': [f"{symbol}.NS" for symbol in NIFTY_MIDCAP_150],
        'micro_caps': [f"{symbol}.NS" for symbol in NIFTY_SMALLCAP_250]
    }

def get_all_symbols():
    """Get flat list of all symbols (with .NS suffix)."""
    universe = get_nse_universe()
    return universe['large_caps'] + universe['mid_caps'] + universe['micro_caps']

def get_universe_stats():
    """Print universe statistics."""
    universe = get_nse_universe()

    print("=" * 80)
    print("NSE TRADING UNIVERSE")
    print("=" * 80)
    print(f"Large-caps (Nifty 50):          {len(universe['large_caps']):3} stocks")
    print(f"Mid-caps (Midcap 150):          {len(universe['mid_caps']):3} stocks")
    print(f"Micro-caps (Smallcap 250):      {len(universe['micro_caps']):3} stocks")
    print("-" * 80)
    print(f"Total Universe:                 {len(get_all_symbols()):3} stocks")
    print("=" * 80)

    return universe

if __name__ == "__main__":
    get_universe_stats()
