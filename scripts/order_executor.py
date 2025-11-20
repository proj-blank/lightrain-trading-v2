"""
Order Executor - Handles both paper trading (simulation) and live orders
Seamless switch between modes via LIVE_ORDERS_ENABLED environment variable
"""
import os
from datetime import datetime
from typing import Dict
import sys
sys.path.insert(0, '/Users/brosshack/project_blank/LightRain/LightRain')
from scripts.angelone_api import get_angelone_api
from scripts.db_connection import get_db_cursor, log_trade, add_position, close_position, update_capital

LIVE_ORDERS_ENABLED = os.getenv('LIVE_ORDERS_ENABLED', 'false').lower() == 'true'

class OrderExecutor:
    """Unified order executor for paper and live trading"""

    def __init__(self, strategy: str):
        self.strategy = strategy
        self.angelone_api = get_angelone_api() if LIVE_ORDERS_ENABLED else None

    def execute_buy(self, ticker: str, quantity: int, price: float, stop_loss: float,
                   take_profit: float, category: str) -> Dict:
        """
        Execute BUY order (paper or live based on config)

        Returns:
            {'success': bool, 'execution_price': float, 'message': str}
        """
        if LIVE_ORDERS_ENABLED:
            return self._execute_live_buy(ticker, quantity, price, stop_loss, take_profit, category)
        else:
            return self._execute_paper_buy(ticker, quantity, price, stop_loss, take_profit, category)

    def execute_sell(self, ticker: str, quantity: int, price: float, reason: str = "") -> Dict:
        """
        Execute SELL order (paper or live)

        Returns:
            {'success': bool, 'execution_price': float, 'pnl': float, 'message': str}
        """
        if LIVE_ORDERS_ENABLED:
            return self._execute_live_sell(ticker, quantity, price, reason)
        else:
            return self._execute_paper_sell(ticker, quantity, price, reason)

    # ==================== PAPER TRADING (SIMULATION) ====================

    def _execute_paper_buy(self, ticker: str, quantity: int, price: float,
                          stop_loss: float, take_profit: float, category: str) -> Dict:
        """Simulate BUY order - log to database as virtual position"""
        try:
            # Add position to database
            position_id = add_position(
                ticker=ticker,
                strategy=self.strategy,
                entry_price=price,
                quantity=quantity,
                stop_loss=stop_loss,
                take_profit=take_profit,
                category=category
            )

            # Log trade
            log_trade(
                ticker=ticker,
                strategy=self.strategy,
                signal='BUY',
                price=price,
                quantity=quantity,
                pnl=None,
                notes=f"[PAPER] Entry @ {price}",
                category=category
            )

            # Log simulated order
            self._log_simulated_order(ticker, 'BUY', quantity, price, 'MARKET', 'EXECUTED')

            print(f"📝 [PAPER] BUY {quantity} {ticker} @ ₹{price:.2f}")

            # Send Telegram alert
            from scripts.telegram_bot import send_telegram_message
            msg = f"📝 PAPER TRADE\n\n"
            msg += f"BUY {quantity} {ticker}\n"
            msg += f"Price: ₹{price:.2f}\n"
            msg += f"Stop Loss: ₹{stop_loss:.2f}\n"
            msg += f"Take Profit: ₹{take_profit:.2f}\n"
            msg += f"Category: {category}"
            send_telegram_message(msg)

            return {
                'success': True,
                'execution_price': price,
                'position_id': position_id,
                'message': f'Paper trade: BUY {quantity} shares @ ₹{price:.2f}',
                'mode': 'PAPER'
            }

        except Exception as e:
            print(f"❌ Paper BUY failed: {e}")
            return {'success': False, 'message': str(e), 'mode': 'PAPER'}

    def _execute_paper_sell(self, ticker: str, quantity: int, price: float, reason: str) -> Dict:
        """Simulate SELL order - close virtual position"""
        try:
            # Get position entry price to calculate P&L
            with get_db_cursor() as cur:
                cur.execute("""
                    SELECT entry_price FROM positions
                    WHERE ticker = %s AND strategy = %s AND status = 'HOLD'
                """, (ticker, self.strategy))
                result = cur.fetchone()

                if not result:
                    return {'success': False, 'message': f'No position found for {ticker}', 'mode': 'PAPER'}

                entry_price = float(result['entry_price'])

            # Calculate P&L
            pnl = round((price - entry_price) * quantity, 2)

            # Close position
            close_position(ticker, self.strategy, price, pnl)

            # Log trade
            log_trade(
                ticker=ticker,
                strategy=self.strategy,
                signal='SELL',
                price=price,
                quantity=quantity,
                pnl=pnl,
                notes=f"[PAPER] {reason}",
                category=None
            )

            # Update capital
            update_capital(self.strategy, pnl)

            # Log simulated order
            self._log_simulated_order(ticker, 'SELL', quantity, price, 'MARKET', 'EXECUTED')

            pnl_pct = ((price - entry_price) / entry_price) * 100
            print(f"📝 [PAPER] SELL {quantity} {ticker} @ ₹{price:.2f} | P&L: ₹{pnl:+,.2f} ({pnl_pct:+.2f}%)")

            # Send Telegram alert
            from scripts.telegram_bot import send_telegram_message
            msg = f"📝 PAPER TRADE\n\n"
            msg += f"SELL {quantity} {ticker}\n"
            msg += f"Price: ₹{price:.2f}\n"
            msg += f"P&L: ₹{pnl:+,.2f} ({pnl_pct:+.2f}%)\n"
            msg += f"Reason: {reason}"
            send_telegram_message(msg)

            return {
                'success': True,
                'execution_price': price,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'message': f'Paper trade: SELL {quantity} shares @ ₹{price:.2f}',
                'mode': 'PAPER'
            }

        except Exception as e:
            print(f"❌ Paper SELL failed: {e}")
            return {'success': False, 'message': str(e), 'mode': 'PAPER'}

    def _log_simulated_order(self, ticker: str, transaction_type: str, quantity: int,
                            price: float, order_type: str, status: str):
        """Log simulated order to angelone_orders table for tracking (optional)"""
        try:
            with get_db_cursor() as cur:
                order_id = f"PAPER_{datetime.now().strftime('%Y%m%d%H%M%S')}_{ticker}"
                cur.execute("""
                    INSERT INTO angelone_orders
                    (order_id, ticker, strategy, transaction_type, quantity, price,
                     order_type, status, exchange)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'NSE')
                """, (order_id, ticker, self.strategy, transaction_type, quantity,
                      price, order_type, status))
        except Exception as e:
            # Table doesn't exist or other DB error - non-critical, continue anyway
            pass

    # ==================== LIVE TRADING (REAL ORDERS) ====================

    def _execute_live_buy(self, ticker: str, quantity: int, price: float,
                         stop_loss: float, take_profit: float, category: str) -> Dict:
        """Execute real BUY order via AngelOne API"""
        try:
            # Place market order
            result = self.angelone_api.place_order(
                ticker=ticker,
                transaction_type='BUY',
                quantity=quantity,
                order_type='MARKET',
                strategy=self.strategy
            )

            if result['success']:
                # Get actual execution price from order status
                order_status = self.angelone_api.get_order_status(result['order_id'])
                execution_price = float(order_status.get('averageprice', price))

                # Add position to database
                position_id = add_position(
                    ticker=ticker,
                    strategy=self.strategy,
                    entry_price=execution_price,
                    quantity=quantity,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    category=category
                )

                # Log trade
                log_trade(
                    ticker=ticker,
                    strategy=self.strategy,
                    signal='BUY',
                    price=execution_price,
                    quantity=quantity,
                    pnl=None,
                    notes=f"[LIVE] Order ID: {result['order_id']}",
                    category=category
                )

                print(f"🔴 [LIVE] BUY {quantity} {ticker} @ ₹{execution_price:.2f} | Order: {result['order_id']}")

                return {
                    'success': True,
                    'execution_price': execution_price,
                    'position_id': position_id,
                    'order_id': result['order_id'],
                    'message': result['message'],
                    'mode': 'LIVE'
                }
            else:
                return {'success': False, 'message': result['message'], 'mode': 'LIVE'}

        except Exception as e:
            print(f"❌ Live BUY failed: {e}")
            return {'success': False, 'message': str(e), 'mode': 'LIVE'}

    def _execute_live_sell(self, ticker: str, quantity: int, price: float, reason: str) -> Dict:
        """Execute real SELL order via AngelOne API"""
        try:
            # Get entry price first
            with get_db_cursor() as cur:
                cur.execute("""
                    SELECT entry_price FROM positions
                    WHERE ticker = %s AND strategy = %s AND status = 'HOLD'
                """, (ticker, self.strategy))
                result_db = cur.fetchone()

                if not result_db:
                    return {'success': False, 'message': f'No position found for {ticker}', 'mode': 'LIVE'}

                entry_price = float(result_db['entry_price'])

            # Place market sell order
            result = self.angelone_api.place_order(
                ticker=ticker,
                transaction_type='SELL',
                quantity=quantity,
                order_type='MARKET',
                strategy=self.strategy
            )

            if result['success']:
                # Get actual execution price
                order_status = self.angelone_api.get_order_status(result['order_id'])
                execution_price = float(order_status.get('averageprice', price))

                # Calculate P&L
                pnl = round((execution_price - entry_price) * quantity, 2)

                # Close position
                close_position(ticker, self.strategy, execution_price, pnl)

                # Log trade
                log_trade(
                    ticker=ticker,
                    strategy=self.strategy,
                    signal='SELL',
                    price=execution_price,
                    quantity=quantity,
                    pnl=pnl,
                    notes=f"[LIVE] {reason} | Order: {result['order_id']}",
                    category=None
                )

                # Update capital
                update_capital(self.strategy, pnl)

                pnl_pct = ((execution_price - entry_price) / entry_price) * 100
                print(f"🔴 [LIVE] SELL {quantity} {ticker} @ ₹{execution_price:.2f} | P&L: ₹{pnl:+,.2f} ({pnl_pct:+.2f}%) | Order: {result['order_id']}")

                return {
                    'success': True,
                    'execution_price': execution_price,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'order_id': result['order_id'],
                    'message': result['message'],
                    'mode': 'LIVE'
                }
            else:
                return {'success': False, 'message': result['message'], 'mode': 'LIVE'}

        except Exception as e:
            print(f"❌ Live SELL failed: {e}")
            return {'success': False, 'message': str(e), 'mode': 'LIVE'}

def get_order_executor(strategy: str) -> OrderExecutor:
    """Factory function to get order executor"""
    return OrderExecutor(strategy)
