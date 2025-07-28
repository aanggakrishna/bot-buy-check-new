# Configuration file for the Telegram bot

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', 0))

# Ethereum Configuration
ETH_NODE_URL = os.getenv('ETH_NODE_URL')
TOKEN_ADDRESSES = os.getenv('TOKEN_ADDRESSES', '').split(',')

# API Keys
ETHPLORER_API_KEY = os.getenv('ETHPLORER_API_KEY')

# Uniswap Contracts
UNISWAP_V2_FACTORY = '0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f'
UNISWAP_V2_ROUTER = '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D'
UNISWAP_V3_FACTORY = '0x1F98431c8aD98523631AE4a59f267346ea31F984'

# WETH Address
WETH_ADDRESS = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'

# Database Configuration
DATABASE_PATH = 'bot_data.db'

# DexScreener API
DEXSCREENER_API_URL = 'https://api.dexscreener.com/latest/dex'

# Ethplorer API
ETHPLORER_API_URL = 'https://api.ethplorer.io'

# Etherscan URLs
ETHERSCAN_TX_URL = 'https://etherscan.io/tx/'
ETHERSCAN_ADDRESS_URL = 'https://etherscan.io/address/'

# Fresh wallet threshold (in days)
FRESH_WALLET_THRESHOLD = 30

# Swing trader threshold (number of token sales in last 24h)
SWING_TRADER_THRESHOLD = 3