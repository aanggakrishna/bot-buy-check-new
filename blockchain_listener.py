# Module for listening to blockchain events

import json
import time
from web3 import Web3
from web3.middleware import geth_poa_middleware
from web3.exceptions import BlockNotFound
import asyncio
from datetime import datetime

from config import ETH_NODE_URL, UNISWAP_V2_FACTORY, UNISWAP_V2_ROUTER, UNISWAP_V3_FACTORY, WETH_ADDRESS

# Uniswap V2 ABI
UNISWAP_V2_PAIR_ABI = json.loads('''[
    {"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"sender","type":"address"},{"indexed":false,"internalType":"uint256","name":"amount0In","type":"uint256"},{"indexed":false,"internalType":"uint256","name":"amount1In","type":"uint256"},{"indexed":false,"internalType":"uint256","name":"amount0Out","type":"uint256"},{"indexed":false,"internalType":"uint256","name":"amount1Out","type":"uint256"},{"indexed":true,"internalType":"address","name":"to","type":"address"}],"name":"Swap","type":"event"}
]''')

# Uniswap V2 Factory ABI
UNISWAP_V2_FACTORY_ABI = json.loads('''[
    {"inputs":[{"internalType":"address","name":"tokenA","type":"address"},{"internalType":"address","name":"tokenB","type":"address"}],"name":"getPair","outputs":[{"internalType":"address","name":"pair","type":"address"}],"stateMutability":"view","type":"function"}
]''')

# ERC20 ABI for token info
ERC20_ABI = json.loads('''[
    {"constant":true,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"payable":false,"stateMutability":"view","type":"function"},
    {"constant":true,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"payable":false,"stateMutability":"view","type":"function"},
    {"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"payable":false,"stateMutability":"view","type":"function"}
]''')

