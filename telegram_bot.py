# Telegram bot implementation

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler, Filters, MessageHandler, Updater
from web3 import Web3

from config import TELEGRAM_BOT_TOKEN, ADMIN_USER_ID, ETHERSCAN_TX_URL, ETHERSCAN_ADDRESS_URL
from database import Database
from dex_data import DexData
from wallet_analyzer import WalletAnalyzer

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, token=TELEGRAM_BOT_TOKEN):
        self.token = token
        self.updater = Updater(token=token, use_context=True)
        self.dispatcher = self.updater.dispatcher
        self.db = Database()
        self.dex_data = DexData()
        self.wallet_analyzer = WalletAnalyzer()
        self.w3 = Web3()
        
        # Register handlers
        self._register_handlers()
    
    def _register_handlers(self):
        # Command handlers
        self.dispatcher.add_handler(CommandHandler("start", self.start_command))
        self.dispatcher.add_handler(CommandHandler("help", self.help_command))
        self.dispatcher.add_handler(CommandHandler("register", self.register_command))
        self.dispatcher.add_handler(CommandHandler("unregister", self.unregister_command))
        self.dispatcher.add_handler(CommandHandler("addtoken", self.add_token_command, filters=Filters.user(user_id=ADMIN_USER_ID)))
        self.dispatcher.add_handler(CommandHandler("removetoken", self.remove_token_command, filters=Filters.user(user_id=ADMIN_USER_ID)))
        self.dispatcher.add_handler(CommandHandler("listtokens", self.list_tokens_command))
        self.dispatcher.add_handler(CommandHandler("listgroups", self.list_groups_command, filters=Filters.user(user_id=ADMIN_USER_ID)))
        
        # Callback query handler
        self.dispatcher.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Error handler
        self.dispatcher.add_error_handler(self.error_handler)
    
    async def send_buy_alert(self, buy_event):
        """
        Send buy alert to all registered groups
        """
        try:
            # Check if we've already processed this transaction
            if self.db.is_transaction_processed(buy_event['tx_hash']):
                return
            
            # Mark transaction as processed
            self.db.mark_transaction_processed(buy_event['tx_hash'])
            
            # Get token info from DexScreener
            token_info = self.dex_data.get_token_info(buy_event['token_address'])
            if not token_info:
                logger.error(f"Could not get token info for {buy_event['token_address']}")
                return
            
            # Get ETH price in USD
            eth_price_usd = self.dex_data.get_eth_price()
            if not eth_price_usd:
                eth_price_usd = 2000  # Fallback value
            
            # Calculate USD values
            eth_amount_usd = buy_event['eth_amount'] * eth_price_usd
            
            # Analyze buyer wallet
            wallet_info = self.wallet_analyzer.get_wallet_info(buy_event['buyer'])
            if not wallet_info:
                logger.error(f"Could not analyze wallet {buy_event['buyer']}")
                wallet_info = {
                    'is_fresh_wallet': False,
                    'wallet_age_days': 999,
                    'token_holdings': [],
                    'is_swing_trader': False,
                    'trading_info': "Unknown"
                }
            
            # Create wallet status text
            wallet_status = "Fresh" if wallet_info['is_fresh_wallet'] else f"Lama ({wallet_info['wallet_age_days']} hari)"
            
            # Create other holdings text
            other_holdings_text = ""
            for holding in wallet_info['token_holdings'][:3]:  # Show top 3 holdings
                other_holdings_text += f"- ${holding['symbol']}: {holding['balance']:.4f} (~${holding['usd_value']:.2f})\n"
            
            if not other_holdings_text:
                other_holdings_text = "- Tidak ada holdings signifikan\n"
            
            # Create behavior text
            behavior_text = "Swing Trader" if wallet_info['is_swing_trader'] else "Diamond Hands"
            behavior_detail = f"({wallet_info['trading_info']})"
            
            # Create message text
            message = f"{buy_event['token_name']} {buy_event['token_symbol']} 💀Buy!\n\n"
            message += "🤑🤑🤑🤑🤑🤑🤑🤑🤑🤑\n\n"
            message += f"💀| {buy_event['eth_amount']:.4f} ETH (${eth_amount_usd:.2f})\n"
            message += f"💀| Got: {buy_event['token_amount']:.4f} {buy_event['token_symbol']}\n"
            message += f"💀| Buyer: [Wallet]({ETHERSCAN_ADDRESS_URL}{buy_event['buyer']}) | [Tx]({ETHERSCAN_TX_URL}{buy_event['tx_hash']})\n"
            message += f"💀| Position: New\n"
            message += f"💀| Holders: {token_info.get('holders', 'Unknown')}\n"
            message += f"💀| Market Cap: ${token_info.get('market_cap', 0):,.2f}\n\n"
            
            message += f"🧠 Wallet Status: {wallet_status}\n"
            message += f"🐋 Other Holdings:\n{other_holdings_text}"
            message += f"📉 Behavior: {behavior_text}\n{behavior_detail}\n\n"
            
            # Create inline keyboard
            keyboard = [
                [
                    InlineKeyboardButton("💀 Buy", url=f"https://app.uniswap.org/#/swap?outputCurrency={buy_event['token_address']}"),
                    InlineKeyboardButton("💀 DexScreener", url=token_info.get('dexscreener_url', f"https://dexscreener.com/ethereum/{buy_event['token_address']}"))
                ],
                [
                    InlineKeyboardButton("💀 Trending", url=f"https://www.dextools.io/app/en/ether/pair-explorer/{buy_event['token_address']}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send message to all registered groups
            registered_groups = self.db.get_registered_groups()
            for chat_id in registered_groups:
                try:
                    # Use bot.send_message instead of await
                    self.updater.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode='Markdown',
                        disable_web_page_preview=True,
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Error sending message to group {chat_id}: {e}")
        except Exception as e:
            logger.error(f"Error sending buy alert: {e}")
    
    # Change from async def to def
    def start_command(self, update: Update, context: CallbackContext):
        """
        Handler for /start command
        """
        update.message.reply_text(
            'Halo! Saya adalah bot yang mendeteksi pembelian token ERC-20 di Uniswap.\n'
            'Gunakan /help untuk melihat daftar perintah yang tersedia.'
        )
    
    # Change from async def to def
    def help_command(self, update: Update, context: CallbackContext):
        """
        Handler for /help command
        """
        help_text = (
            'Daftar perintah yang tersedia:\n\n'
            '/register - Mendaftarkan grup ini untuk menerima notifikasi\n'
            '/unregister - Membatalkan pendaftaran grup ini\n'
            '/listtokens - Menampilkan daftar token yang dipantau\n\n'
            'Perintah Admin:\n'
            '/addtoken <alamat> <nama> <simbol> - Menambahkan token untuk dipantau\n'
            '/removetoken <alamat> - Menghapus token dari pantauan\n'
            '/listgroups - Menampilkan daftar grup yang terdaftar'
        )
        update.message.reply_text(help_text)
    
    # Change from async def to def
    def register_command(self, update: Update, context: CallbackContext):
        """
        Handler for /register command
        """
        chat_id = update.effective_chat.id
        chat_title = update.effective_chat.title or f"Chat {chat_id}"
        user_id = update.effective_user.id
        
        # Check if this is a group chat
        if update.effective_chat.type not in ['group', 'supergroup']:
            update.message.reply_text('Perintah ini hanya dapat digunakan dalam grup.')
            return
        
        # Register the group
        success = self.db.register_group(chat_id, chat_title, user_id)
        
        if success:
            update.message.reply_text('Grup ini berhasil didaftarkan untuk menerima notifikasi pembelian token.')
        else:
            update.message.reply_text('Gagal mendaftarkan grup. Silakan coba lagi nanti.')
    
    # Change from async def to def
    def unregister_command(self, update: Update, context: CallbackContext):
        """
        Handler for /unregister command
        """
        chat_id = update.effective_chat.id
        
        # Unregister the group
        success = self.db.unregister_group(chat_id)
        
        if success:
            update.message.reply_text('Grup ini telah berhenti menerima notifikasi pembelian token.')
        else:
            update.message.reply_text('Gagal membatalkan pendaftaran grup. Silakan coba lagi nanti.')
    
    # Change from async def to def
    def add_token_command(self, update: Update, context: CallbackContext):
        """
        Handler for /addtoken command
        """
        # Check if user is admin
        if update.effective_user.id != ADMIN_USER_ID:
            update.message.reply_text('Anda tidak memiliki izin untuk menggunakan perintah ini.')
            return
        
        # Check arguments
        if len(context.args) < 3:
            update.message.reply_text('Penggunaan: /addtoken <alamat> <nama> <simbol>')
            return
        
        token_address = context.args[0]
        token_name = context.args[1]
        token_symbol = context.args[2]
        
        # Validate token address
        if not self.w3.is_address(token_address):
            update.message.reply_text('Alamat token tidak valid.')
            return
        
        # Add token to database
        success = self.db.add_token(token_address, token_name, token_symbol)
        
        if success:
            update.message.reply_text(f'Token {token_name} ({token_symbol}) berhasil ditambahkan.')
        else:
            update.message.reply_text('Gagal menambahkan token. Silakan coba lagi nanti.')
    
    # Change from async def to def
    def remove_token_command(self, update: Update, context: CallbackContext):
        """
        Handler for /removetoken command
        """
        # Check if user is admin
        if update.effective_user.id != ADMIN_USER_ID:
            update.message.reply_text('Anda tidak memiliki izin untuk menggunakan perintah ini.')
            return
        
        # Check arguments
        if len(context.args) < 1:
            update.message.reply_text('Penggunaan: /removetoken <alamat>')
            return
        
        token_address = context.args[0]
        
        # Remove token from database
        success = self.db.remove_token(token_address)
        
        if success:
            update.message.reply_text(f'Token dengan alamat {token_address} berhasil dihapus.')
        else:
            update.message.reply_text('Gagal menghapus token. Silakan coba lagi nanti.')
    
    # Change from async def to def
    def list_tokens_command(self, update: Update, context: CallbackContext):
        """
        Handler for /listtokens command
        """
        tokens = self.db.get_monitored_tokens()
        
        if not tokens:
            update.message.reply_text('Tidak ada token yang dipantau saat ini.')
            return
        
        message = 'Daftar token yang dipantau:\n\n'
        for token_address, token_name, token_symbol in tokens:
            message += f'• {token_name} ({token_symbol})\n  `{token_address}`\n\n'
        
        update.message.reply_text(message, parse_mode='Markdown')
    
    # Change from async def to def
    def list_groups_command(self, update: Update, context: CallbackContext):
        """
        Handler for /listgroups command
        """
        # Check if user is admin
        if update.effective_user.id != ADMIN_USER_ID:
            update.message.reply_text('Anda tidak memiliki izin untuk menggunakan perintah ini.')
            return
        
        groups = self.db.get_registered_groups()
        
        if not groups:
            update.message.reply_text('Tidak ada grup yang terdaftar saat ini.')
            return
        
        message = 'Daftar grup yang terdaftar:\n\n'
        for chat_id in groups:
            message += f'• Chat ID: {chat_id}\n'
        
        update.message.reply_text(message)
    
    # Change from async def to def
    def button_callback(self, update: Update, context: CallbackContext):
        """
        Handler for inline keyboard button presses
        """
        query = update.callback_query
        query.answer()
    
    # Change from async def to def
    def error_handler(self, update: Update, context: CallbackContext):
        """
        Error handler for the bot
        """
        logger.error(f"Update {update} caused error {context.error}")
    
    def start(self):
        """
        Start the bot
        """
        self.updater.start_polling()
        logger.info("Bot started")
    
    def stop(self):
        """
        Stop the bot
        """
        self.updater.stop()
        logger.info("Bot stopped")
        self.db.close()