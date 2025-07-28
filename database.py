# Database operations for the Telegram bot

import sqlite3
import json
from config import DATABASE_PATH

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def _create_tables(self):
        # Create table for registered groups
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS registered_groups (
            chat_id INTEGER PRIMARY KEY,
            chat_title TEXT,
            registered_by INTEGER,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create table for monitored tokens
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS monitored_tokens (
            token_address TEXT PRIMARY KEY,
            token_name TEXT,
            token_symbol TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create table for processed transactions to avoid duplicates
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_transactions (
            tx_hash TEXT PRIMARY KEY,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create table for token price history
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS token_price_history (
            token_address TEXT,
            timestamp INTEGER,
            price_usd REAL,
            volume_usd REAL,
            PRIMARY KEY (token_address, timestamp)
        )
        ''')
        
        # Create table for detected trading patterns
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS trading_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_address TEXT,
            pattern_type TEXT,  -- 'pump_dump', 'accumulation', etc.
            start_timestamp INTEGER,
            end_timestamp INTEGER,
            start_price REAL,
            end_price REAL,
            percent_change REAL,
            volume_change REAL,
            wallet_count INTEGER,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        self.conn.commit()
    
    def register_group(self, chat_id, chat_title, registered_by):
        try:
            self.cursor.execute(
                'INSERT OR REPLACE INTO registered_groups (chat_id, chat_title, registered_by) VALUES (?, ?, ?)',
                (chat_id, chat_title, registered_by)
            )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error registering group: {e}")
            return False
    
    def unregister_group(self, chat_id):
        try:
            self.cursor.execute('DELETE FROM registered_groups WHERE chat_id = ?', (chat_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error unregistering group: {e}")
            return False
    
    def get_registered_groups(self):
        try:
            self.cursor.execute('SELECT chat_id FROM registered_groups')
            return [row[0] for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"Error getting registered groups: {e}")
            return []
    
    def add_token(self, token_address, token_name, token_symbol):
        try:
            self.cursor.execute(
                'INSERT OR REPLACE INTO monitored_tokens (token_address, token_name, token_symbol) VALUES (?, ?, ?)',
                (token_address, token_name, token_symbol)
            )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error adding token: {e}")
            return False
    
    def remove_token(self, token_address):
        try:
            self.cursor.execute('DELETE FROM monitored_tokens WHERE token_address = ?', (token_address,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error removing token: {e}")
            return False
    
    def get_monitored_tokens(self):
        try:
            self.cursor.execute('SELECT token_address, token_name, token_symbol FROM monitored_tokens')
            return self.cursor.fetchall()
        except Exception as e:
            print(f"Error getting monitored tokens: {e}")
            return []
    
    def is_transaction_processed(self, tx_hash):
        self.cursor.execute('SELECT 1 FROM processed_transactions WHERE tx_hash = ?', (tx_hash,))
        return self.cursor.fetchone() is not None
    
    def mark_transaction_processed(self, tx_hash):
        try:
            self.cursor.execute('INSERT INTO processed_transactions (tx_hash) VALUES (?)', (tx_hash,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error marking transaction as processed: {e}")
            return False
    
    def close(self):
        self.conn.close()
    
    # Add methods to store and retrieve price history
    def store_token_price(self, token_address, price_usd, volume_usd):
        try:
            timestamp = int(datetime.now().timestamp())
            self.cursor.execute(
                'INSERT OR REPLACE INTO token_price_history (token_address, timestamp, price_usd, volume_usd) VALUES (?, ?, ?, ?)',
                (token_address, timestamp, price_usd, volume_usd)
            )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error storing token price: {e}")
            return False
    
    def get_token_price_history(self, token_address, hours=24):
        try:
            timestamp_threshold = int((datetime.now() - timedelta(hours=hours)).timestamp())
            self.cursor.execute(
                'SELECT timestamp, price_usd, volume_usd FROM token_price_history WHERE token_address = ? AND timestamp >= ? ORDER BY timestamp',
                (token_address, timestamp_threshold)
            )
            return self.cursor.fetchall()
        except Exception as e:
            print(f"Error getting token price history: {e}")
            return []
    
    def store_trading_pattern(self, token_address, pattern_type, start_timestamp, end_timestamp, 
                             start_price, end_price, percent_change, volume_change, wallet_count):
        try:
            self.cursor.execute(
                '''INSERT INTO trading_patterns 
                   (token_address, pattern_type, start_timestamp, end_timestamp, start_price, end_price, 
                    percent_change, volume_change, wallet_count) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (token_address, pattern_type, start_timestamp, end_timestamp, start_price, end_price, 
                 percent_change, volume_change, wallet_count)
            )
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            print(f"Error storing trading pattern: {e}")
            return None
    
    def get_recent_patterns(self, token_address=None, pattern_type=None, hours=24):
        try:
            timestamp_threshold = int((datetime.now() - timedelta(hours=hours)).timestamp())
            query = 'SELECT * FROM trading_patterns WHERE detected_at >= datetime(?, "unixepoch")'
            params = [timestamp_threshold]
            
            if token_address:
                query += ' AND token_address = ?'
                params.append(token_address)
            
            if pattern_type:
                query += ' AND pattern_type = ?'
                params.append(pattern_type)
                
            query += ' ORDER BY detected_at DESC'
            
            self.cursor.execute(query, params)
            return self.cursor.fetchall()
        except Exception as e:
            print(f"Error getting recent patterns: {e}")
            return []