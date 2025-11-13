#!/usr/bin/env python3
"""
Angel One broker integration for live trading
Handles authentication, order placement, GTT orders, and portfolio sync
"""

import os
import json
import pyotp
from datetime import datetime
from SmartApi import SmartConnect
from dotenv import load_dotenv

load_dotenv()

class AngelOneBroker:
    def __init__(self):
        self.api_key = os.getenv("ANGELONE_API_KEY")
        self.client_id = os.getenv("ANGELONE_CLIENT_ID")
        self.password = os.getenv("ANGELONE_PASSWORD")
        self.totp_secret = os.getenv("ANGELONE_TOTP_SECRET")

        self.smartApi = None
        self.auth_token = None
        self.refresh_token = None
        self.feed_token = None

        if not all([self.api_key, self.client_id, self.password, self.totp_secret]):
            raise ValueError("Angel One credentials not found in .env file")

    def login(self):
        """Login to Angel One and get auth tokens"""
        try:
            self.smartApi = SmartConnect(api_key=self.api_key)

            # Generate TOTP
            totp = pyotp.TOTP(self.totp_secret).now()

            # Login
            data = self.smartApi.generateSession(
                clientCode=self.client_id,
                password=self.password,
                totp=totp
            )

            if data['status']:
                self.auth_token = data['data']['jwtToken']
                self.refresh_token = data['data']['refreshToken']
                self.feed_token = self.smartApi.getfeedToken()
                print(f"✅ Angel One login successful")
                return True
            else:
                print(f"❌ Login failed: {data.get('message', 'Unknown error')}")
                return False

        except Exception as e:
            print(f"❌ Login error: {str(e)}")
            return False

    def get_profile(self):
        """Get user profile"""
        try:
            profile = self.smartApi.getProfile(self.refresh_token)
            if profile['status']:
                return profile['data']
            return None
        except Exception as e:
            print(f"❌ Error getting profile: {str(e)}")
            return None

    def get_funds(self):
        """Get available funds"""
        try:
            funds = self.smartApi.rmsLimit()
            if funds['status']:
                return funds['data']
            return None
        except Exception as e:
            print(f"❌ Error getting funds: {str(e)}")
            return None

    def get_ltp(self, exchange, symbol, token):
        """Get Last Traded Price"""
        try:
            ltp_data = self.smartApi.ltpData(exchange, symbol, token)
            if ltp_data['status']:
                return ltp_data['data']['ltp']
            return None
        except Exception as e:
            print(f"❌ Error getting LTP: {str(e)}")
            return None

    def search_scrip(self, symbol):
        """
        Search for scrip to get exchange and token
        Example: INFY.NS -> {exchange: NSE, token: 1594, symbol: INFY-EQ}
        """
        try:
            # Remove .NS/.BO suffix for Angel One
            clean_symbol = symbol.replace('.NS', '').replace('.BO', '')

            # Search in master data
            search_result = self.smartApi.searchScrip('NSE', clean_symbol)

            if search_result['status'] and search_result['data']:
                # Find the -EQ symbol (equity)
                for scrip in search_result['data']:
                    if scrip.get('tradingsymbol', '').endswith('-EQ'):
                        return {
                            'exchange': scrip.get('exchange', 'NSE'),
                            'token': scrip.get('symboltoken', scrip.get('token')),
                            'symbol': scrip.get('tradingsymbol'),
                            'name': scrip.get('tradingsymbol', clean_symbol)
                        }

                # Fallback to first result if no -EQ found
                scrip = search_result['data'][0]
                return {
                    'exchange': scrip.get('exchange', 'NSE'),
                    'token': scrip.get('symboltoken', scrip.get('token')),
                    'symbol': scrip.get('tradingsymbol'),
                    'name': scrip.get('tradingsymbol', clean_symbol)
                }

            print(f"❌ Symbol {symbol} not found")
            return None

        except Exception as e:
            print(f"❌ Error searching scrip {symbol}: {str(e)}")
            return None

    def place_order(self, symbol, quantity, price=None, order_type='MARKET',
                   transaction_type='BUY', product_type='DELIVERY'):
        """
        Place an order

        Args:
            symbol: Stock symbol (e.g., 'INFY.NS')
            quantity: Number of shares
            price: Limit price (None for market orders)
            order_type: 'MARKET' or 'LIMIT'
            transaction_type: 'BUY' or 'SELL'
            product_type: 'DELIVERY' or 'INTRADAY'
        """
        try:
            # Search for scrip details
            scrip = self.search_scrip(symbol)
            if not scrip:
                return None

            order_params = {
                "variety": "NORMAL",
                "tradingsymbol": scrip['symbol'],
                "symboltoken": scrip['token'],
                "transactiontype": transaction_type,
                "exchange": scrip['exchange'],
                "ordertype": order_type,
                "producttype": product_type,
                "duration": "DAY",
                "quantity": str(quantity)
            }

            if order_type == 'LIMIT' and price:
                order_params['price'] = str(price)

            response = self.smartApi.placeOrder(order_params)

            if response['status']:
                order_id = response['data']['orderid']
                print(f"✅ Order placed: {transaction_type} {quantity} {symbol} @ {price if price else 'MARKET'}")
                print(f"   Order ID: {order_id}")
                return order_id
            else:
                print(f"❌ Order failed: {response.get('message', 'Unknown error')}")
                return None

        except Exception as e:
            print(f"❌ Error placing order: {str(e)}")
            return None

    def place_gtt_order(self, symbol, quantity, trigger_price, limit_price,
                       transaction_type='SELL', order_type='LIMIT'):
        """
        Place GTT (Good Till Triggered) order for SL/TP

        Args:
            symbol: Stock symbol
            quantity: Number of shares
            trigger_price: Price at which order triggers (SL or TP)
            limit_price: Limit price for the order
            transaction_type: 'BUY' or 'SELL'
            order_type: 'LIMIT' or 'MARKET'
        """
        try:
            scrip = self.search_scrip(symbol)
            if not scrip:
                return None

            gtt_params = {
                "tradingsymbol": scrip['symbol'],
                "symboltoken": scrip['token'],
                "exchange": scrip['exchange'],
                "transactiontype": transaction_type,
                "producttype": "DELIVERY",
                "price": str(limit_price),
                "qty": str(quantity),
                "triggerprice": str(trigger_price),
                "disclosedqty": "0"
            }

            response = self.smartApi.gttCreateRule(gtt_params)

            if response['status']:
                gtt_id = response['data']['id']
                print(f"✅ GTT order placed: {transaction_type} {quantity} {symbol}")
                print(f"   Trigger: ₹{trigger_price} | Limit: ₹{limit_price}")
                print(f"   GTT ID: {gtt_id}")
                return gtt_id
            else:
                print(f"❌ GTT order failed: {response.get('message', 'Unknown error')}")
                return None

        except Exception as e:
            print(f"❌ Error placing GTT order: {str(e)}")
            return None

    def get_order_book(self):
        """Get all orders"""
        try:
            orders = self.smartApi.orderBook()
            if orders['status']:
                return orders['data']
            return None
        except Exception as e:
            print(f"❌ Error getting order book: {str(e)}")
            return None

    def get_positions(self):
        """Get current positions"""
        try:
            positions = self.smartApi.position()
            if positions['status']:
                return positions['data']
            return None
        except Exception as e:
            print(f"❌ Error getting positions: {str(e)}")
            return None

    def get_holdings(self):
        """Get holdings (delivery positions)"""
        try:
            holdings = self.smartApi.holding()
            if holdings['status']:
                return holdings['data']
            return None
        except Exception as e:
            print(f"❌ Error getting holdings: {str(e)}")
            return None

    def cancel_order(self, order_id, variety='NORMAL'):
        """Cancel an order"""
        try:
            response = self.smartApi.cancelOrder(order_id, variety)
            if response['status']:
                print(f"✅ Order {order_id} cancelled")
                return True
            else:
                print(f"❌ Cancel failed: {response.get('message', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"❌ Error cancelling order: {str(e)}")
            return False

    def get_gtt_list(self):
        """Get all GTT orders"""
        try:
            gtt_list = self.smartApi.gttList()
            if gtt_list['status']:
                return gtt_list['data']
            return None
        except Exception as e:
            print(f"❌ Error getting GTT list: {str(e)}")
            return None

    def cancel_gtt_order(self, gtt_id):
        """Cancel a GTT order"""
        try:
            response = self.smartApi.gttCancelRule(gtt_id)
            if response['status']:
                print(f"✅ GTT order {gtt_id} cancelled")
                return True
            else:
                print(f"❌ GTT cancel failed: {response.get('message', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"❌ Error cancelling GTT: {str(e)}")
            return False


def test_connection():
    """Test Angel One connection and display account info"""
    try:
        broker = AngelOneBroker()

        print("=" * 60)
        print("ANGEL ONE BROKER TEST")
        print("=" * 60)

        # Login
        if not broker.login():
            print("❌ Login failed")
            return False

        # Get profile
        profile = broker.get_profile()
        if profile:
            print(f"\n📋 Profile:")
            print(f"   Client ID: {profile.get('clientcode', 'N/A')}")
            print(f"   Name: {profile.get('name', 'N/A')}")
            print(f"   Email: {profile.get('email', 'N/A')}")

        # Get funds
        funds = broker.get_funds()
        if funds:
            print(f"\n💰 Funds:")
            print(f"   Available: ₹{float(funds.get('availablecash', 0)):,.2f}")
            print(f"   Used: ₹{float(funds.get('utiliseddebits', 0)):,.2f}")

        # Get holdings
        holdings = broker.get_holdings()
        if holdings:
            print(f"\n📊 Holdings: {len(holdings)} positions")
            for holding in holdings[:5]:  # Show first 5
                print(f"   • {holding.get('tradingsymbol', 'N/A')}: {holding.get('quantity', 0)} shares")

        print("\n" + "=" * 60)
        print("✅ Connection test successful!")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        return False


if __name__ == "__main__":
    test_connection()
