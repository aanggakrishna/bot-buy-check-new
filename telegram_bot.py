# Telegram bot implementation

import asyncio
import logging
from datetime import datetime
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
        self.dispatcher.add_handler(CommandHandler("tokeninfo", self.token_info_command))
        #self.dispatcher.add_handler(CommandHandler("patterns", self.patterns_command))
        
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
            
            # In the send_buy_alert method
            # Create wallet status text
            wallet_status = "Fresh" if wallet_info['is_fresh_wallet'] else f"Old ({wallet_info['wallet_age_days']} days)"
            
            # Create other holdings text
            other_holdings_text = ""
            for holding in wallet_info['token_holdings'][:3]:  # Show top 3 holdings
                other_holdings_text += f"- ${holding['symbol']}: {holding['balance']:.4f} (~${holding['usd_value']:.2f})\n"
            
            if not other_holdings_text:
                other_holdings_text = "- No significant holdings\n"
            
            # Create behavior text
            behavior_text = "Swing Trader" if wallet_info['is_swing_trader'] else "Diamond Hands"
            behavior_detail = f"({wallet_info['trading_info']})"
            
            # Get token trading info if the wallet has traded this token before
            token_trading_info = self.wallet_analyzer.get_token_trading_info(buy_event['buyer'], buy_event['token_address'])
            
            # Create message text
            message = f"{buy_event['token_name']} {buy_event['token_symbol']} 💀Buy!\n\n"
            message += "🤑🤑🤑🤑🤑🤑🤑🤑🤑🤑\n\n"
            message += f"💀| {buy_event['eth_amount']:.4f} ETH (${eth_amount_usd:.2f})\n"
            message += f"💀| Got: {buy_event['token_amount']:.4f} {buy_event['token_symbol']}\n"
            message += f"💀| Buyer: [Wallet]({ETHERSCAN_ADDRESS_URL}{buy_event['buyer']}) | [Tx]({ETHERSCAN_TX_URL}{buy_event['tx_hash']})\n"
            
            # Add token trading info if available
            if token_trading_info and token_trading_info['trade_count'] > 0:
                message += f"💀| Position: Swing Trade ({token_trading_info['trade_count']} trades)\n"
                message += f"💀| Bought: {token_trading_info['bought_amount']:.4f} tokens (${token_trading_info['bought_value_usd']:.2f})\n"
                message += f"💀| PNL: ${token_trading_info['total_pnl']:.2f} ({token_trading_info['pnl_percentage']:.2f}%)\n"
                message += f"💀| Remaining: {token_trading_info['remaining_tokens']:.4f} tokens (${token_trading_info['current_value_usd']:.2f})\n"
            else:
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
    
    # In the start_command method
    def start_command(self, update: Update, context: CallbackContext):
        """
        Handler for /start command
        """
        update.message.reply_text(
            'Hello! I am a bot that detects ERC-20 token purchases on Uniswap.\n'
            'Use /help to see the list of available commands.'
        )
    
    # In the help_command method
    def help_command(self, update: Update, context: CallbackContext):
        """
        Handler for /help command
        """
        help_text = (
            'List of available commands:\n\n'
            '/register - Register this group to receive notifications\n'
            '/unregister - Unregister this group\n'
            '/listtokens - Display list of monitored tokens\n\n'
            'Admin Commands:\n'
            '/addtoken <address> <name> <symbol> - Add token to monitor\n'
            '/removetoken <address> - Remove token from monitoring\n'
            '/listgroups - Display list of registered groups'
        )
        update.message.reply_text(help_text)
    
    # In the register_command method
    def register_command(self, update: Update, context: CallbackContext):
        """
        Handler for /register command
        """
        chat_id = update.effective_chat.id
        chat_title = update.effective_chat.title or f"Chat {chat_id}"
        user_id = update.effective_user.id
        
        # Check if this is a group chat
        if update.effective_chat.type not in ['group', 'supergroup']:
            update.message.reply_text('This command can only be used in groups.')
            return
        
        # Register the group
        success = self.db.register_group(chat_id, chat_title, user_id)
        
        if success:
            update.message.reply_text('This group has been successfully registered to receive token purchase notifications.')
        else:
            update.message.reply_text('Failed to register group. Please try again later.')
    
    # In the unregister_command method
    def unregister_command(self, update: Update, context: CallbackContext):
        """
        Handler for /unregister command
        """
        chat_id = update.effective_chat.id
        
        # Unregister the group
        success = self.db.unregister_group(chat_id)
        
        if success:
            update.message.reply_text('This group has stopped receiving token purchase notifications.')
        else:
            update.message.reply_text('Failed to unregister group. Please try again later.')
    
    # In the add_token_command method
    def add_token_command(self, update: Update, context: CallbackContext):
        """
        Handler for /addtoken command
        """
        # Check if user is admin
        if update.effective_user.id != ADMIN_USER_ID:
            update.message.reply_text('You do not have permission to use this command.')
            return
        
        # Check arguments
        if len(context.args) < 3:
            update.message.reply_text('Usage: /addtoken <address> <name> <symbol>')
            return
        
        token_address = context.args[0]
        token_name = context.args[1]
        token_symbol = context.args[2]
        
        # Validate token address
        if not self.w3.is_address(token_address):
            update.message.reply_text('Invalid token address.')
            return
        
        # Add token to database
        success = self.db.add_token(token_address, token_name, token_symbol)
        
        if success:
            update.message.reply_text(f'Token {token_name} ({token_symbol}) successfully added.')
        else:
            update.message.reply_text('Failed to add token. Please try again later.')
    
    # In the remove_token_command method
    def remove_token_command(self, update: Update, context: CallbackContext):
        """
        Handler for /removetoken command
        """
        # Check if user is admin
        if update.effective_user.id != ADMIN_USER_ID:
            update.message.reply_text('You do not have permission to use this command.')
            return
        
        # Check arguments
        if len(context.args) < 1:
            update.message.reply_text('Usage: /removetoken <address>')
            return
        
        token_address = context.args[0]
        
        # Remove token from database
        success = self.db.remove_token(token_address)
        
        if success:
            update.message.reply_text(f'Token with address {token_address} successfully removed.')
        else:
            update.message.reply_text('Failed to remove token. Please try again later.')
    
    # In the list_tokens_command method
    def list_tokens_command(self, update: Update, context: CallbackContext):
        """
        Handler for /listtokens command
        """
        tokens = self.db.get_monitored_tokens()
        
        if not tokens:
            update.message.reply_text('No tokens are currently being monitored.')
            return
        
        message = 'List of monitored tokens:\n\n'
        for token_address, token_name, token_symbol in tokens:
            message += f'• {token_name} ({token_symbol})\n  `{token_address}`\n\n'
        
        update.message.reply_text(message, parse_mode='Markdown')
    
    # In the list_groups_command method
    def list_groups_command(self, update: Update, context: CallbackContext):
        """
        Handler for /listgroups command
        """
        # Check if user is admin
        if update.effective_user.id != ADMIN_USER_ID:
            update.message.reply_text('You do not have permission to use this command.')
            return
        
        groups = self.db.get_registered_groups()
        
        if not groups:
            update.message.reply_text('No groups are currently registered.')
            return
        
        message = 'List of registered groups:\n\n'
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
    
    def token_info_command(self, update: Update, context: CallbackContext):
        """
        Handler for /tokeninfo command
        """
        # Check arguments
        if len(context.args) < 2:
            update.message.reply_text('Usage: /tokeninfo <wallet_address> <token_address>')
            return
        
        wallet_address = context.args[0]
        token_address = context.args[1]
        
        # Validate addresses
        if not self.w3.is_address(wallet_address) or not self.w3.is_address(token_address):
            update.message.reply_text('Invalid wallet or token address.')
            return
        
        # Get token trading info
        trading_info = self.wallet_analyzer.get_token_trading_info(wallet_address, token_address)
        
        if not trading_info:
            update.message.reply_text('Could not retrieve trading information for this token.')
            return
        
        if trading_info['trade_count'] == 0:
            update.message.reply_text('No trading activity found for this token in this wallet.')
            return
        
        # Create message
        message = f"Trading info for {trading_info['token_symbol']}:\n\n"
        message += f"Total Trades: {trading_info['trade_count']} ({trading_info['buy_count']} buys, {trading_info['sell_count']} sells)\n\n"
        message += f"Bought: {trading_info['bought_amount']:.4f} tokens\n"
        message += f"Total Cost: ${trading_info['bought_value_usd']:.2f}\n\n"
        message += f"Sold: {trading_info['sold_amount']:.4f} tokens\n"
        message += f"Sold Value: ${trading_info['sold_value_usd']:.2f}\n\n"
        message += f"Remaining: {trading_info['remaining_tokens']:.4f} tokens\n"
        message += f"Current Value: ${trading_info['current_value_usd']:.2f}\n\n"
        message += f"Realized PNL: ${trading_info['realized_pnl']:.2f}\n"
        message += f"Unrealized PNL: ${trading_info['unrealized_pnl']:.2f}\n"
        message += f"Total PNL: ${trading_info['total_pnl']:.2f} ({trading_info['pnl_percentage']:.2f}%)\n"
        
        update.message.reply_text(message)
    
    # Di dalam metode _register_handlers, tambahkan:
    self.dispatcher.add_handler(CommandHandler("patterns", self.patterns_command))
    
    # Tambahkan metode baru:
    def patterns_command(self, update: Update, context: CallbackContext):
        """
        Handler for /patterns command
        """
        # Check arguments
        token_address = None
        hours = 24
    
        if context.args:
            if len(context.args) >= 1:
                token_address = context.args[0]
            if len(context.args) >= 2 and context.args[1].isdigit():
                hours = int(context.args[1])
        
        # Get recent patterns
        patterns = self.db.get_recent_patterns(token_address, hours=hours)
        
        if not patterns:
            update.message.reply_text('No trading patterns detected in the specified time period.')
            return
        
        message = f"Trading patterns detected in the last {hours} hours:\n\n"
        
        for pattern in patterns:
            token_info = self.dex_data.get_token_info(pattern[1])  # token_address is at index 1
            token_symbol = token_info['symbol'] if token_info else "Unknown"
            
            pattern_type = pattern[2]  # pattern_type is at index 2
            start_time = datetime.fromtimestamp(pattern[3]).strftime('%Y-%m-%d %H:%M')  # start_timestamp at index 3
            end_time = datetime.fromtimestamp(pattern[4]).strftime('%Y-%m-%d %H:%M')  # end_timestamp at index 4
            percent_change = pattern[7]  # percent_change at index 7
            
            message += f"Token: {token_symbol} ({pattern[1][:6]}...{pattern[1][-4:]})\n"
            message += f"Pattern: {pattern_type.upper()}\n"
            message += f"Time: {start_time} to {end_time}\n"
            message += f"Price Change: {percent_change:.2f}%\n\n"
        
        update.message.reply_text(message)