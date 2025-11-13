#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/ubuntu/trading')
from scripts.database import get_db_connection
from datetime import datetime

# Get today's date
today = datetime.now().strftime('%Y-%m-%d')

conn = get_db_connection()
cur = conn.cursor()

# Count positions to delete
cur.execute('''
    SELECT ticker FROM positions 
    WHERE strategy = 'DAILY' AND entry_date = %s AND status = 'OPEN'
''', (today,))
tickers = [row[0] for row in cur.fetchall()]

print(f'Found {len(tickers)} DAILY positions from {today}:')
for t in tickers:
    print(f'  - {t}')

if len(tickers) > 0:
    # Update status to CLOSED instead of deleting (safer)
    cur.execute('''
        UPDATE positions 
        SET status = 'CLOSED', updated_at = NOW()
        WHERE strategy = 'DAILY' AND entry_date = %s AND status = 'OPEN'
    ''', (today,))
    
    conn.commit()
    print(f'\n✅ Closed {len(tickers)} positions (marked as CLOSED)')
else:
    print('No positions to close')

cur.close()
conn.close()
