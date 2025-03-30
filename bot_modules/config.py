import os
import logging
from dotenv import load_dotenv
from . import strings as s  # Import the strings module

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv(override=True)
logger.info(s.LOG_DOTENV_LOADED)

# --- Debug Mode ---
DEBUG_MODE_STR_RAW = os.environ.get("DEBUG_MODE", "False")
logger.info(s.LOG_RAW_DEBUG_MODE.format(raw_value=DEBUG_MODE_STR_RAW))
DEBUG_MODE_STR = DEBUG_MODE_STR_RAW.lower()
DEBUG_MODE = DEBUG_MODE_STR == "true"

print(s.LOG_DEBUG_MODE_EVALUATED.format(debug_mode=DEBUG_MODE)) # Use a slightly different print message
if DEBUG_MODE:
    print(s.DEBUG_MODE_ON)
else:
    print(s.DEBUG_MODE_OFF)

# --- Telegram Configuration ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError(s.ERROR_TOKEN_NOT_SET)

BASE_URL = os.environ.get("BASE_URL")
if not BASE_URL:
    logger.warning(s.WARN_BASE_URL_NOT_SET)
    port = os.environ.get("PORT", "443")
    BASE_URL = f"https://localhost:{port}"
    logger.warning(s.WARN_INFERRED_BASE_URL.format(base_url=BASE_URL))

WEBHOOK_URL = f"{BASE_URL}/{TOKEN}"
WEBAPP_EDIT_PROFILE_URL = f"{BASE_URL}/webapp/edit_profile" # URL for the profile editing web app
WEBAPP_EDIT_MESSAGES_URL = f"{BASE_URL}/webapp/edit_messages" # URL for the message editing web app

# --- Google API Configuration ---
SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if not SERVICE_ACCOUNT_FILE or not os.path.exists(SERVICE_ACCOUNT_FILE):
    logger.warning(s.WARN_GOOGLE_CREDS_NOT_SET)

# Gemini API endpoint
GEMINI_API_ENDPOINT = os.environ.get(
    "GEMINI_API_ENDPOINT",
    "https://LOCATION-aiplatform.googleapis.com/v1/projects/PROJECT_ID/locations/LOCATION/publishers/google/models/gemini-2.0-flash-lite:generateContent"
)

# Google Form configuration
GOOGLE_FORM_ID = os.environ.get("GOOGLE_FORM_ID")
if not GOOGLE_FORM_ID:
    logger.warning(s.WARN_GOOGLE_FORM_ID_NOT_SET)
else:
    logger.info(s.LOG_GOOGLE_FORM_ID_SUCCESS.format(form_id=GOOGLE_FORM_ID))

# Apps Script configuration
APPS_SCRIPT_ID = os.environ.get("APPS_SCRIPT_ID")
if not APPS_SCRIPT_ID:
    logger.warning(s.WARN_APPS_SCRIPT_ID_NOT_SET)
else:
    logger.info(s.LOG_APPS_SCRIPT_ID_SUCCESS.format(script_id=APPS_SCRIPT_ID))

# Apps Script Web App configuration
APPS_SCRIPT_WEB_APP_URL = os.environ.get("APPS_SCRIPT_WEB_APP_URL")
APPS_SCRIPT_API_KEY = os.environ.get("APPS_SCRIPT_API_KEY")
if not APPS_SCRIPT_WEB_APP_URL or not APPS_SCRIPT_API_KEY:
    logger.warning(s.WARN_APPS_SCRIPT_WEB_APP_NOT_SET)
else:
    logger.info(s.LOG_APPS_SCRIPT_WEB_APP_SUCCESS)

# --- Database Configuration ---
DB_PATH = 'bot_users.db'

# --- SSL Configuration ---
# Use relative paths assuming 'certs' is in the root alongside app.py/main.py
WEBHOOK_SSL_CERT = "certs/fullchain.pem"
WEBHOOK_SSL_PRIV = "certs/privkey.pem"

# --- Flask Configuration ---
FLASK_PORT = int(os.environ.get("PORT", 443)) # Use PORT from env if set, else default 443
