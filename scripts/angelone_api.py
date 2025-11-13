"""
AngelOne API Integration for LightRain
- Market data (replace Yahoo Finance)
- Order execution (BUY/SELL/MODIFY/CANCEL)
- WebSocket for live prices
- Database logging for all API calls
"""
import os
import pyotp
from SmartApi import SmartConnect
from datetime import datetime, timedelta
import pandas as pd
from typing import Dict, List, Optional

# Database imports
import sys
sys.path.insert(0, '/home/ubuntu/trading')
from scripts.db_connection import get_db_cursor

class AngelOneAPI:
    def __init__(self):
        self.api_key = os.getenv('ANGELONE_API_KEY')
        self.client_id = os.getenv('ANGELONE_CLIENT_ID')
        self.password = os.getenv('ANGELONE_PASSWORD')
        self.totp_secret = os.getenv('ANGELONE_TOTP_SECRET')
        self.smart_api = None
        self.feed_token = None

    def login(self):
        """Login to AngelOne and get session"""
        try:
            self.smart_api = SmartConnect(api_key=self.api_key)
            totp = pyotp.TOTP(self.totp_secret).now()

            data = self.smart_api.generateSession(
                self.client_id,
                self.password,
                totp
            )

            if data['status']:
                self.feed_token = self.smart_api.getfeedToken()
                print(f"✅ AngelOne login successful")
                return True
            else:
                print(f"❌ AngelOne login failed: {data}")
                return False
        except Exception as e:
            print(f"❌ AngelOne login error: {e}")
            return False

    # ==================== MARKET DATA ====================

    def get_historical_data(self, ticker: str, interval: str = 'ONE_DAY',
                           from_date: str = None, to_date: str = None) -> pd.DataFrame:
        """
        Get historical market data from AngelOne (replaces Yahoo Finance)

        Args:
            ticker: Stock symbol (e.g., 'SBIN-EQ')
            interval: ONE_MINUTE, THREE_MINUTE, FIVE_MINUTE, TEN_MINUTE,
                     FIFTEEN_MINUTE, THIRTY_MINUTE, ONE_HOUR, ONE_DAY
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
        """
        if not self.smart_api:
            self.login()

        # Convert ticker format (SBIN.NS -> SBIN-EQ)
        symbol_token = self._get_symbol_token(ticker)

        if not to_date:
            to_date = datetime.now().strftime('%Y-%m-%d %H:%M')
        if not from_date:
            from_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d %H:%M')

        try:
            params = {
                "exchange": "NSE",
                "symboltoken": symbol_token,
                "interval": interval,
                "fromdate": from_date,
                "todate": to_date
            }

            data = self.smart_api.getCandleData(params)

            if data['status'] and data['data']:
                df = pd.DataFrame(data['data'],
                                 columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
                return df
            else:
                print(f"⚠️ No data for {ticker}")
                return pd.DataFrame()

        except Exception as e:
            print(f"❌ Error fetching data for {ticker}: {e}")
            return pd.DataFrame()

    def get_ltp(self, ticker: str) -> float:
        """Get Last Traded Price (LTP) for a stock"""
        if not self.smart_api:
            self.login()

        symbol_token = self._get_symbol_token(ticker)
        if not symbol_token:
            return 0.0

        try:
            # Correct API signature for getMarketData
            data = self.smart_api.getMarketData("LTP", {"NSE": [symbol_token]})

            if data and data.get('status') and data.get('data'):
                fetched = data['data'].get('fetched')
                if fetched and len(fetched) > 0:
                    return float(fetched[0].get('ltp', 0))
            return 0.0

        except Exception as e:
            print(f"❌ Error fetching LTP for {ticker}: {e}")
            return 0.0

    def get_quote(self, ticker: str) -> Dict:
        """Get full quote with OHLC, volume, bid/ask"""
        if not self.smart_api:
            self.login()

        symbol_token = self._get_symbol_token(ticker)
        if not symbol_token:
            return {}

        try:
            # Correct API signature for getMarketData
            data = self.smart_api.getMarketData("FULL", {"NSE": [symbol_token]})

            if data and data.get('status') and data.get('data'):
                fetched = data['data'].get('fetched')
                if fetched and len(fetched) > 0:
                    return fetched[0]
            return {}

        except Exception as e:
            print(f"❌ Error fetching quote for {ticker}: {e}")
            return {}

    # ==================== ORDER EXECUTION ====================

    def place_order(self, ticker: str, transaction_type: str, quantity: int,
                   order_type: str = 'MARKET', price: float = 0,
                   strategy: str = 'DAILY') -> Dict:
        """
        Place order on AngelOne

        Args:
            ticker: Stock symbol
            transaction_type: 'BUY' or 'SELL'
            quantity: Number of shares
            order_type: 'MARKET' or 'LIMIT'
            price: Limit price (for LIMIT orders)
            strategy: 'DAILY' or 'SWING'
        """
        if not self.smart_api:
            self.login()

        symbol_token = self._get_symbol_token(ticker)
        trading_symbol = ticker.replace('.NS', '')

        try:
            order_params = {
                "variety": "NORMAL",
                "tradingsymbol": trading_symbol,
                "symboltoken": symbol_token,
                "transactiontype": transaction_type,
                "exchange": "NSE",
                "ordertype": order_type,
                "producttype": "DELIVERY",
                "duration": "DAY",
                "quantity": str(quantity)
            }

            if order_type == 'LIMIT':
                order_params['price'] = str(price)

            response = self.smart_api.placeOrder(order_params)

            if response['status']:
                order_id = response['data']['orderid']

                # Log order to database
                self._log_order_to_db(
                    order_id=order_id,
                    ticker=ticker,
                    strategy=strategy,
                    transaction_type=transaction_type,
                    quantity=quantity,
                    price=price,
                    order_type=order_type,
                    status='PLACED'
                )

                print(f"✅ Order placed: {transaction_type} {quantity} {ticker} @ {order_type}")
                return {'success': True, 'order_id': order_id, 'message': response['message']}
            else:
                print(f"❌ Order failed: {response}")
                return {'success': False, 'message': response.get('message', 'Unknown error')}

        except Exception as e:
            print(f"❌ Order placement error: {e}")
            return {'success': False, 'message': str(e)}

    def modify_order(self, order_id: str, quantity: int = None, price: float = None,
                    order_type: str = None) -> Dict:
        """Modify existing order"""
        if not self.smart_api:
            self.login()

        try:
            modify_params = {"orderid": order_id, "variety": "NORMAL"}

            if quantity:
                modify_params['quantity'] = str(quantity)
            if price:
                modify_params['price'] = str(price)
            if order_type:
                modify_params['ordertype'] = order_type

            response = self.smart_api.modifyOrder(modify_params)

            if response['status']:
                self._update_order_status_in_db(order_id, 'MODIFIED')
                return {'success': True, 'message': response['message']}
            else:
                return {'success': False, 'message': response.get('message')}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def cancel_order(self, order_id: str) -> Dict:
        """Cancel pending order"""
        if not self.smart_api:
            self.login()

        try:
            response = self.smart_api.cancelOrder(order_id, "NORMAL")

            if response['status']:
                self._update_order_status_in_db(order_id, 'CANCELLED')
                return {'success': True, 'message': response['message']}
            else:
                return {'success': False, 'message': response.get('message')}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def get_order_status(self, order_id: str) -> Dict:
        """Get order status from AngelOne"""
        if not self.smart_api:
            self.login()

        try:
            response = self.smart_api.orderBook()

            if response['status'] and response['data']:
                for order in response['data']:
                    if order['orderid'] == order_id:
                        # Update DB with latest status
                        self._update_order_status_in_db(order_id, order['status'])
                        return order
            return {}
        except Exception as e:
            print(f"❌ Error fetching order status: {e}")
            return {}

    # ==================== HELPER FUNCTIONS ====================

    def _get_symbol_token(self, ticker: str) -> str:
        """
        Convert ticker to AngelOne symbol token using database lookup

        Args:
            ticker: Stock symbol (e.g., 'SBIN.NS', 'RELIANCE.NS')

        Returns:
            AngelOne exchange token (numeric string)
        """
        # Convert ticker format: SBIN.NS -> SBIN-EQ
        if ticker.endswith('.NS'):
            symbol = ticker.replace('.NS', '-EQ')
        elif ticker.endswith('.BO'):
            symbol = ticker.replace('.BO', '-EQ')
        else:
            symbol = ticker

        # Lookup in database
        try:
            from scripts.db_connection import get_db_cursor

            with get_db_cursor() as cur:
                cur.execute("""
                    SELECT token FROM angelone_symbols
                    WHERE symbol = %s AND exch_seg = 'NSE'
                    LIMIT 1
                """, (symbol,))

                result = cur.fetchone()
                if result:
                    return result['token']
                else:
                    # Fallback: try without -EQ suffix
                    base_symbol = symbol.replace('-EQ', '')
                    cur.execute("""
                        SELECT token FROM angelone_symbols
                        WHERE symbol LIKE %s AND exch_seg = 'NSE'
                        LIMIT 1
                    """, (f"{base_symbol}%",))

                    result = cur.fetchone()
                    if result:
                        return result['token']

            print(f"⚠️  Symbol {ticker} not found in database")
            return None

        except Exception as e:
            print(f"❌ Error looking up symbol {ticker}: {e}")
            return None

    def _log_order_to_db(self, order_id: str, ticker: str, strategy: str,
                        transaction_type: str, quantity: int, price: float,
                        order_type: str, status: str):
        """Log order to PostgreSQL"""
        with get_db_cursor() as cur:
            cur.execute("""
                INSERT INTO angelone_orders
                (order_id, ticker, strategy, transaction_type, quantity, price,
                 order_type, status, exchange)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'NSE')
            """, (order_id, ticker, strategy, transaction_type, quantity,
                  price, order_type, status))

    def _update_order_status_in_db(self, order_id: str, status: str):
        """Update order status in database"""
        with get_db_cursor() as cur:
            cur.execute("""
                UPDATE angelone_orders
                SET status = %s
                WHERE order_id = %s
            """, (status, order_id))

# Singleton instance
_angelone_instance = None

def get_angelone_api() -> AngelOneAPI:
    """Get singleton AngelOne API instance"""
    global _angelone_instance
    if _angelone_instance is None:
        _angelone_instance = AngelOneAPI()
        _angelone_instance.login()
    return _angelone_instance
