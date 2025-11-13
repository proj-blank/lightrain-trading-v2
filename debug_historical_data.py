#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/ubuntu/trading')
from scripts.angelone_api import get_angelone_api

# Test historical data with debug output
api = get_angelone_api()
ticker = 'SBIN.NS'

# Get token
symbol_token = api._get_symbol_token(ticker)
print(f"Ticker: {ticker}")
print(f"Symbol Token: {symbol_token}")

# Try to get historical data
from datetime import datetime, timedelta
to_date = datetime.now().strftime('%Y-%m-%d %H:%M')
from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M')

print(f"From: {from_date}")
print(f"To: {to_date}")

params = {
    'exchange': 'NSE',
    'symboltoken': symbol_token,
    'interval': 'ONE_DAY',
    'fromdate': from_date,
    'todate': to_date
}

print(f"Params: {params}")

data = api.smart_api.getCandleData(params)
print(f"Response status: {data.get('status')}")
print(f"Response message: {data.get('message')}")
if data.get('data'):
    print(f"Data rows: {len(data['data'])}")
else:
    print(f"Full response: {data}")
