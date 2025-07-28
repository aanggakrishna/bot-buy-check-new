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