# Main entry point for the Telegram bot

import asyncio
import logging
import signal
import sys
from config import TOKEN_ADDRESSES
from database import Database
from blockchain_listener import BlockchainListener
from telegram_bot import TelegramBot

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global variables
bot = None
blockchain_listener = None

async def main():
    global bot, blockchain_listener
    
    try:
        # Initialize database
        db = Database()
        
        # Initialize Telegram bot
        bot = TelegramBot()
        
        # Get monitored tokens from database
        monitored_tokens = db.get_monitored_tokens()
        token_addresses = [token[0] for token in monitored_tokens]
        
        # If no tokens in database, use the ones from config
        if not token_addresses:
            token_addresses = TOKEN_ADDRESSES
        
        # Initialize blockchain listener
        blockchain_listener = BlockchainListener(token_addresses, bot.send_buy_alert)
        
        # Start the bot
        bot.start()
        
        # Start listening for blockchain events
        await blockchain_listener.listen_for_swaps()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Shutting down...")
        cleanup()
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        cleanup()

def cleanup():
    """
    Clean up resources before exiting
    """
    global bot, blockchain_listener
    logger.info("Cleaning up resources...")
    
    if blockchain_listener:
        blockchain_listener.stop()
    
    if bot:
        bot.stop()
    
    logger.info("Cleanup complete. Exiting.")
    sys.exit(0)

def signal_handler(sig, frame):
    """
    Handle termination signals
    """
    logger.info(f"Received signal {sig}. Shutting down...")
    cleanup()

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run the main function
    asyncio.run(main())