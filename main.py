# main.py (formerly app.py)
import logging
import os
import getpass
import telebot # Keep for ApiTelegramException

# Import from our modules
from bot_modules import config
from bot_modules.database import init_db
from bot_modules.telegram_bot import bot # Import the initialized bot instance
from bot_modules.flask_app import app # Import the initialized Flask app
from bot_modules import strings_en
from bot_modules import strings_es

# Set language based on environment
BOT_LANGUAGE = os.getenv('BOT_LANGUAGE', 'english').lower()
s = strings_es if BOT_LANGUAGE == 'spanish' else strings_en

# --- Initial Logging Setup ---
# Configure logging (this should be done early)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Environment and Language Setup ---
# Log the language read from the environment
logger.info(f"Bot language set to: {BOT_LANGUAGE}")

# Log effective user (optional, for debugging permissions)
try:
    logger.info(s.LOG_EFFECTIVE_UID.format(uid=os.geteuid()))
    logger.info(s.LOG_EFFECTIVE_USER.format(user=getpass.getuser()))
except Exception as e:
    logger.warning(s.WARN_CANNOT_GET_USER_INFO.format(error=e))

# --- Database Initialization ---
try:
    init_db()
except Exception as db_init_e:
    logger.error(s.FATAL_DB_INIT_FAILED.format(error=db_init_e), exc_info=True)
    exit(1) # Exit if DB can't be initialized

# --- Main Execution Logic ---
if __name__ == '__main__':
    inferred_base_url = "localhost" in config.BASE_URL or "127.0.0.1" in config.BASE_URL

    if config.DEBUG_MODE:
        logger.info(s.LOG_STARTING_DEBUG_POLLING)
        try:
            logger.info(s.LOG_REMOVING_WEBHOOK)
            bot.remove_webhook()
            logger.info(s.LOG_WEBHOOK_REMOVED)
        except Exception as e:
            logger.warning(s.WARN_CANNOT_REMOVE_WEBHOOK.format(error=e))

        logger.info(s.LOG_POLLING_STARTED)
        # Note: Flask server is NOT started automatically in polling mode.
        # Web Apps and webhook routes will not be reachable unless Flask is run separately.
        try:
            bot.infinity_polling(logger_level=logging.INFO)
        except Exception as poll_e:
             logger.error(s.ERROR_POLLING_FAILED.format(error=poll_e), exc_info=True)
        finally:
             logger.info(s.LOG_POLLING_STOPPED)

    else: # Production mode (DEBUG_MODE is False)
        logger.info(s.LOG_STARTING_PRODUCTION_WEBHOOK)
        if inferred_base_url or not config.BASE_URL or not config.BASE_URL.startswith("https://"):
             logger.error(s.FATAL_INVALID_BASE_URL_PRODUCTION)
             logger.error(s.LOG_CURRENT_BASE_URL.format(base_url=config.BASE_URL))
             exit(1)

        try:
            logger.info(s.LOG_REMOVING_WEBHOOK)
            bot.remove_webhook()
            logger.info(s.LOG_WEBHOOK_REMOVED)
        except Exception as e:
            logger.error(s.ERROR_REMOVING_WEBHOOK_PRODUCTION.format(error=e))
            exit(1)

        try:
            logger.info(s.LOG_SETTING_WEBHOOK.format(url=config.WEBHOOK_URL))
            cert_exists = os.path.exists(config.WEBHOOK_SSL_CERT)
            key_exists = os.path.exists(config.WEBHOOK_SSL_PRIV)
            if not cert_exists or not key_exists:
                 logger.warning(s.WARN_SSL_CERT_NOT_FOUND.format(cert_path=config.WEBHOOK_SSL_CERT, key_path=config.WEBHOOK_SSL_PRIV))

            bot.set_webhook(url=config.WEBHOOK_URL) # No cert parameter needed if handled by reverse proxy
            logger.info(s.LOG_WEBHOOK_SET_NO_CERT_PARAM)
            webhook_info_check = bot.get_webhook_info()
            logger.info(s.LOG_WEBHOOK_STATUS_CHECK.format(url=webhook_info_check.url, pending_updates=webhook_info_check.pending_update_count))
            if webhook_info_check.last_error_message:
                 logger.warning(s.WARN_TELEGRAM_WEBHOOK_ERROR.format(error_message=webhook_info_check.last_error_message))

        except telebot.apihelper.ApiTelegramException as e:
             logger.error(s.FATAL_WEBHOOK_SET_API_ERROR.format(error=e), exc_info=True)
             exit(1)
        except Exception as e:
            logger.error(s.FATAL_WEBHOOK_SET_OTHER_ERROR.format(error=e), exc_info=True)
            exit(1)

        # Start the Flask web server
        logger.info(s.LOG_STARTING_FLASK.format(port=config.FLASK_PORT))
        try:
            if not os.path.exists(config.WEBHOOK_SSL_CERT) or not os.path.exists(config.WEBHOOK_SSL_PRIV):
                 logger.error(s.FATAL_SSL_FILES_NOT_FOUND_FLASK)
                 logger.error(s.LOG_CERT_PATH_CHECKED.format(path=os.path.abspath(config.WEBHOOK_SSL_CERT)))
                 logger.error(s.LOG_KEY_PATH_CHECKED.format(path=os.path.abspath(config.WEBHOOK_SSL_PRIV)))
                 exit(1)

            # Run Flask app using the imported 'app' instance
            app.run(
                host='0.0.0.0',
                port=config.FLASK_PORT,
                ssl_context=(config.WEBHOOK_SSL_CERT, config.WEBHOOK_SSL_PRIV),
                debug=False # Flask debug MUST be off in production
            )
        except FileNotFoundError:
             logger.error(s.FATAL_SSL_FILES_NOT_FOUND_FLASK)
             exit(1)
        except OSError as e:
             if "Address already in use" in str(e): logger.error(s.FATAL_PORT_IN_USE.format(port=config.FLASK_PORT))
             else: logger.error(s.FATAL_FLASK_OS_ERROR.format(error=e), exc_info=True)
             exit(1)
        except Exception as e:
             logger.error(s.FATAL_FLASK_START_FAILED.format(error=e), exc_info=True)
             exit(1)
