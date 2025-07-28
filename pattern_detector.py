# Module for detecting trading patterns

import numpy as np
from datetime import datetime, timedelta
from config import PUMP_DUMP_PERCENT_THRESHOLD, PUMP_DUMP_TIME_WINDOW, ACCUMULATION_THRESHOLD, ACCUMULATION_TIME_WINDOW

class PatternDetector:
    def __init__(self, database):
        self.db = database
    
    def detect_patterns(self, token_address):
        """Detect trading patterns for a specific token"""
        patterns = []
        
        # Check for pump and dump pattern
        pump_dump = self.detect_pump_dump(token_address)
        if pump_dump:
            patterns.append(pump_dump)
        
        # Check for accumulation pattern
        accumulation = self.detect_accumulation(token_address)
        if accumulation:
            patterns.append(accumulation)
        
        return patterns
    
    def detect_pump_dump(self, token_address):
        """Detect pump and dump pattern"""
        # Get price history for the token
        price_history = self.db.get_token_price_history(token_address, hours=PUMP_DUMP_TIME_WINDOW)
        if len(price_history) < 2:
            return None
        
        # Convert to numpy arrays for easier analysis
        timestamps = np.array([p[0] for p in price_history])
        prices = np.array([p[1] for p in price_history])
        volumes = np.array([p[2] for p in price_history])
        
        # Find maximum price and its index
        max_price_idx = np.argmax(prices)
        max_price = prices[max_price_idx]
        max_price_time = timestamps[max_price_idx]
        
        # Find minimum price before the maximum
        if max_price_idx > 0:
            min_price_before = np.min(prices[:max_price_idx])
            min_before_idx = np.argmin(prices[:max_price_idx])
            min_price_before_time = timestamps[min_before_idx]
        else:
            min_price_before = prices[0]
            min_price_before_time = timestamps[0]
        
        # Find minimum price after the maximum
        if max_price_idx < len(prices) - 1:
            min_price_after = np.min(prices[max_price_idx+1:])
            min_after_idx = np.argmin(prices[max_price_idx+1:]) + max_price_idx + 1
            min_price_after_time = timestamps[min_after_idx]
        else:
            min_price_after = prices[-1]
            min_price_after_time = timestamps[-1]
        
        # Calculate price changes
        pump_percent = ((max_price - min_price_before) / min_price_before * 100) if min_price_before > 0 else 0
        dump_percent = ((max_price - min_price_after) / max_price * 100) if max_price > 0 else 0
        
        # Calculate volume changes
        avg_volume_before = np.mean(volumes[:max_price_idx]) if max_price_idx > 0 else volumes[0]
        max_volume = np.max(volumes)
        volume_increase = ((max_volume - avg_volume_before) / avg_volume_before * 100) if avg_volume_before > 0 else 0
        
        # Check if this is a pump and dump pattern
        is_pump_dump = (pump_percent >= PUMP_DUMP_PERCENT_THRESHOLD and 
                       dump_percent >= PUMP_DUMP_PERCENT_THRESHOLD and
                       volume_increase >= 50)  # Volume should increase significantly
        
        if is_pump_dump:
            return {
                'pattern_type': 'pump_dump',
                'token_address': token_address,
                'start_timestamp': min_price_before_time,
                'peak_timestamp': max_price_time,
                'end_timestamp': min_price_after_time,
                'start_price': float(min_price_before),
                'peak_price': float(max_price),
                'end_price': float(min_price_after),
                'pump_percent': float(pump_percent),
                'dump_percent': float(dump_percent),
                'volume_change': float(volume_increase),
                'wallet_count': 0  # This would require additional data
            }
        
        return None
    
    def detect_accumulation(self, token_address):
        """Detect accumulation pattern (multiple buys with little price movement)"""
        # This would require transaction data, which we can get from the blockchain_listener
        # For now, we'll implement a simplified version
        
        # Get recent buy transactions for this token
        recent_buys = self.get_recent_buys(token_address, hours=ACCUMULATION_TIME_WINDOW)
        if len(recent_buys) < ACCUMULATION_THRESHOLD:
            return None
        
        # Group buys by wallet to find wallets that are accumulating
        wallet_buys = {}
        for buy in recent_buys:
            wallet = buy['buyer']
            if wallet not in wallet_buys:
                wallet_buys[wallet] = []
            wallet_buys[wallet].append(buy)
        
        # Find wallets with multiple buys
        accumulating_wallets = {w: buys for w, buys in wallet_buys.items() if len(buys) >= 3}
        
        if accumulating_wallets:
            # Get price history to check if price has remained relatively stable
            price_history = self.db.get_token_price_history(token_address, hours=ACCUMULATION_TIME_WINDOW)
            if len(price_history) < 2:
                return None
            
            prices = np.array([p[1] for p in price_history])
            price_volatility = np.std(prices) / np.mean(prices) * 100  # Coefficient of variation as percentage
            
            # Low volatility (< 15%) suggests accumulation rather than pumping
            if price_volatility < 15:
                # Get the earliest and latest buy timestamps
                all_buys = [buy for buys in accumulating_wallets.values() for buy in buys]
                start_time = min(buy['timestamp'] for buy in all_buys)
                end_time = max(buy['timestamp'] for buy in all_buys)
                
                # Get prices at start and end
                start_price = next((p[1] for p in price_history if p[0] >= start_time), prices[0])
                end_price = next((p[1] for p in price_history if p[0] <= end_time), prices[-1])
                
                return {
                    'pattern_type': 'accumulation',
                    'token_address': token_address,
                    'start_timestamp': start_time,
                    'end_timestamp': end_time,
                    'start_price': float(start_price),
                    'end_price': float(end_price),
                    'percent_change': float((end_price - start_price) / start_price * 100) if start_price > 0 else 0,
                    'volume_change': 0,  # Would need more data
                    'wallet_count': len(accumulating_wallets),
                    'accumulating_wallets': list(accumulating_wallets.keys())
                }
        
        return None
    
    def get_recent_buys(self, token_address, hours=48):
        """Get recent buy transactions for a token"""
        # This would need to be implemented to fetch from the database
        # For now, we'll return an empty list as a placeholder
        return []