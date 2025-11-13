import sys
sys.path.insert(0, '/home/ubuntu/trading')
from scripts.telegram_bot import send_telegram_message

msg = 'LightRain AWS - PostgreSQL initialized with 12 positions (6 DAILY + 6 SWING). System ready!'
result = send_telegram_message(msg)
print('Telegram test:', 'SUCCESS' if result else 'FAILED')
