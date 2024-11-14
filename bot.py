import os
import yaml
import datetime
from threading import Lock
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
import requests
from anthropic import Anthropic
import logging
from telegram.error import Conflict, NetworkError, TelegramError

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
CLAUDE_KEY = os.getenv('CLAUDE_KEY')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set in environment variables")

if not CLAUDE_KEY:
    raise ValueError("CLAUDE_KEY not set in environment variables")

# Initialize directories
os.makedirs('sources', exist_ok=True)
os.makedirs('responses', exist_ok=True)

# Initialize a lock for thread-safe file writing
file_lock = Lock()

# Initialize Claude client
client = Anthropic(api_key=CLAUDE_KEY)

DEFAULT_ADMINS = {
    '67950696': True,
}

DEFAULT_GROUPS = {
    '-1001868541493': {'messages_today': 0, 'last_reset': str(datetime.date.today())}, 
    '-4069234649': {'messages_today': 0, 'last_reset': str(datetime.date.today())},
}

def error_handler(update: Update, context: CallbackContext) -> None:
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")
    
    try:
        raise context.error
    except Conflict:
        # Handle conflict errors (multiple instances)
        logger.warning("Conflict: Another instance is running")
    except NetworkError:
        # Handle network errors
        logger.error("Network error occurred")
    except TelegramError:
        # Handle other Telegram-related errors
        logger.error("Telegram error occurred")
    except Exception as e:
        # Handle other errors
        logger.error(f"Other error occurred: {str(e)}")

def main() -> None:
    try:
        # Initialize the updater with clean=True to handle conflicts
        updater = Updater(TELEGRAM_TOKEN, use_context=True)
        dispatcher = updater.dispatcher

        # Add error handler
        dispatcher.add_error_handler(error_handler)

        # Add command handlers
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("help", help_command))
        dispatcher.add_handler(CommandHandler("prompt", handle_message))
        dispatcher.add_handler(CommandHandler("p", handle_message))
        dispatcher.add_handler(CommandHandler("preaudit", preaudit))
        dispatcher.add_handler(CommandHandler("add_admin", add_admin))
        dispatcher.add_handler(CommandHandler("add_group", add_group))
        
        # Start the bot with clean=True to handle conflicts
        updater.start_polling(clean=True, drop_pending_updates=True)
        
        logger.info("Bot started successfully")
        
        # Run the bot until Ctrl+C is pressed
        updater.idle()
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise

if __name__ == '__main__':
    logger.info("Starting bot...")
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")