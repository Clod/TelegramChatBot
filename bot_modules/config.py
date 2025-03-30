import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv(override=True)
logger.info(".env file loaded (override=True)")

# --- Debug Mode ---
DEBUG_MODE_STR_RAW = os.environ.get("DEBUG_MODE", "False")
logger.info(f"Raw DEBUG_MODE string from environment: '{DEBUG_MODE_STR_RAW}'")
DEBUG_MODE_STR = DEBUG_MODE_STR_RAW.lower()
DEBUG_MODE = DEBUG_MODE_STR == "true"

print(f"DEBUG_MODE evaluated as: {DEBUG_MODE}") # Use a slightly different print message
if DEBUG_MODE:
    print("Debug mode is ON!")
else:
    print("Debug mode is OFF!")

# --- Telegram Configuration ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

BASE_URL = os.environ.get("BASE_URL")
if not BASE_URL:
    logger.warning("BASE_URL environment variable is not set. Attempting to infer...")
    port = os.environ.get("PORT", "443")
    BASE_URL = f"https://localhost:{port}"
    logger.warning(f"Inferred BASE_URL as {BASE_URL}. Set this explicitly in .env for production.")

WEBHOOK_URL = f"{BASE_URL}/{TOKEN}"
WEBAPP_EDIT_PROFILE_URL = f"{BASE_URL}/webapp/edit_profile" # URL for the profile editing web app
WEBAPP_EDIT_MESSAGES_URL = f"{BASE_URL}/webapp/edit_messages" # URL for the message editing web app

# --- Google API Configuration ---
SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if not SERVICE_ACCOUNT_FILE or not os.path.exists(SERVICE_ACCOUNT_FILE):
    logger.warning("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set or file does not exist. Some Google API features may not work.")

# Gemini API endpoint
GEMINI_API_ENDPOINT = os.environ.get(
    "GEMINI_API_ENDPOINT",
    "https://LOCATION-aiplatform.googleapis.com/v1/projects/PROJECT_ID/locations/LOCATION/publishers/google/models/gemini-2.0-flash-lite:generateContent"
)

# Google Form configuration
GOOGLE_FORM_ID = os.environ.get("GOOGLE_FORM_ID")
if not GOOGLE_FORM_ID:
    logger.warning("GOOGLE_FORM_ID could not be retrieved. Form retrieval will not work.")
else:
    logger.info("GOOLGE_FORM_ID retrieved successfully: " + GOOGLE_FORM_ID)

# Apps Script configuration
APPS_SCRIPT_ID = os.environ.get("APPS_SCRIPT_ID")
if not APPS_SCRIPT_ID:
    logger.warning("APPS_SCRIPT_ID environment variable is not set. Google Sheet retrieval will not work.")
else:
    logger.info(f"APPS_SCRIPT_ID retrieved successfully: {APPS_SCRIPT_ID}")

# Apps Script Web App configuration
APPS_SCRIPT_WEB_APP_URL = os.environ.get("APPS_SCRIPT_WEB_APP_URL")
APPS_SCRIPT_API_KEY = os.environ.get("APPS_SCRIPT_API_KEY")
if not APPS_SCRIPT_WEB_APP_URL or not APPS_SCRIPT_API_KEY:
    logger.warning("APPS_SCRIPT_WEB_APP_URL or APPS_SCRIPT_API_KEY environment variable is not set. Google Sheet retrieval via Web App will not work.")
else:
    logger.info(f"APPS_SCRIPT_WEB_APP_URL retrieved successfully.")

# --- Database Configuration ---
DB_PATH = 'bot_users.db'

# --- SSL Configuration ---
# Use relative paths assuming 'certs' is in the root alongside app.py/main.py
WEBHOOK_SSL_CERT = "certs/fullchain.pem"
WEBHOOK_SSL_PRIV = "certs/privkey.pem"

# --- Flask Configuration ---
FLASK_PORT = int(os.environ.get("PORT", 443)) # Use PORT from env if set, else default 443
