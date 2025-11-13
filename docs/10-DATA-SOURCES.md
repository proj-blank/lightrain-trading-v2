# 10 - Data Sources

Complete guide to data providers, APIs, and data reliability.

---

## Table of Contents
1. [Data Source Overview](#data-source-overview)
2. [yfinance](#yfinance)
3. [Angel One API](#angel-one-api)
4. [Data Reliability](#data-reliability)
5. [Fallback Strategy](#fallback-strategy)

---

## Data Source Overview

### Primary Sources
1. **yfinance**: Historical OHLCV data, screening, backtesting
2. **Angel One API**: Real-time quotes, order execution, live indices

### Use Cases
| Data Type | Primary Source | Fallback | Usage |
|-----------|---------------|----------|--------|
| Historical OHLCV | yfinance | - | Screening, indicators |
| Real-time prices | Angel One | yfinance | Monitoring, execution |
| Index data | Angel One | yfinance | Market sentiment |
| Order execution | Angel One | Manual | Trade execution |

---

## yfinance

### Overview
Open-source library for Yahoo Finance data.

### Features
- **Free**: No API key required
- **Historical data**: Up to 10 years
- **Multiple intervals**: 1m, 5m, 15m, 1h, 1d, 1wk, 1mo
- **Global coverage**: NSE, BSE, NYSE, NASDAQ, etc.

### Usage in LightRain

#### Screening Data
```python
import yfinance as yf

# Download 6 months of daily data
df = yf.download('RELIANCE.NS', period='6mo', interval='1d', progress=False)

# Columns: Open, High, Low, Close, Adj Close, Volume
```

#### Current Price (Delayed)
```python
stock = yf.Ticker('TCS.NS')
hist = stock.history(period='1d')
current_price = hist['Close'].iloc[-1]
```

### NSE Ticker Format
```python
# NSE stocks require .NS suffix
'RELIANCE.NS'  # Correct
'RELIANCE'     # Incorrect (will fail)
```

### Limitations
- **15-minute delay**: Not real-time
- **Rate limits**: Too many requests = temporary ban
- **Data quality**: Occasional missing/incorrect data
- **No order execution**: Read-only

---

## Angel One API

### Overview
Official broker API for Angel Broking (Angel One).

### Features
- **Real-time data**: Live quotes (NSE, BSE)
- **Order execution**: Market, limit, stop-loss orders
- **Account info**: Holdings, funds, positions
- **Historical data**: Candles (intraday + daily)

### Authentication
```python
from SmartApi import SmartConnect
import pyotp

# Credentials from .env
API_KEY = os.getenv('ANGELONE_API_KEY')
CLIENT_CODE = os.getenv('ANGELONE_CLIENT_ID')
PASSWORD = os.getenv('ANGELONE_PASSWORD')
TOTP_SECRET = os.getenv('ANGELONE_TOTP_SECRET')

# Login
smart_api = SmartConnect(api_key=API_KEY)
totp = pyotp.TOTP(TOTP_SECRET).now()
data = smart_api.generateSession(CLIENT_CODE, PASSWORD, totp)

# Session valid for 1 day
```

### Usage in LightRain

#### Real-Time Index Data
```python
# Nifty 50
ltp_data = smart_api.ltpData('NSE', 'NIFTY 50', '99926000')
ltp = ltp_data['data']['ltp']
open_price = ltp_data['data']['open']

# Calculate today's change
change_pct = ((ltp - open_price) / open_price) * 100
```

#### Real-Time Stock Price
```python
# Stock symbols require exchange token
# Example: RELIANCE = token 2885
ltp_data = smart_api.ltpData('NSE', 'RELIANCE-EQ', '2885')
current_price = ltp_data['data']['ltp']
```

#### Historical Candles
```python
params = {
    'exchange': 'NSE',
    'symboltoken': '2885',  # RELIANCE
    'interval': 'ONE_DAY',
    'fromdate': '2024-01-01 09:00',
    'todate': '2024-11-13 15:30'
}
candles = smart_api.getCandleData(params)
```

### Token Mapping
Angel One requires exchange tokens for each symbol.

**Setup Script**: `setup_angelone_symbols.py`

**Database Table**: `angelone_symbols`
```sql
CREATE TABLE angelone_symbols (
    symbol VARCHAR(20) PRIMARY KEY,
    token VARCHAR(20) NOT NULL,
    exchange VARCHAR(10) DEFAULT 'NSE'
);
```

### Index Tokens
```python
INDICES = {
    'NIFTY 50': '99926000',
    'NIFTY MIDCAP 150': '99926023',
    'NIFTY SMLCAP 250': '99926037'
}
```

### Limitations
- **Session timeout**: Requires daily re-login (TOTP)
- **Rate limits**: 10 requests/second
- **Trading hours only**: Some APIs work 9:15 AM - 3:30 PM only
- **Token requirement**: Must map symbols to tokens

---

## Data Reliability

### yfinance Reliability
**Strengths**:
- Consistent historical data
- Rarely goes down
- Good for backtesting

**Weaknesses**:
- 15-minute delay
- Occasional missing bars
- Can be blocked if overused

### Angel One Reliability
**Strengths**:
- Real-time data
- Official broker API
- Order execution

**Weaknesses**:
- Session expires daily
- API downtime during market hours (rare)
- Rate limits

---

## Fallback Strategy

### Price Fetching
```python
def get_current_price(ticker):
    # Try Angel One first
    try:
        price = get_price_angelone(ticker)
        if price:
            return price
    except:
        pass
    
    # Fallback to yfinance
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='1d')
        return hist['Close'].iloc[-1]
    except:
        return None
```

### Error Handling
- **Angel One down**: Use yfinance (delayed but reliable)
- **yfinance down**: Cache last known prices
- **Both down**: Alert user, pause trading

---

## Data Caching

### Purpose
Reduce API calls, improve performance.

### Implementation
```python
# Cache index data (5-minute expiry)
INDEX_CACHE = {}
CACHE_EXPIRY = 300  # seconds

def get_index_cached(token, symbol):
    cache_key = f"{token}_{symbol}"
    now = time.time()
    
    if cache_key in INDEX_CACHE:
        cached_time, cached_value = INDEX_CACHE[cache_key]
        if now - cached_time < CACHE_EXPIRY:
            return cached_value
    
    # Fetch fresh data
    value = get_index_change_angelone(token, symbol)
    INDEX_CACHE[cache_key] = (now, value)
    return value
```

---

## Data Quality Checks

### Missing Data
```python
# Check for sufficient data
if len(df) < 60:
    print(f"Insufficient data for {ticker}: {len(df)} bars")
    continue
```

### Data Validation
```python
# Check for NaN values
if df['Close'].isna().any():
    print(f"Missing close prices for {ticker}")
    df = df.dropna()
```

### Outlier Detection
```python
# Check for unrealistic price jumps
daily_returns = df['Close'].pct_change()
if abs(daily_returns).max() > 0.30:  # 30% daily move
    print(f"Warning: Large price movement detected for {ticker}")
```

---

## Environment Variables

### yfinance
No configuration needed.

### Angel One
Required in `.env`:
```bash
ANGELONE_API_KEY=your_api_key
ANGELONE_CLIENT_ID=your_client_id
ANGELONE_PASSWORD=your_password
ANGELONE_TOTP_SECRET=your_totp_secret
```

---

## Key Files

### Data Fetching
- `scripts/data_loader.py`: yfinance wrapper (legacy)
- `scripts/data_loader_angelone.py`: Angel One wrapper
- `scripts/angelone_api.py`: Angel One session management

### Symbol Management
- `setup_angelone_symbols.py`: Token mapping setup
- `test_angelone_data.py`: API testing

### Database
- `angelone_symbols` table: Symbol-to-token mapping

---

## Troubleshooting

### yfinance Issues
```python
# Error: No data returned
# Solution: Check ticker format (must include .NS for NSE)
df = yf.download('RELIANCE.NS', period='1mo')  # Correct

# Error: 429 Too Many Requests
# Solution: Add delays between requests
time.sleep(0.5)
```

### Angel One Issues
```python
# Error: Session expired
# Solution: Re-login
smart_api = SmartConnect(api_key=API_KEY)
totp = pyotp.TOTP(TOTP_SECRET).now()
smart_api.generateSession(CLIENT_CODE, PASSWORD, totp)

# Error: Invalid token
# Solution: Check angelone_symbols table
# Run: python3 setup_angelone_symbols.py
```

---

**Next**: [11-TROUBLESHOOTING.md](11-TROUBLESHOOTING.md) - Common issues and fixes
