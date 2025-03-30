# main.py (formerly app.py)
import logging
import os
import getpass
import traceback
import telebot # Keep for ApiTelegramException

# Import from our modules
from bot_modules import config
from bot_modules.database import init_db
from bot_modules.telegram_bot import bot # Import the initialized bot instance
from bot_modules.flask_app import app # Import the initialized Flask app

# --- Initial Logging Setup ---
# Configure logging (this should be done early)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Log effective user (optional, for debugging permissions)
try:
    logger.info(f"Effective UID: {os.geteuid()}")
    logger.info(f"Effective User: {getpass.getuser()}")
except Exception as e:
    logger.warning(f"Could not get user info: {e}")

# --- Database Initialization ---
try:
    init_db()
except Exception as db_init_e:
    logger.error(f"FATAL: Failed to initialize database: {db_init_e}", exc_info=True)
    exit(1) # Exit if DB can't be initialized

# --- Main Execution Logic ---
if __name__ == '__main__':
    inferred_base_url = "localhost" in config.BASE_URL or "127.0.0.1" in config.BASE_URL

    if config.DEBUG_MODE:
        logger.info("Starting bot in DEBUG mode using polling...")
        try:
            logger.info("Attempting to remove existing webhook (if any)...")
            bot.remove_webhook()
            logger.info("Webhook removed successfully (or was not set).")
        except Exception as e:
            logger.warning(f"Could not remove webhook (may not have been set): {e}")

        logger.info("Bot polling started...")
        # Note: Flask server is NOT started automatically in polling mode.
        # Web Apps and webhook routes will not be reachable unless Flask is run separately.
        try:
            bot.infinity_polling(logger_level=logging.INFO)
        except Exception as poll_e:
             logger.error(f"Polling failed: {poll_e}", exc_info=True)
        finally:
             logger.info("Bot polling stopped.")

    else: # Production mode (DEBUG_MODE is False)
        logger.info("Starting bot in PRODUCTION mode using webhook...")
        if inferred_base_url or not config.BASE_URL or not config.BASE_URL.startswith("https://"):
             logger.error("FATAL: BASE_URL is not set, not HTTPS, or is local in production mode.")
             logger.error(f"Current BASE_URL: {config.BASE_URL}")
             exit(1)

        try:
            logger.info("Attempting to remove existing webhook...")
            bot.remove_webhook()
            logger.info("Webhook removed successfully.")
        except Exception as e:
            logger.error(f"Error removing webhook before setting new one: {e}")
            exit(1)

        try:
            logger.info(f"Setting webhook to: {config.WEBHOOK_URL}")
            cert_exists = os.path.exists(config.WEBHOOK_SSL_CERT)
            key_exists = os.path.exists(config.WEBHOOK_SSL_PRIV)
            if not cert_exists or not key_exists:
                 logger.warning(f"SSL Certificate or Key not found. Cert: {config.WEBHOOK_SSL_CERT}, Key: {config.WEBHOOK_SSL_PRIV}. Setting webhook without certificate parameter.")

            bot.set_webhook(url=config.WEBHOOK_URL) # No cert parameter needed if handled by reverse proxy
            logger.info("Webhook set successfully (without sending certificate parameter to Telegram).")
            webhook_info_check = bot.get_webhook_info()
            logger.info(f"Webhook status check: URL='{webhook_info_check.url}', Pending Updates={webhook_info_check.pending_update_count}")
            if webhook_info_check.last_error_message:
                 logger.warning(f"Telegram reported webhook error: {webhook_info_check.last_error_message}")

        except telebot.apihelper.ApiTelegramException as e:
             logger.error(f"FATAL: Failed to set webhook due to Telegram API error: {e}", exc_info=True)
             exit(1)
        except Exception as e:
            logger.error(f"FATAL: Failed to set webhook due to other error: {e}", exc_info=True)
            exit(1)

        # Start the Flask web server
        logger.info(f"Starting Flask server on 0.0.0.0:{config.FLASK_PORT} with SSL...")
        try:
            if not os.path.exists(config.WEBHOOK_SSL_CERT) or not os.path.exists(config.WEBHOOK_SSL_PRIV):
                 logger.error("FATAL: SSL certificate or key file not found for Flask server.")
                 logger.error(f"Cert path checked: {os.path.abspath(config.WEBHOOK_SSL_CERT)}")
                 logger.error(f"Key path checked: {os.path.abspath(config.WEBHOOK_SSL_PRIV)}")
                 exit(1)

            # Run Flask app using the imported 'app' instance
            app.run(
                host='0.0.0.0',
                port=config.FLASK_PORT,
                ssl_context=(config.WEBHOOK_SSL_CERT, config.WEBHOOK_SSL_PRIV),
                debug=False # Flask debug MUST be off in production
            )
        except FileNotFoundError:
             logger.error("FATAL: SSL certificate or key file not found during Flask startup.")
             exit(1)
        except OSError as e:
             if "Address already in use" in str(e): logger.error(f"FATAL: Port {config.FLASK_PORT} is already in use.")
             else: logger.error(f"FATAL: Failed to start Flask server due to OS error: {e}", exc_info=True)
             exit(1)
        except Exception as e:
             logger.error(f"FATAL: Failed to start Flask server: {e}", exc_info=True)
             exit(1)
