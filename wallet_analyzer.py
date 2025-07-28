# Module for analyzing Ethereum wallets

import requests
import json
from datetime import datetime, timedelta
import time
from config import ETHPLORER_API_KEY, ETHPLORER_API_URL, FRESH_WALLET_THRESHOLD, SWING_TRADER_THRESHOLD

class WalletAnalyzer:
    def __init__(self):
        self.api_key = ETHPLORER_API_KEY
        self.api_url = ETHPLORER_API_URL
    
    def get_wallet_info(self, wallet_address):
        """
        Get wallet information including age, token holdings, and transaction history
        """
        try:
            # Get wallet info
            url = f"{self.api_url}/getAddressInfo/{wallet_address}?apiKey={self.api_key}"
            response = requests.get(url)
            data = response.json()
            
            # Get wallet age
            wallet_age = self._calculate_wallet_age(data)
            
            # Get token holdings
            token_holdings = self._get_token_holdings(data)
            
            # Determine if wallet is a swing trader
            is_swing_trader, trading_info = self._analyze_trading_behavior(wallet_address)
            
            return {
                'address': wallet_address,
                'is_fresh_wallet': wallet_age < FRESH_WALLET_THRESHOLD,
                'wallet_age_days': wallet_age,
                'token_holdings': token_holdings,
                'is_swing_trader': is_swing_trader,
                'trading_info': trading_info
            }
        except Exception as e:
            print(f"Error analyzing wallet: {e}")
            return None
    
    def _calculate_wallet_age(self, wallet_data):
        """
        Calculate wallet age in days
        """
        try:
            # Try to get the first transaction timestamp
            if 'ETH' in wallet_data and 'transfersCount' in wallet_data['ETH'] and wallet_data['ETH']['transfersCount'] > 0:
                # Get first transaction
                address = wallet_data.get('address')
                url = f"{self.api_url}/getAddressTransactions/{address}?apiKey={self.api_key}&limit=1&sort=asc"
                response = requests.get(url)
                transactions = response.json()
                
                if transactions and len(transactions) > 0:
                    first_tx_timestamp = transactions[0].get('timestamp', 0)
                    wallet_creation_date = datetime.fromtimestamp(first_tx_timestamp)
                    age_days = (datetime.now() - wallet_creation_date).days
                    return age_days
            
            # If we can't determine the age, return a large number
            return 999
        except Exception as e:
            print(f"Error calculating wallet age: {e}")
            return 999
    
    def _get_token_holdings(self, wallet_data):
        """
        Get token holdings with USD values
        """
        holdings = []
        
        try:
            if 'tokens' in wallet_data:
                for token in wallet_data['tokens']:
                    token_info = token.get('tokenInfo', {})
                    
                    # Skip tokens without proper info
                    if not token_info.get('symbol') or not token_info.get('name'):
                        continue
                    
                    # Calculate token balance
                    decimals = int(token_info.get('decimals', 18))
                    balance = float(token.get('balance', 0)) / (10 ** decimals)
                    
                    # Get USD value if available
                    price_usd = float(token_info.get('price', {}).get('rate', 0))
                    usd_value = balance * price_usd
                    
                    # Only include tokens with significant value (> $10)
                    if usd_value > 10:
                        holdings.append({
                            'symbol': token_info.get('symbol'),
                            'name': token_info.get('name'),
                            'balance': balance,
                            'usd_value': usd_value
                        })
            
            # Sort by USD value (highest first)
            holdings.sort(key=lambda x: x['usd_value'], reverse=True)
            
            # Limit to top 5 holdings
            return holdings[:5]
        except Exception as e:
            print(f"Error getting token holdings: {e}")
            return []
    
    def _analyze_trading_behavior(self, wallet_address):
        """
        Analyze if the wallet is a swing trader based on recent transactions
        """
        try:
            # Get recent transactions (last 24 hours)
            url = f"{self.api_url}/getAddressHistory/{wallet_address}?apiKey={self.api_key}&type=transfer&limit=50"
            response = requests.get(url)
            history = response.json()
            
            if 'operations' not in history:
                return False, "No recent transactions"
            
            # Filter transactions in the last 24 hours
            now = datetime.now()
            yesterday = now - timedelta(days=1)
            yesterday_timestamp = int(yesterday.timestamp())
            
            recent_sells = 0
            tokens_sold = set()
            
            for op in history['operations']:
                # Skip old transactions
                if op.get('timestamp', 0) < yesterday_timestamp:
                    continue
                
                # Check if this is a token sale (transfer from this address)
                if op.get('from') == wallet_address.lower():
                    recent_sells += 1
                    if 'tokenInfo' in op and 'symbol' in op['tokenInfo']:
                        tokens_sold.add(op['tokenInfo']['symbol'])
            
            # In the _analyze_trading_behavior method
            is_swing_trader = recent_sells >= SWING_TRADER_THRESHOLD
            trading_info = f"Sold {recent_sells} tokens in last 24h"
            
            return is_swing_trader, trading_info
        except Exception as e:
            print(f"Error analyzing trading behavior: {e}")
            return False, "Could not analyze trading behavior"
    
    def get_token_trading_info(self, wallet_address, token_address):
        """
        Get detailed trading information for a specific token
        """
        try:
            # Get token transactions for this wallet
            url = f"{self.api_url}/getAddressHistory/{wallet_address}?apiKey={self.api_key}&token={token_address}&type=transfer&limit=100"
            response = requests.get(url)
            history = response.json()
            
            if 'operations' not in history:
                return {
                    'trade_count': 0,
                    'bought_amount': 0,
                    'bought_value_usd': 0,
                    'sold_amount': 0,
                    'sold_value_usd': 0,
                    'remaining_tokens': 0,
                    'estimated_pnl': 0,
                    'pnl_percentage': 0
                }
            
            # Process transactions
            buys = []
            sells = []
            token_decimals = 18  # Default
            token_symbol = "Unknown"
            
            for op in history['operations']:
                if 'tokenInfo' in op:
                    token_decimals = int(op['tokenInfo'].get('decimals', 18))
                    token_symbol = op['tokenInfo'].get('symbol', 'Unknown')
                
                # Buy transaction (tokens coming in)
                if op.get('to') == wallet_address.lower():
                    amount = float(op.get('value', 0)) / (10 ** token_decimals)
                    buys.append({
                        'amount': amount,
                        'timestamp': op.get('timestamp', 0),
                        'price_usd': op.get('usdPrice', 0)
                    })
                
                # Sell transaction (tokens going out)
                elif op.get('from') == wallet_address.lower():
                    amount = float(op.get('value', 0)) / (10 ** token_decimals)
                    sells.append({
                        'amount': amount,
                        'timestamp': op.get('timestamp', 0),
                        'price_usd': op.get('usdPrice', 0)
                    })
            
            # Calculate totals
            total_bought = sum(buy['amount'] for buy in buys)
            total_bought_value = sum(buy['amount'] * buy['price_usd'] for buy in buys if buy['price_usd'])
            
            total_sold = sum(sell['amount'] for sell in sells)
            total_sold_value = sum(sell['amount'] * sell['price_usd'] for sell in sells if sell['price_usd'])
            
            remaining_tokens = total_bought - total_sold
            
            # Get current token price
            current_price = 0
            try:
                token_url = f"{self.api_url}/getTokenInfo/{token_address}?apiKey={self.api_key}"
                token_response = requests.get(token_url)
                token_data = token_response.json()
                current_price = float(token_data.get('price', {}).get('rate', 0))
            except Exception as e:
                print(f"Error getting current token price: {e}")
            
            # Calculate PNL
            current_value = remaining_tokens * current_price
            realized_pnl = total_sold_value - (total_sold / total_bought * total_bought_value if total_bought > 0 else 0)
            unrealized_pnl = current_value - (remaining_tokens / total_bought * total_bought_value if total_bought > 0 else 0)
            total_pnl = realized_pnl + unrealized_pnl
            
            # Calculate PNL percentage
            pnl_percentage = (total_pnl / total_bought_value * 100) if total_bought_value > 0 else 0
            
            return {
                'token_symbol': token_symbol,
                'trade_count': len(buys) + len(sells),
                'buy_count': len(buys),
                'sell_count': len(sells),
                'bought_amount': total_bought,
                'bought_value_usd': total_bought_value,
                'sold_amount': total_sold,
                'sold_value_usd': total_sold_value,
                'remaining_tokens': remaining_tokens,
                'current_token_price': current_price,
                'current_value_usd': current_value,
                'realized_pnl': realized_pnl,
                'unrealized_pnl': unrealized_pnl,
                'total_pnl': total_pnl,
                'pnl_percentage': pnl_percentage
            }
        except Exception as e:
            print(f"Error getting token trading info: {e}")
            return None