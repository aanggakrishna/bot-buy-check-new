# Module for fetching data from DexScreener API

import requests
import json
from config import DEXSCREENER_API_URL

class DexData:
    def __init__(self):
        self.api_url = DEXSCREENER_API_URL
    
    def get_token_info(self, token_address):
        """
        Get token information from DexScreener API
        """
        try:
            url = f"{self.api_url}/tokens/{token_address}"
            response = requests.get(url)
            data = response.json()
            
            if 'pairs' not in data or not data['pairs']:
                return None
            
            # Get the first pair (usually the most liquid one)
            pair = data['pairs'][0]
            
            return {
                'name': pair.get('baseToken', {}).get('name'),
                'symbol': pair.get('baseToken', {}).get('symbol'),
                'price_usd': pair.get('priceUsd'),
                'price_eth': pair.get('priceNative'),
                'liquidity_usd': pair.get('liquidity', {}).get('usd'),
                'fdv': pair.get('fdv'),  # Fully Diluted Valuation
                'market_cap': pair.get('marketCap'),
                'holders': None,  # DexScreener doesn't provide holders count
                'dexscreener_url': f"https://dexscreener.com/ethereum/{pair.get('pairAddress')}"
            }
        except Exception as e:
            print(f"Error fetching token info from DexScreener: {e}")
            return None
    
    def get_eth_price(self):
        """
        Get current ETH price in USD
        """
        try:
            # Using WETH as a reference
            url = f"{self.api_url}/tokens/ethereum/0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
            response = requests.get(url)
            data = response.json()
            
            if 'pairs' not in data or not data['pairs']:
                return None
            
            # Get the first pair with USDC or USDT
            for pair in data['pairs']:
                if pair.get('quoteToken', {}).get('symbol') in ['USDC', 'USDT']:
                    return float(pair.get('priceUsd', 0))
            
            return float(data['pairs'][0].get('priceUsd', 0))
        except Exception as e:
            print(f"Error fetching ETH price: {e}")
            return None