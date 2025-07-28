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
            
            is_swing_trader = recent_sells >= SWING_TRADER_THRESHOLD
            trading_info = f"Sold {recent_sells} tokens in last 24h"
            
            return is_swing_trader, trading_info
        except Exception as e:
            print(f"Error analyzing trading behavior: {e}")
            return False, "Could not analyze trading behavior"