class BlockchainListener:
    def __init__(self, token_addresses, callback):
        self.w3 = Web3(Web3.HTTPProvider(ETH_NODE_URL))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.token_addresses = [addr.lower() for addr in token_addresses if addr]
        self.callback = callback
        self.factory_contract = self.w3.eth.contract(address=self.w3.to_checksum_address(UNISWAP_V2_FACTORY), abi=UNISWAP_V2_FACTORY_ABI)
        self.weth_address = WETH_ADDRESS.lower()
        self.pairs = {}
        self.initialize_pairs()
    
    def initialize_pairs(self):
        """
        Initialize Uniswap pairs for monitored tokens
        """
        for token_address in self.token_addresses:
            try:
                # Get pair address for token/WETH
                pair_address = self.factory_contract.functions.getPair(
                    self.w3.to_checksum_address(token_address),
                    self.w3.to_checksum_address(self.weth_address)
                ).call()
                
                if pair_address and pair_address != '0x0000000000000000000000000000000000000000':
                    # Create pair contract
                    pair_contract = self.w3.eth.contract(address=pair_address, abi=UNISWAP_V2_PAIR_ABI)
                    
                    # Get token info
                    token_contract = self.w3.eth.contract(address=self.w3.to_checksum_address(token_address), abi=ERC20_ABI)
                    token_name = token_contract.functions.name().call()
                    token_symbol = token_contract.functions.symbol().call()
                    token_decimals = token_contract.functions.decimals().call()
                    
                    # Store pair info
                    self.pairs[pair_address.lower()] = {
                        'contract': pair_contract,
                        'token_address': token_address,
                        'token_name': token_name,
                        'token_symbol': token_symbol,
                        'token_decimals': token_decimals
                    }
                    
                    print(f"Initialized pair for {token_name} ({token_symbol}): {pair_address}")
            except Exception as e:
                print(f"Error initializing pair for token {token_address}: {e}")
    
    def update_monitored_tokens(self, token_addresses):
        """
        Update the list of monitored tokens
        """
        self.token_addresses = [addr.lower() for addr in token_addresses if addr]
        self.pairs = {}
        self.initialize_pairs()
    
    # Tambahkan di metode listen_for_swaps
    async def listen_for_swaps(self):
        """Listen for swap events on Uniswap pairs"""
        print("Starting to listen for swap events...")
        last_block = self.w3.eth.block_number
        
        # Tambahkan flag untuk kontrol loop
        self.running = True
        
        while self.running:
            try:
                # Cek apakah ada sinyal untuk berhenti setiap iterasi
                current_block = self.w3.eth.block_number
                
                if current_block > last_block:
                    print(f"Checking blocks {last_block+1} to {current_block}")
                    
                    for block_number in range(last_block + 1, current_block + 1):
                        await self.check_block_for_swaps(block_number)
                    
                    last_block = current_block
                
                # Sleep dengan timeout pendek agar bisa merespons sinyal
                await asyncio.sleep(5)  # Kurangi dari 12 detik menjadi 5 detik
            except Exception as e:
                print(f"Error in blockchain listener: {e}")
                await asyncio.sleep(10)  # Kurangi dari 30 detik menjadi 10 detik
    
    # Tambahkan metode untuk menghentikan listener
    def stop(self):
        """Stop the blockchain listener"""
        self.running = False
    
    async def check_block_for_swaps(self, block_number):
        """
        Check a specific block for swap events
        """
        try:
            block = self.w3.eth.get_block(block_number, full_transactions=True)
            
            for tx in block['transactions']:
                # Check if transaction is to Uniswap Router
                if tx['to'] and tx['to'].lower() == UNISWAP_V2_ROUTER.lower():
                    # Get transaction receipt
                    receipt = self.w3.eth.get_transaction_receipt(tx['hash'])
                    
                    # Process logs for swap events
                    for log in receipt['logs']:
                        # Check if log is from a monitored pair
                        if 'address' in log and log['address'].lower() in self.pairs:
                            pair_info = self.pairs[log['address'].lower()]
                            pair_contract = pair_info['contract']
                            
                            # Try to parse the log as a Swap event
                            try:
                                parsed_log = pair_contract.events.Swap().process_log(log)
                                event_args = parsed_log['args']
                                
                                # Check if this is a buy (ETH/WETH to token)
                                is_buy = self._is_token_buy(event_args, pair_info['token_address'])
                                
                                if is_buy:
                                    # Process the buy event
                                    await self._process_buy_event(
                                        tx['hash'].hex(),
                                        event_args,
                                        pair_info,
                                        tx['from']
                                    )
                            except Exception as e:
                                # Not a Swap event or error parsing
                                pass
        except BlockNotFound:
            print(f"Block {block_number} not found")
        except Exception as e:
            print(f"Error checking block {block_number}: {e}")
    
    def _is_token_buy(self, event_args, token_address):
        """
        Determine if a swap event is a token buy (ETH/WETH to token)
        """
        # For a buy: amount0In or amount1In should be WETH, and amount0Out or amount1Out should be token
        # This is a simplified check and might need adjustment based on pair order
        if event_args['amount0In'] > 0 and event_args['amount1Out'] > 0:
            # WETH is token0, target token is token1
            return True
        elif event_args['amount1In'] > 0 and event_args['amount0Out'] > 0:
            # WETH is token1, target token is token0
            return True
        return False
    
    async def _process_buy_event(self, tx_hash, event_args, pair_info, buyer_address):
        """
        Process a token buy event
        """
        try:
            # Extract event data
            token_address = pair_info['token_address']
            token_name = pair_info['token_name']
            token_symbol = pair_info['token_symbol']
            token_decimals = pair_info['token_decimals']
            
            # Calculate amounts
            eth_amount = 0
            token_amount = 0
            
            if event_args['amount0In'] > 0 and event_args['amount1Out'] > 0:
                # WETH is token0, target token is token1
                eth_amount = event_args['amount0In'] / 10**18  # WETH has 18 decimals
                token_amount = event_args['amount1Out'] / 10**token_decimals
            elif event_args['amount1In'] > 0 and event_args['amount0Out'] > 0:
                # WETH is token1, target token is token0
                eth_amount = event_args['amount1In'] / 10**18  # WETH has 18 decimals
                token_amount = event_args['amount0Out'] / 10**token_decimals
            
            # Create buy event data
            buy_event = {
                'tx_hash': tx_hash,
                'buyer': buyer_address,
                'token_address': token_address,
                'token_name': token_name,
                'token_symbol': token_symbol,
                'eth_amount': eth_amount,
                'token_amount': token_amount,
                'timestamp': datetime.now().timestamp()
            }
            
            # Call the callback function with the buy event
            await self.callback(buy_event)
        except Exception as e:
            print(f"Error processing buy event: {e}")