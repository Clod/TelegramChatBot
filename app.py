# Import necessary libraries
import logging  # For logging messages and errors
import os  # For accessing environment variables and file paths
import sqlite3  # For SQLite database operations
from datetime import datetime  # For timestamps in health checks
from flask import Flask, request, jsonify, render_template # Web framework for creating API endpoints
import telebot  # Python Telegram Bot API wrapper
from dotenv import load_dotenv  # For loading environment variables from .env file
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo # For creating interactive buttons
import requests  # For making HTTP requests to Gemini API
import json  # For parsing JSON responses
import tempfile  # For creating temporary files
import uuid  # For generating unique filenames
import traceback  # For detailed error information in logs
import base64  # For encoding images to base64
import time    # For generating timestamp-based message IDs
import google.auth
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleAuthRequest
import re # For regular expression matching
from googleapiclient.discovery import build # For Google API client
from googleapiclient.errors import HttpError # For Google API errors


import getpass
print(f"Effective UID: {os.geteuid()}")                                                                                              
print(f"Effective User: {getpass.getuser()}")                                                                                        

# Configure logging to track what's happening in our application
# This helps with debugging and monitoring
logging.basicConfig(
    level=logging.INFO,  # Log level - INFO means we'll see general operational messages
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'  # Format of log messages
)
logger = logging.getLogger(__name__)  # Create a logger specific to this module

# Load environment variables from .env file
# This is a security best practice to avoid hardcoding sensitive information
# override=True ensures that variables in .env take precedence over system environment variables
load_dotenv(override=True)
logger.info(".env file loaded (override=True)")


# Get DEBUG_MODE from environment variables
# Default to "False" if not set
DEBUG_MODE_STR_RAW = os.environ.get("DEBUG_MODE", "False")
logger.info(f"Raw DEBUG_MODE string from environment: '{DEBUG_MODE_STR_RAW}'") # Log the raw value
DEBUG_MODE_STR = DEBUG_MODE_STR_RAW.lower()
DEBUG_MODE = DEBUG_MODE_STR == "true" # Only "true" (case-insensitive) evaluates to True

print(f"DEBUG_MODE evaluated as: {DEBUG_MODE}") # Use a slightly different print message

if DEBUG_MODE:
    print("Debug mode is ON!")
else:
    print("Debug mode is OFF!")

# Get the Telegram Bot Token from environment variables
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    # If the token isn't set, raise an error - the bot can't work without it
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

# Create the webhook URL that Telegram will use to send updates to our bot
BASE_URL = os.environ.get("BASE_URL")
if not BASE_URL:
    logger.warning("BASE_URL environment variable is not set. Attempting to infer...")
    # Basic inference for local testing, might need adjustment
    port = os.environ.get("PORT", "443") # Default to 443 if not set
    BASE_URL = f"https://localhost:{port}"
    logger.warning(f"Inferred BASE_URL as {BASE_URL}. Set this explicitly in .env for production.")

WEBHOOK_URL = f"{BASE_URL}/{TOKEN}"
# Define URLs for Web Apps (ensure these use BASE_URL)
WEBAPP_EDIT_PROFILE_URL = f"{BASE_URL}/webapp/edit_profile" # URL for the profile editing web app
WEBAPP_EDIT_MESSAGES_URL = f"{BASE_URL}/webapp/edit_messages" # URL for the message editing web app


# Path to the service account JSON file
SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if not SERVICE_ACCOUNT_FILE or not os.path.exists(SERVICE_ACCOUNT_FILE):
    logger.warning("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set or file does not exist. Image processing will not work.")

# Gemini API endpoint - update to use the correct format for authenticated requests
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
    logger.info(f"APPS_SCRIPT_WEB_APP_URL retrieved successfully.") # Don't log the key itself


# Paths to SSL certificate files
# These are needed for secure HTTPS communication
# WEBHOOK_SSL_CERT = "/etc/letsencrypt/live/precarina.com.ar/fullchain.pem"  # Public certificate
# WEBHOOK_SSL_PRIV = "/etc/letsencrypt/live/precarina.com.ar/privkey.pem"     # Private key

WEBHOOK_SSL_CERT = "certs/fullchain.pem"  # Public certificate
WEBHOOK_SSL_PRIV = "certs/privkey.pem"     # Private key

# Initialize our web application and Telegram bot
app = Flask(__name__)  # Create a Flask web application
bot = telebot.TeleBot(TOKEN)  # Create a Telegram bot instance with our token

# Dictionary to store user sessions
user_sessions = {}  # Key: user_id, Value: dict with user state and data

# Database setup
DB_PATH = 'bot_users.db'

def init_db():
    """Initialize the SQLite database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create users table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        language_code TEXT,
        is_bot BOOLEAN,
        chat_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create user_interactions table to track user actions
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action_type TEXT,
        action_data TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    # Create user_preferences table to store user settings
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_preferences (
        user_id INTEGER PRIMARY KEY,
        language TEXT DEFAULT 'en',
        notifications BOOLEAN DEFAULT 1,
        theme TEXT DEFAULT 'default',
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    # Create user_messages table to store messages sent by users
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        chat_id INTEGER,
        message_id INTEGER,
        message_text TEXT,
        message_type TEXT,
        has_media BOOLEAN DEFAULT 0,
        media_type TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    # Create image_processing_results table to store Gemini API responses
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS image_processing_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message_id INTEGER,
        file_id TEXT,
        gemini_response TEXT,
        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")

# Initialize the database when the app starts
init_db()

def save_user(user, chat_id=None):
    """Save or update user information in the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if user already exists
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user.id,))
    exists = cursor.fetchone()
    
    if exists:
        # Update existing user's last activity
        if chat_id:
            cursor.execute("""
            UPDATE users 
            SET username = ?, first_name = ?, last_name = ?, language_code = ?, 
                chat_id = ?, last_activity = CURRENT_TIMESTAMP 
            WHERE user_id = ?
            """, (user.username, user.first_name, user.last_name, user.language_code, 
                  chat_id, user.id))
        else:
            cursor.execute("""
            UPDATE users 
            SET username = ?, first_name = ?, last_name = ?, language_code = ?, 
                last_activity = CURRENT_TIMESTAMP 
            WHERE user_id = ?
            """, (user.username, user.first_name, user.last_name, user.language_code, user.id))
    else:
        # Insert new user
        cursor.execute("""
        INSERT INTO users (user_id, username, first_name, last_name, language_code, is_bot, chat_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user.id, user.username, user.first_name, user.last_name, 
              user.language_code, user.is_bot, chat_id))
        
        # Initialize user preferences for new users
        cursor.execute("""
        INSERT INTO user_preferences (user_id)
        VALUES (?)
        """, (user.id,))
    
    conn.commit()
    conn.close()

def log_interaction(user_id, action_type, action_data=None):
    """Log user interaction in the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Convert action_data to JSON string if it's not None and not already a string
    action_data_str = None
    if action_data is not None:
        if isinstance(action_data, str):
            action_data_str = action_data
        else:
            try:
                action_data_str = json.dumps(action_data)
            except Exception as e:
                logger.error(f"Error converting action_data to JSON for user {user_id}, action {action_type}: {e}")
                action_data_str = str(action_data) # Fallback to string representation

    cursor.execute("""
    INSERT INTO user_interactions (user_id, action_type, action_data)
    VALUES (?, ?, ?)
    """, (user_id, action_type, action_data_str)) # Use the string version

    conn.commit()
    conn.close()

def save_message(message):
    """Save a user message to the database"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    message_id = message.message_id
    message_text = message.text if message.content_type == 'text' else None
    
    # Determine message type
    message_type = message.content_type
    has_media = message.content_type != 'text'
    media_type = message.content_type if has_media else None
    
    # Get file_id for photo messages
    file_id = None
    if message.content_type == 'photo' and message.photo:
        file_id = message.photo[-1].file_id
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
    INSERT INTO user_messages (user_id, chat_id, message_id, message_text, message_type, has_media, media_type)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, chat_id, message_id, message_text, message_type, has_media, media_type))
    
    conn.commit()
    conn.close()
    
    if message_text:
        logger.info(f"Saved message from user {user_id}: {message_text[:50]}...")
    else:
        logger.info(f"Saved {message_type} message from user {user_id}")

def get_user_preferences(user_id):
    """Get user preferences from the database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,))
    prefs = cursor.fetchone()
    
    conn.close()
    
    if prefs:
        return dict(prefs)
    else:
        # Return default preferences if not found
        return {
            'user_id': user_id,
            'language': 'en',
            'notifications': True,
            'theme': 'default'
        }

def update_user_preference(user_id, preference_name, preference_value):
    """Update a specific user preference"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if user has preferences record
    cursor.execute("SELECT user_id FROM user_preferences WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone()
    
    if exists:
        # Update the specific preference
        cursor.execute(f"""
        UPDATE user_preferences 
        SET {preference_name} = ?, last_updated = CURRENT_TIMESTAMP 
        WHERE user_id = ?
        """, (preference_value, user_id))
    else:
        # Create default preferences with the specified value
        defaults = {
            'language': 'en',
            'notifications': True,
            'theme': 'default'
        }
        defaults[preference_name] = preference_value
        
        cursor.execute("""
        INSERT INTO user_preferences (user_id, language, notifications, theme)
        VALUES (?, ?, ?, ?)
        """, (user_id, defaults['language'], defaults['notifications'], defaults['theme']))
    
    conn.commit()
    conn.close()
    return True

def get_user_data_summary(user_id):
    """Get a summary of all data stored for a user"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    summary = {}
    
    # Get user profile
    cursor.execute("""
    SELECT u.*, p.language, p.notifications, p.theme
    FROM users u
    LEFT JOIN user_preferences p ON u.user_id = p.user_id
    WHERE u.user_id = ?
    """, (user_id,))
    user = cursor.fetchone()
    
    if user:
        summary['profile'] = dict(user)
        
        # Get message count
        cursor.execute("SELECT COUNT(*) as count FROM user_messages WHERE user_id = ?", (user_id,))
        message_count = cursor.fetchone()
        summary['message_count'] = message_count['count'] if message_count else 0
        
        # Get interaction count
        cursor.execute("SELECT COUNT(*) as count FROM user_interactions WHERE user_id = ?", (user_id,))
        interaction_count = cursor.fetchone()
        summary['interaction_count'] = interaction_count['count'] if interaction_count else 0
        
        # Get interaction types
        cursor.execute("""
        SELECT action_type, COUNT(*) as count
        FROM user_interactions
        WHERE user_id = ?
        GROUP BY action_type
        ORDER BY count DESC
        """, (user_id,))
        summary['interaction_types'] = [dict(row) for row in cursor.fetchall()]
        
        # Get recent messages (last 5)
        cursor.execute("""
        SELECT message_text, timestamp
        FROM user_messages
        WHERE user_id = ?
        ORDER BY timestamp DESC
        LIMIT 5
        """, (user_id,))
        summary['recent_messages'] = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return summary

def delete_user_data(user_id):
    """Delete all data associated with a user from the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Start a transaction
        cursor.execute("BEGIN TRANSACTION")
        
        # Delete user messages
        cursor.execute("DELETE FROM user_messages WHERE user_id = ?", (user_id,))
        messages_deleted = cursor.rowcount
        
        # Delete user interactions
        cursor.execute("DELETE FROM user_interactions WHERE user_id = ?", (user_id,))
        interactions_deleted = cursor.rowcount
        
        # Delete user preferences
        cursor.execute("DELETE FROM user_preferences WHERE user_id = ?", (user_id,))
        
        # Delete user record
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        
        # Commit the transaction
        conn.commit()
        
        # If the user has an active session, remove it
        if user_id in user_sessions:
            del user_sessions[user_id]
        
        logger.info(f"Deleted user data for user_id {user_id}: {messages_deleted} messages, {interactions_deleted} interactions")
        return True, messages_deleted, interactions_deleted
        
    except Exception as e:
        # If anything goes wrong, roll back the transaction
        conn.rollback()
        logger.error(f"Error deleting user data: {str(e)}")
        return False, 0, 0
    finally:
        conn.close()

def call_apps_script(script_id, function_name, parameters):
    """Calls a Google Apps Script function with extensive logging."""
    logger.info(f"Initiating call to Apps Script ID: {script_id}, Function: {function_name}")
    logger.debug(f"Apps Script parameters: {parameters}") # Log parameters at debug level

    # Get credentials for Apps Script API
    apps_script_scope = ["https://www.googleapis.com/auth/script.execute"]
    credentials = get_credentials_for_google_apis(scopes=apps_script_scope)

    if not credentials:
        # get_credentials already logs the error extensively
        logger.error("Failed to obtain credentials for Apps Script call.")
        return None, "Authentication failed. Could not get credentials."

    # Log credential details (avoid logging full token)
    logger.info(f"Using credentials for service account: {credentials.service_account_email}")
    logger.debug(f"Credentials valid: {credentials.valid}, Scopes: {credentials.scopes}")

    try:
        logger.info("Building Apps Script API service (script, v1)...")
        service = build('script', 'v1', credentials=credentials)
        logger.info("Apps Script API service built successfully.")

        # Create the request body
        request = {
            'function': function_name,
            'parameters': parameters,
            'devMode': False  # Set to True only if debugging the Apps Script itself
        }
        logger.info(f"Executing Apps Script function '{function_name}'...")
        logger.debug(f"Apps Script request body: {request}")

        # Make the API call to run the script
        response = service.scripts().run(scriptId=script_id, body=request).execute()
        logger.info(f"Received response from Apps Script execution.")
        logger.debug(f"Raw Apps Script response: {response}") # Log raw response at debug level

        # Check for errors returned by the Apps Script execution itself
        if 'error' in response:
            error_details = response['error'].get('details', [{}])[0]
            error_message = error_details.get('errorMessage', 'Unknown script execution error')
            error_type = error_details.get('errorType', 'UnknownType')
            script_stack_trace = error_details.get('scriptStackTraceElements', [])

            logger.error(f"Apps Script execution error: Type={error_type}, Message={error_message}")
            if script_stack_trace:
                logger.error(f"Apps Script Stacktrace: {script_stack_trace}")

            # Provide a more user-friendly message based on common issues
            if "Authorization is required" in error_message or "Script has attempted to perform an action" in error_message:
                 user_error = "Authorization error within the Apps Script. Ensure the script has the necessary permissions."
            elif "not found" in error_message: # Function or variable not found
                 user_error = f"Error within the Apps Script: '{function_name}' or related code not found."
            else:
                 user_error = f"Error during script execution: {error_message}"
            return None, user_error

        # Extract the result if execution was successful
        result = response.get('response', {}).get('result')
        logger.info(f"Apps Script execution successful. Result type: {type(result)}")
        logger.debug(f"Apps Script result: {result}") # Log result at debug level
        return result, None # Return result and no error

    except HttpError as http_error:
        status_code = http_error.resp.status
        error_content = http_error.content.decode('utf-8')
        logger.error(f"HTTP error calling Apps Script API: Status={status_code}, Response={error_content}", exc_info=True)

        # Provide specific user messages based on HTTP status code
        if status_code == 401: # Unauthorized
            user_error = "Authentication failed (401). Check service account credentials and API access."
        elif status_code == 403: # Forbidden
            user_error = "Permission denied (403). Ensure the Apps Script API is enabled and the service account has permission to execute the script."
        elif status_code == 404: # Not Found
            user_error = f"Apps Script project (ID: {script_id}) not found (404)."
        elif status_code == 429: # Rate Limited
             user_error = "API rate limit exceeded (429). Please try again later."
        else:
            user_error = f"API error occurred ({status_code}). Check logs for details."
        return None, user_error

    except Exception as e:
        logger.error(f"Unexpected error calling Apps Script: {e}", exc_info=True)
        return None, "An unexpected error occurred while communicating with the Apps Script service."

def get_sheet_data_via_webapp(id_to_find):
    """Retrieves data from the Google Sheet via the deployed Apps Script Web App."""
    logger.info(f"Initiating call to Apps Script Web App for ID: {id_to_find}")

    # Check if configuration is available
    if not APPS_SCRIPT_WEB_APP_URL or not APPS_SCRIPT_API_KEY:
        logger.error("Web App URL or API Key is not configured.")
        return None, "Web App retrieval is not configured on the server."

    try:
        # Construct the URL with query parameters
        params = {
            'id': id_to_find,
            'apiKey': APPS_SCRIPT_API_KEY
        }
        target_url = APPS_SCRIPT_WEB_APP_URL
        logger.info(f"Making GET request to Web App URL (parameters omitted for security)")
        # For debugging ONLY, uncomment the next line:
        # logger.debug(f"Request URL: {target_url}?id={id_to_find}&apiKey={APPS_SCRIPT_API_KEY[:4]}...")

        # --- START MODIFICATION ---
        logger.info(f"Attempting requests.get to {target_url} with timeout=30...") # Add log BEFORE request
        # Make the GET request
        response = requests.get(target_url, params=params, timeout=30) # Existing request
        logger.info(f"requests.get call completed. Status code received: {response.status_code}") # Add log AFTER request
        # --- END MODIFICATION ---

        # Log basic response info (existing log)
        logger.info(f"Received response from Web App. Status: {response.status_code}, Content-Type: {response.headers.get('Content-Type')}")
        logger.debug(f"Raw response text (first 500 chars): {response.text[:500]}")

        # Check for HTTP errors (4xx or 5xx)
        response.raise_for_status()

        # Check for specific text responses indicating errors from the script itself
        if response.text == "Not Found":
            logger.warning(f"Web App returned 'Not Found' for ID: {id_to_find}")
            return None, f"ID '{id_to_find}' not found in the Google Sheet."
        if response.text == "Unauthorized":
            logger.error("Web App returned 'Unauthorized'. Check the API Key.")
            return None, "Authorization failed. Invalid API Key provided to Web App."
        if response.text == "Bad Request":
             logger.error("Web App returned 'Bad Request'. Check if 'id' parameter is missing or invalid.")
             return None, "Bad request sent to the Web App (e.g., missing ID)."

        # Attempt to parse the JSON response
        try:
            json_result = response.json()
            logger.info(f"Successfully parsed JSON response from Web App for ID: {id_to_find}")
            return json_result, None # Return data and no error
        except json.JSONDecodeError as json_err:
            logger.error(f"Failed to decode JSON response from Web App: {json_err}")
            logger.error(f"Response text was: {response.text}")
            return None, "Received invalid data format from the Web App."

    except requests.exceptions.Timeout:
         logger.error(f"Request to Web App timed out for ID: {id_to_find}")
         return None, "The request to the Web App timed out."
    except requests.exceptions.RequestException as req_err:
        logger.error(f"HTTP request error calling Web App: {req_err}", exc_info=True)
        # Try to provide more specific feedback based on status code if available
        status_code = getattr(req_err.response, 'status_code', None)
        if status_code == 401: # Often means script requires login / incorrect sharing
             user_error = "Web App access denied (401). Check script permissions/deployment settings."
        elif status_code == 403: # Might mean API key mismatch or other permission issue
             user_error = "Web App forbidden (403). Check API key or script access settings."
        elif status_code == 404: # URL incorrect
             user_error = "Web App URL not found (404). Check the configured URL."
        elif status_code == 500: # Internal server error in the script
             user_error = "Error within the Web App script (500). Check script logs."
        else:
             user_error = f"Network error communicating with the Web App: {req_err}"
        return None, user_error
    except Exception as e:
        logger.error(f"Unexpected error retrieving data via Web App: {e}", exc_info=True)
        return None, "An unexpected error occurred while contacting the Web App."

# Function to create the main menu with interactive buttons
def generate_main_menu():
    # Create a new inline keyboard markup (buttons that appear in the message)
    markup = InlineKeyboardMarkup()
    markup.row_width = 2  # Set how many buttons to show in each row
    
    # Add buttons to the markup
    markup.add(
        InlineKeyboardButton("📊 Analyze My Messages", callback_data="menu1"),
        InlineKeyboardButton("📄 Retrieve Form Data", callback_data="retrieve_form"),
        InlineKeyboardButton("📈 Retrieve Sheet Data", callback_data="retrieve_sheet_data"), # <-- ADD THIS LINE
        InlineKeyboardButton("Menu 2", callback_data="menu2")
    )
    # Add data management buttons in new rows
    markup.add(
        InlineKeyboardButton("📊 View My Data", callback_data="view_my_data")  # View data button
    )
    
    markup.add(
        InlineKeyboardButton("🗑️ Delete My Data", callback_data="delete_my_data")  # Delete data button
    )

    # Add Web App buttons only if not in DEBUG_MODE (requires valid BASE_URL)
    # Also check if BASE_URL starts with https, as required by Telegram Web Apps
    logger.debug(f"generate_main_menu: DEBUG_MODE={DEBUG_MODE}, BASE_URL='{BASE_URL}'") # DEBUG Log
    if not DEBUG_MODE and BASE_URL and BASE_URL.startswith("https://"):
        logger.info("generate_main_menu: Conditions met for adding Web App buttons.") # INFO Log
        web_app_buttons = []
        # Check if the URLs seem valid (basic check) - Assuming profile URL might exist
        # logger.debug(f"Checking Profile URL: {WEBAPP_EDIT_PROFILE_URL}") # DEBUG Log
        # if WEBAPP_EDIT_PROFILE_URL and WEBAPP_EDIT_PROFILE_URL.startswith("https://"):
        #     logger.info("generate_main_menu: Adding 'Edit My Profile' button.") # INFO Log
        #     web_app_buttons.append(
        #         InlineKeyboardButton("✏️ Edit My Profile", web_app=WebAppInfo(WEBAPP_EDIT_PROFILE_URL))
        #     )
        logger.debug(f"Checking Messages URL: {WEBAPP_EDIT_MESSAGES_URL}") # DEBUG Log
        if WEBAPP_EDIT_MESSAGES_URL and WEBAPP_EDIT_MESSAGES_URL.startswith("https://"):
            logger.info("generate_main_menu: Adding 'Edit My Messages' button.") # INFO Log
            web_app_buttons.append(
                 InlineKeyboardButton("📝 Edit My Messages", web_app=WebAppInfo(WEBAPP_EDIT_MESSAGES_URL))
            )

        if web_app_buttons:
             logger.info(f"generate_main_menu: Calling markup.add() with {len(web_app_buttons)} web app button(s).") # INFO Log
             # Add buttons in a new row or append to existing logic as needed
             markup.add(*web_app_buttons) # Adds buttons in a row
        else:
             # This warning should NOT appear if BASE_URL is correct and DEBUG_MODE is False
             logger.warning("generate_main_menu: No valid Web App buttons created, skipping markup.add().")
    elif not BASE_URL or not BASE_URL.startswith("https://"):
        # This warning should NOT appear if BASE_URL is correct
        logger.warning("generate_main_menu: BASE_URL is not set or does not use HTTPS. Web App buttons will not be shown.")
    else: # This case means DEBUG_MODE is True
         logger.info("generate_main_menu: DEBUG_MODE is True, skipping Web App buttons.")


    return markup  # Return the created menu

# Function to create submenus based on which main menu item was selected
def generate_submenu(menu_id):
    # Create a new inline keyboard markup for the submenu
    markup = InlineKeyboardMarkup()
    markup.row_width = 2  # Set how many buttons to show in each row
    
    # Add three buttons to the submenu
    markup.add(
        # First submenu item - uses f-strings to include the menu_id in the text and callback_data
        InlineKeyboardButton(f"{menu_id} Subitem 1", callback_data=f"{menu_id}_sub1"),
        # Second submenu item
        InlineKeyboardButton(f"{menu_id} Subitem 2", callback_data=f"{menu_id}_sub2"),
        # Back button to return to main menu
        InlineKeyboardButton("Back to Main Menu", callback_data="main_menu")
    )
    return markup  # Return the created submenu

def send_main_menu_message(chat_id, text="Choose an option from the menu:"):
    """Sends a new message with the main menu."""
    try:
        bot.send_message(
            chat_id,
            text,
            reply_markup=generate_main_menu()
        )
        logger.info(f"Sent main menu as a new message to chat {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send main menu message to chat {chat_id}: {e}")



@bot.message_handler(commands=['generate_file'])
def send_welcome(message):
    chat_id = message.chat.id
    
    # Step 1: Generate a file with some content
    file_name = "example.txt"
    with open(file_name, "w") as file:
        file.write("Hello! This is your generated file.\n")
        file.write("This is an example of a Telegram bot sending files.")
    
    # Step 2: Send the file to the user
    with open(file_name, "rb") as file:
        bot.send_document(chat_id, file)
        
# Handler for /start and /help commands
# This decorator tells the bot to call this function when users send these commands
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    # Get the user ID to track this specific user's session
    user_id = message.from_user.id
    chat_id = message.chat.id
    logger.info(f"Received /start or /help command from user {user_id} in chat {chat_id}")

    try: # <<< ADD try block here
        # Save user information to database with chat_id
        save_user(message.from_user, chat_id)

        # Save the message to the database
        save_message(message)

        # Log this interaction
        command = message.text.split()[0].replace('/', '')
        log_interaction(user_id, f"command_{command}")

        # Get user preferences
        prefs = get_user_preferences(user_id)

        # Initialize or reset the user's session
        user_sessions[user_id] = {
            'state': 'main_menu',
            'data': {},
            'preferences': prefs
        }

        # Welcome text based on language preference
        welcome_text = "Welcome to the bot! Choose an option:"
        if prefs['language'] == 'es':
            welcome_text = "¡Bienvenido al bot! Elige una opción:"

        # Use send_main_menu_message to send a message with the main menu
        send_main_menu_message(chat_id, welcome_text)
        logger.info(f"Sent welcome message with main menu to user {user_id}")

    except Exception as e: # <<< ADD except block here
        logger.error(f"Error during send_welcome for user {user_id}: {e}", exc_info=True) # Log error with traceback
        try:
            # Attempt to send an error message to the user
            bot.reply_to(message, "Sorry, something went wrong while starting our chat. Please try /start again later.")
        except Exception as send_error:
            logger.error(f"Failed to send error message to user {user_id} after initial error: {send_error}")


def find_form_response_id(user_id, search_limit=20):
    """Search recent user messages for the form=ID pattern."""
    logger.info(f"Searching for 'form=<ID>' in last {search_limit} messages for user {user_id}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT message_text
        FROM user_messages
        WHERE user_id = ? AND message_text IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT ?
    """, (user_id, search_limit))

    response_id = None
    pattern = re.compile(r"form=(\d+)", re.IGNORECASE) # Pattern: form= followed by digits

    for row in cursor.fetchall():
        message_text = row[0]
        match = pattern.search(message_text)
        if match:
            response_id = match.group(1) # Extract the digits
            logger.info(f"Found response ID: {response_id} in message: '{message_text}'")
            break # Stop after finding the first match

    conn.close()
    if not response_id:
        logger.warning(f"Could not find 'format=<ID>' pattern for user {user_id}")
    return response_id


def get_google_form_response(form_id, response_id):
    """Retrieves a specific response from a Google Form."""
    logger.info(f"Attempting to retrieve response {response_id} from form {form_id}")

    # Get credentials for Google Forms API
    forms_scope = ["https://www.googleapis.com/auth/forms.responses.readonly"]
    credentials = get_credentials_for_google_apis(scopes=forms_scope)

    if not credentials:
        logger.error("Failed to get credentials for Google Forms API.")
        return None, "Authentication failed."

    try:
        # Build the service object
        service = build('forms', 'v1', credentials=credentials)

        # Retrieve the response
        result = service.forms().responses().get(
            formId=form_id,
            responseId=response_id
        ).execute()

        logger.info(f"Successfully retrieved form response {response_id}")
        return result, None # Return data and no error

    except HttpError as error:
        error_details = error.resp.get('content', '{}')
        try:
             error_json = json.loads(error_details)
             error_message = error_json.get('error', {}).get('message', 'Unknown API error')
             status_code = error_json.get('error', {}).get('code', error.resp.status)
        except json.JSONDecodeError:
             error_message = f"API Error (Status: {error.resp.status})"
             status_code = error.resp.status

        logger.error(f"Google Forms API error: {status_code} - {error_message}")
        if status_code == 404:
             return None, f"Response ID '{response_id}' not found in form '{form_id}'."
        elif status_code == 403:
             return None, "Permission denied. Ensure the service account has access to the form responses."
        else:
             return None, f"API Error: {error_message}"
    except Exception as e:
        logger.error(f"Unexpected error retrieving form response: {e}", exc_info=True)
        return None, "An unexpected error occurred."


# Function to get user's message history
def get_user_message_history(user_id, limit=10):
    """Get the message history for a specific user"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get user messages ordered by timestamp (newest first)
    # Include both regular text messages and processed text from images
    cursor.execute("""
    SELECT message_text, timestamp
    FROM user_messages
    WHERE user_id = ? 
      AND message_text IS NOT NULL 
      AND message_text != '' 
      AND message_text != '/start' -- Exclude /start messages
      AND (message_type = 'text' OR message_type = 'processed_text_from_image' OR message_type = 'retrieved_sheet_data')
    ORDER BY timestamp DESC
    LIMIT ?
    """, (user_id, limit))
    
    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    logger.info(f"Retrieved {len(messages)} messages for user {user_id}, including processed image text")
    return messages

# Image processing functions
def download_image_from_telegram(file_id, user_id, message_id):
    """
    Download an image from Telegram servers using file_id
    Returns: Path to downloaded file or None if download failed
    """
    logger.info(f"Starting image download process for file_id: {file_id}, user_id: {user_id}, message_id: {message_id}")
    
    try:
        # Get file info from Telegram
        file_info = bot.get_file(file_id)
        file_path = file_info.file_path
        
        # Create a unique filename using uuid
        temp_dir = tempfile.gettempdir()
        unique_filename = f"{uuid.uuid4().hex}.jpg"
        local_file_path = os.path.join(temp_dir, unique_filename)
        
        # Download the file
        downloaded_file = bot.download_file(file_path)
        
        # Save the file locally
        with open(local_file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        file_size = os.path.getsize(local_file_path)
        logger.info(f"Successfully downloaded image to {local_file_path} (Size: {file_size} bytes)")
        
        return local_file_path
    
    except Exception as e:
        logger.error(f"Error downloading image: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def process_image_with_gemini(image_path, user_id):
    """
    Process an image using Gemini 2.0 Lite API with service account authentication
    Returns: Parsed JSON response or None if processing failed
    """
    logger.info(f"Initiating Gemini API request for image from user_id: {user_id}")

    try:
        # Use the dedicated Gemini credentials function
        credentials = get_credentials_for_gemini()
        
        if not credentials:
            logger.error("Failed to get authenticated credentials")
            return None
        
        # Read the image file as binary data
        with open(image_path, 'rb') as image_file:
            image_data = image_file.read()
        
        # Encode image to base64
        encoded_image = base64.b64encode(image_data).decode('utf-8')
        
        # Prepare the request payload
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": s.GEMINI_PROMPT_IMAGE_ANALYSIS},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": encoded_image
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.4,
                "topK": 32,
                "topP": 1,
                "maxOutputTokens": 4096
            }
        }
        
        logger.info(f"Sending image data to Gemini API")
        
        # Get an access token from the credentials
        auth_req = GoogleAuthRequest()
        credentials.refresh(auth_req)
        access_token = credentials.token
        
        # Log token information (without revealing the full token)
        token_preview = access_token[:10] + "..." if access_token else "None"
        logger.info(f"Using token starting with: {token_preview} for image processing")
        
        # Make the API request with the access token
        response = requests.post(
            GEMINI_API_ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            },
            data=json.dumps(payload)
        )
        
        # Log the raw response
        logger.info(f"Received raw response from Gemini API: {response.text[:500]}...")
        
        # Check if the request was successful
        if response.status_code == 200:
            logger.info("Successfully received response from Gemini API")
            
            # Parse the JSON response
            logger.info("Starting JSON parsing of Gemini API response")
            parsed_response = response.json()
            logger.info("Successfully parsed JSON response")
            
            return parsed_response
        else:
            logger.error(f"Gemini API request failed with status code: {response.status_code}")
            logger.error(f"Error response: {response.text}")
            return None
    
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON response: {str(e)}")
        logger.error(traceback.format_exc())
        return None
    except Exception as e:
        logger.error(f"Error processing image with Gemini: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def save_image_processing_result(user_id, message_id, file_id, gemini_response):
    """
    Save the Gemini API response to the database
    """
    logger.info(f"Initiating database storage for Gemini API response for user_id: {user_id}, message_id: {message_id}")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Convert the response to a JSON string
        gemini_response_json = json.dumps(gemini_response)
        
        # Insert the record
        cursor.execute("""
        INSERT INTO image_processing_results (user_id, message_id, file_id, gemini_response)
        VALUES (?, ?, ?, ?)
        """, (user_id, message_id, file_id, gemini_response_json))
        
        # Get the inserted record ID
        record_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        logger.info(f"Successfully stored Gemini API response in database (record ID: {record_id})")
        return True
    
    except Exception as e:
        logger.error(f"Error saving image processing result to database: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def extract_text_from_gemini_response(gemini_response):
    """
    Extract the text content from Gemini API response and format it as pipe-separated key-value pairs
    """
    try:
        # Check if response is already a dictionary (parsed JSON)
        if isinstance(gemini_response, dict):
            response_dict = gemini_response
        else:
            # Try to parse the response as JSON if it's a string
            if isinstance(gemini_response, str):
                response_dict = json.loads(gemini_response)
            else:
                # If it's neither a dict nor a string, assume it's already the parsed object
                response_dict = gemini_response
        
        # Initialize all_text to collect the text from all parts
        all_text = ""
        
        # If it's a list of responses (like in gemini_response.json)
        if isinstance(response_dict, list):
            # Extract text from all parts in all responses
            for response_segment in response_dict:
                if "candidates" in response_segment and response_segment["candidates"]:
                    candidate = response_segment["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        for part in candidate["content"]["parts"]:
                            if "text" in part:
                                all_text += part["text"]
        
        # Handle single response format
        elif "candidates" in response_dict and response_dict["candidates"]:
            candidate = response_dict["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                for part in candidate["content"]["parts"]:
                    if "text" in part:
                        all_text += part["text"]
        else:
            logger.warning(f"Unexpected response format: {response_dict}")
            return "No text content found in the response."
        
        # If we didn't extract any text, return a message
        if not all_text:
            logger.warning("No text was extracted from the response")
            return "No text content found in the response."
        
        # Clean up the text - remove code blocks, markdown formatting, etc.
        all_text = all_text.replace("```json", "").replace("```", "").strip()
        
        # If the text contains JSON, extract the values and convert to pipe-separated format
        if "{" in all_text and "}" in all_text:
            try:
                # Try to extract JSON content
                json_start = all_text.find("{")
                json_end = all_text.rfind("}") + 1
                json_content = all_text[json_start:json_end]
                
                # Parse the JSON
                data = json.loads(json_content)
                
                # Convert to pipe-separated format
                pipe_format = "|".join([f"{key}={value}" for key, value in data.items()])
                return pipe_format
            except json.JSONDecodeError:
                # If JSON parsing fails, return the cleaned text
                # Remove any remaining markdown formatting
                all_text = all_text.replace("`", "").replace("**", "")
                return all_text
        
        # If the text already contains pipe-separated values, just return it
        if "|" in all_text and "=" in all_text:
            # Remove any markdown formatting
            all_text = all_text.replace("`", "").replace("**", "")
            return all_text
            
        # Otherwise, return the cleaned text
        all_text = all_text.replace("`", "").replace("**", "")
        return all_text
        
    except Exception as e:
        logger.error(f"Error extracting text from Gemini response: {str(e)}")
        logger.error(f"Response type: {type(gemini_response)}")
        if isinstance(gemini_response, (dict, list)):
            logger.error(f"Response preview: {str(gemini_response)[:500]}")
# Handler for photo messages
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    """Handle photos sent by users"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    message_id = message.message_id
    logger.info(f"Received photo from user {user_id} in chat {chat_id}, message_id {message_id}") # Added message_id logging

    # Save user information to database with chat_id
    save_user(message.from_user, chat_id)
    
    # Save the message to the database
    save_message(message)
    
    # Log this interaction
    log_interaction(user_id, "photo_message")
    
    # Get the file ID of the largest photo (best quality)
    if message.photo:
        file_id = message.photo[-1].file_id
        logger.info(f"Image received from user {user_id} with message ID {message_id}. File ID: {file_id}")

        # Send a processing message to the user
        processing_message = bot.reply_to(message, "Processing your image... Please wait.")

        image_path = None # Initialize image_path
        try:
            # Download the image
            image_path = download_image_from_telegram(file_id, user_id, message_id)

            if not image_path:
                bot.edit_message_text(
                    "Sorry, I couldn't download your image. Please try again later.",
                    chat_id=chat_id,
                    message_id=processing_message.message_id
                )
                log_interaction(user_id, 'download_image_error', {'file_id': file_id}) # Log download error
                return

            # Process the image with Gemini API
            logger.info(f"Starting image processing workflow for user {user_id}")
            gemini_response = process_image_with_gemini(image_path, user_id)
            
            if not gemini_response:
                bot.edit_message_text(
                    "Sorry, I couldn't process your image with our AI service. Please try again later.",
                    chat_id=chat_id,
                    message_id=processing_message.message_id
                )
                log_interaction(user_id, 'gemini_processing_error', {'error': 'No response'}) # Log processing error
                # No cleanup needed here, finally block handles it
                return

            # Extract the text content from the response (pipe-separated string)
            result_text = extract_text_from_gemini_response(gemini_response)
            logger.info(f"Extracted text from Gemini for user {user_id}: {result_text[:100]}...") # Log extracted text preview

            # --- START MODIFICATION ---

            # Convert the pipe-separated string to a JSON string
            json_to_save = None
            try:
                if result_text and '|' in result_text and '=' in result_text:
                    pairs = result_text.strip().split('|')
                    data_dict = {}
                    for pair in pairs:
                        if '=' in pair:
                            key, value = pair.split('=', 1)
                            # Handle potential 'null' string for age or empty strings
                            if value.lower() == 'null':
                                data_dict[key.strip()] = None
                            else:
                                data_dict[key.strip()] = value.strip()
                        else:
                            logger.warning(f"Skipping invalid pair '{pair}' in Gemini response for user {user_id}")
                    if data_dict: # Only convert if we successfully parsed something
                        json_to_save = json.dumps(data_dict, ensure_ascii=False, indent=2)
                        logger.info(f"Successfully converted extracted text to JSON for user {user_id}")
                    else:
                         logger.warning(f"Could not parse any valid key-value pairs from Gemini response for user {user_id}. Saving original text.")
                         json_to_save = result_text # Fallback to saving original text
                else:
                    logger.warning(f"Extracted text for user {user_id} does not seem to be pipe-separated key-value pairs. Saving original text.")
                    json_to_save = result_text # Fallback to saving original text

            except Exception as e:
                logger.error(f"Error converting pipe-separated string to JSON for user {user_id}: {e}", exc_info=True)
                json_to_save = result_text # Fallback to saving original text in case of error

            # Save the result (JSON string or original text) to database
            # Use json_to_save which holds either the JSON string or the original result_text
            save_image_processing_success = save_image_processing_result(user_id, message_id, file_id, json_to_save)

            # --- START: Save processed text to user_messages ---
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO user_messages (user_id, chat_id, message_id, message_text, message_type, has_media, media_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (user_id, chat_id, message_id, json_to_save, 'processed_text_from_image', False, None))
                conn.commit()
                conn.close()
                logger.info(f"Saved processed text (JSON or original) to user_messages for user {user_id}, original message_id {message_id}")
            except Exception as db_err:
                logger.error(f"Error saving processed text to user_messages for user {user_id}: {db_err}", exc_info=True)
            # --- END: Save processed text to user_messages ---

            # --- END MODIFICATION --- # This comment seems misplaced from the original code, keeping structure

            if not save_image_processing_success: # Check the success of saving to image_processing_results
                logger.warning(f"Failed to save image processing result to database for user {user_id}")
                # Continue anyway, as we can still return the result to the user

            # --- REMOVE MockMessage and history logic ---
            # Remove the following lines:
            # class MockMessage: ... (entire class definition if it's only used here)
            # mock_message = MockMessage(user_id, chat_id, result_text)
            # save_message(mock_message)
            # message_history = get_user_message_history(user_id, limit=10)
            # if message_history: ... (entire if/else block sending history)

            # --- MODIFY final user message ---
            # Send the extracted text directly back to the user
            final_message_text = f"Extracted Information:\n\n{result_text}"
            if len(final_message_text) > 4096: # Telegram message length limit
                final_message_text = final_message_text[:4093] + "..."
                logger.warning(f"Truncated long extracted text message for user {user_id}")

            bot.edit_message_text(
                final_message_text,
                chat_id=chat_id,
                message_id=processing_message.message_id
            )
            log_interaction(user_id, 'sent_extracted_text', {'length': len(result_text)}) # Log sending result

            # Log successful completion
            logger.info(f"Successfully completed image processing workflow for user {user_id}")

            # --- ADD THIS ---
            # Send the main menu as a new message after successful photo processing
            send_main_menu_message(chat_id, text="Image processed. What would you like to do next?")
            # --- END ADD ---

        except Exception as e:
            logger.error(f"Error in image processing workflow: {str(e)}", exc_info=True) # Use exc_info=True for traceback

            # Inform the user
            try:
                bot.edit_message_text(
                    "Sorry, an error occurred while processing your image. Please try again later.",
                    chat_id=chat_id,
                    message_id=processing_message.message_id
                )
            except Exception as api_e: # Catch potential error editing message if original failed badly
                 logger.error(f"Failed to send error message to user {user_id}: {api_e}")

            log_interaction(user_id, 'photo_workflow_error', {'error': str(e)}) # Log workflow error

        finally:
            # Clean up the temporary file
            cleanup_temp_file(image_path) # cleanup_temp_file already logs success/failure
            logger.info(f"Completed image processing workflow cleanup for user {user_id}")
    else:
        # No photo found in the message
        bot.reply_to(message, "I couldn't find any image in your message. Please try sending it again.")
        log_interaction(user_id, 'photo_message_no_data')
        # --- ADD THIS ---
        # Send menu if the user sent a 'photo' message type without actual photo data
        send_main_menu_message(chat_id)
        # --- END ADD ---

# Handler for text messages
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text(message):
    # Get the user ID
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Save user information to database
    save_user(message.from_user, chat_id)
    
    # Save the message to the database
    save_message(message)
    
    # Log this interaction
    log_interaction(user_id, "text_message")
    
    # If we're not handling this message with a specific command handler,
    # we can add default behavior here
    if message.text.startswith('/'):
        # It's a command we don't recognize
        bot.reply_to(message, "Sorry, I don't understand that command.")
    else:
        if (DEBUG_MODE == True):
            # Get the user's message history
            message_history = get_user_message_history(user_id, limit=10) # Descomentar para que conteste con la history
        else:
            message_history = []
        
        # Format the message history
        if message_history:
            # Create a formatted message with the user's message history
            history_text = "📝 Your message history:\n\n"
            
            # Skip the most recent message (the one just sent)
            for i, msg in enumerate(message_history[1:], 1):
                # Format the timestamp
                timestamp = datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00'))
                formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                
                # Add the message to the history text
                history_text += f"{i}. [{formatted_time}] {msg['message_text']}\n"
            
            # If there are no previous messages (only the current one)
            if len(message_history) <= 1:
                history_text += "No previous messages found."
                
            # Send the message history back to the user
            bot.reply_to(message, history_text)
        else:
            # Default reply if not a command and history display is off or empty
            bot.reply_to(message, "Received your message.") # Simplified reply

    # --- MODIFY THIS SECTION ---
    # Send the main menu only if the message was not a command
    if not message.text.startswith('/'):
        send_main_menu_message(chat_id)
        logger.info(f"Sent main menu after handling non-command text from chat {chat_id}")
    else:
        # Log that we skipped sending the menu because it was a command
        logger.info(f"Skipped sending main menu from handle_text for command '{message.text}' in chat {chat_id}")
    # --- END MODIFICATION ---

# Function to create a confirmation menu for data deletion
def generate_delete_confirmation_menu():
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    
    markup.add(
        InlineKeyboardButton("✅ Yes, Delete My Data", callback_data="confirm_delete"),
        InlineKeyboardButton("❌ No, Keep My Data", callback_data="cancel_delete")
    )
    
    return markup

# Handler for button clicks (callback queries)
# This decorator tells the bot to call this function when users click any button
@bot.callback_query_handler(func=lambda call: True)  # The lambda function means "handle all callbacks"
def handle_callback_query(call):
    # Get the user ID to ensure we're handling the correct user's session
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # Save user information to database with chat_id
    save_user(call.from_user, chat_id)
    
    # Log this interaction
    log_interaction(user_id, "button_click", call.data)
    
    # Ensure the user has a session, create one if not
    if user_id not in user_sessions:
        # Get user preferences
        prefs = get_user_preferences(user_id)
        
        user_sessions[user_id] = {
            'state': 'main_menu',
            'data': {},
            'preferences': prefs
        }
    # Check which button was clicked by examining the callback_data

    if call.data == "retrieve_form":
        logger.info(f"User {user_id}: Clicked 'Retrieve Form Data'")
        log_interaction(user_id, "button_click", call.data)

        # Check if Form ID is configured
        if not GOOGLE_FORM_ID:
            bot.answer_callback_query(call.id, "Form retrieval is not configured.", show_alert=True)
            logger.warning("Retrieve form called, but GOOGLE_FORM_ID is not set.")
            # Optionally edit message back to main menu if needed
            # bot.edit_message_text(...)
            return # Stop processing

        # Send processing message
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Searching for form response ID in your recent messages..."
        )

        # 1. Find the response ID
        response_id = find_form_response_id(user_id)

        if not response_id:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Could not find a message with 'form=<number>' in your recent history.",
                reply_markup=generate_main_menu()
            )
            return # Stop processing

        # 2. Retrieve the form data
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"Found ID: {response_id}. Retrieving data from Google Form..."
        )

        form_data, error_message = get_google_form_response(GOOGLE_FORM_ID, response_id)

        if form_data:
            # --- START: Store retrieved form data as JSON in user_messages ---
            try:
                # Convert the form_data dictionary (returned by Google API) to a JSON string
                form_data_json_string = json.dumps(form_data, indent=2, ensure_ascii=False)

                # Connect to DB and insert the JSON string as a new message record
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO user_messages (user_id, chat_id, message_id, message_text, message_type, has_media, media_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (user_id, chat_id, call.message.message_id, form_data_json_string, 'retrieved_form_data', False, None))
                # Note: Using call.message.message_id associates this data with the message containing the button.
                conn.commit()
                conn.close()
                logger.info(f"Stored retrieved form data JSON in user_messages for user {user_id}, associated with original message_id {call.message.message_id}")

            except Exception as db_store_err:
                logger.error(f"Error storing retrieved form data JSON in user_messages for user {user_id}: {db_store_err}", exc_info=True)
                # Decide if you want to notify the user about this specific failure; currently, it only logs.
            # --- END: Store retrieved form data ---

            # Success - Display the data (e.g., as JSON)
            try:
                # Format the response data nicely (e.g., extract answers)
                # For now, just display the raw JSON, truncated if too long
                response_text = json.dumps(form_data, indent=2, ensure_ascii=False)
                display_text = f"📄 Form Response Data (ID: {response_id}):\n\n```json\n{response_text}\n```"

                if len(display_text) > 4000: # Keep under Telegram limit, accounting for markdown
                    display_text = display_text[:4000] + "... (truncated)\n```"

                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=display_text,
                    reply_markup=generate_main_menu(),
                    parse_mode="Markdown" # Use Markdown for code block
                )
                log_interaction(user_id, "form_retrieval_success", {'response_id': response_id})

            except Exception as display_e:
                 logger.error(f"Error formatting/displaying form data: {display_e}", exc_info=True)
                 bot.edit_message_text(
                     chat_id=call.message.chat.id,
                     message_id=call.message.message_id,
                     text=f"Successfully retrieved data for response {response_id}, but failed to display it.",
                     reply_markup=generate_main_menu()
                 )

        else:
            # Failure - Display error message
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"❌ Failed to retrieve form data:\n{error_message}",
                reply_markup=generate_main_menu()
            )
            log_interaction(user_id, "form_retrieval_failed", {'response_id': response_id, 'error': error_message})

    elif call.data == "retrieve_sheet_data":
        logger.info(f"User {user_id}: Clicked 'Retrieve Sheet Data'")
        log_interaction(user_id, "button_click", call.data)

        # Check if Apps Script ID is configured
        if not APPS_SCRIPT_ID:
            bot.answer_callback_query(call.id, "Sheet retrieval via Apps Script is not configured.", show_alert=True)
            logger.warning("Retrieve sheet data called, but APPS_SCRIPT_ID is not set.")
            return # Stop processing

        # Send processing message
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Searching for ID (form=<number>) in your recent messages..."
        )

        # 1. Find the ID to search for (reuse the form ID finding logic)
        id_to_find = find_form_response_id(user_id) # Reusing the function as the pattern is the same

        if not id_to_find:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Could not find a message with 'form=<number>' in your recent history to use as the ID.",
                reply_markup=generate_main_menu()
            )
            return # Stop processing

        # 2. Call the Web App to retrieve data
        logger.info(f"Calling get_sheet_data_via_webapp for ID: {id_to_find}") # Modified log message
        sheet_data, error_message = get_sheet_data_via_webapp(id_to_find)

        if sheet_data is not None: # Check if data was returned (could be empty JSON {} or [])
            # --- START: Store retrieved sheet data as JSON in user_messages ---
            try:
                # Convert the sheet_data (already likely JSON/dict) to a formatted JSON string
                sheet_data_json_string = json.dumps(sheet_data, indent=2, ensure_ascii=False)

                # Connect to DB and insert the JSON string as a new message record
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO user_messages (user_id, chat_id, message_id, message_text, message_type, has_media, media_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (user_id, chat_id, call.message.message_id, sheet_data_json_string, 'retrieved_sheet_data', False, None))
                # Note: Using call.message.message_id associates this data with the message containing the button.
                conn.commit()
                conn.close()
                logger.info(f"Stored retrieved sheet data JSON in user_messages for user {user_id}, associated with original message_id {call.message.message_id}")

            except Exception as db_store_err:
                logger.error(f"Error storing retrieved sheet data JSON in user_messages for user {user_id}: {db_store_err}", exc_info=True)
                # Decide if you want to notify the user about this specific failure; currently, it only logs.
            # --- END: Store retrieved sheet data ---
            # Success - Display the data (assuming it's JSON)
            try:
                # Format the response data nicely (as JSON)
                response_text = json.dumps(sheet_data, indent=2, ensure_ascii=False)
                display_text = f"📈 Sheet Data (ID: {id_to_find}):\n\n```json\n{response_text}\n```"

                if len(display_text) > 4000: # Keep under Telegram limit
                    display_text = display_text[:4000] + "... (truncated)\n```"

                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=display_text,
                    reply_markup=generate_main_menu(),
                    parse_mode="Markdown" # Use Markdown for code block
                )
                log_interaction(user_id, "sheet_retrieval_success", {'id_found': id_to_find})

            except Exception as display_e:
                 logger.error(f"Error formatting/displaying sheet data: {display_e}", exc_info=True)
                 bot.edit_message_text(
                     chat_id=call.message.chat.id,
                     message_id=call.message.message_id,
                     text=f"Successfully retrieved data for ID {id_to_find}, but failed to display it.",
                     reply_markup=generate_main_menu()
                 )

        else:
            # Failure - Display the specific error message from call_apps_script
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"❌ Failed to retrieve sheet data:\n{error_message}",
                reply_markup=generate_main_menu()
            )
            log_interaction(user_id, "sheet_retrieval_failed", {'id_found': id_to_find, 'error': error_message})

    elif call.data == "view_my_data":
        # User clicked the "View My Data" button
        logger.info(f"User {user_id}: Requested to view their data")
        
        try:
            # Get user data summary
            user_data = get_user_data_summary(user_id)
            
            if user_data and 'profile' in user_data:
                # Format the data into a readable message
                profile = user_data['profile']
                
                # Create a formatted message with the user's data
                data_text = "📊 Your Data Summary\n\n"
                
                # User profile
                data_text += "Profile Information:\n"
                data_text += f"• Username: @{profile.get('username') or 'Not set'}\n"
                data_text += f"• Name: {profile.get('first_name', '')} {profile.get('last_name', '')}\n"
                data_text += f"• Language: {profile.get('language_code', 'Not set')}\n"
                data_text += f"• First joined: {profile.get('created_at', 'Unknown')}\n"
                data_text += f"• Last activity: {profile.get('last_activity', 'Unknown')}\n\n"
                
                # Preferences
                data_text += "Your Preferences:\n"
                data_text += f"• Bot language: {profile.get('language', 'en')}\n"
                data_text += f"• Notifications: {'Enabled' if profile.get('notifications') else 'Disabled'}\n"
                data_text += f"• Theme: {profile.get('theme', 'default')}\n\n"
                
                # Statistics
                data_text += "Your Activity:\n"
                data_text += f"• Total messages: {user_data.get('message_count', 0)}\n"
                data_text += f"• Total interactions: {user_data.get('interaction_count', 0)}\n\n"
                
                # Recent messages
                if user_data.get('recent_messages'):
                    data_text += "Your Recent Messages:\n"
                    for i, msg in enumerate(user_data['recent_messages'], 1):
                        # Truncate long messages
                        message_text = msg['message_text']
                        if message_text:  # Check if message_text is not None
                            if len(message_text) > 30:
                                message_text = message_text[:27] + "..."
                            data_text += f"{i}. {message_text}\n"
                        else:
                            data_text += f"{i}. [Media message]\n"
                
                # Create a button to return to main menu
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("Back to Main Menu", callback_data="main_menu"))
                
                # Edit the message to show the user data
                # Remove parse_mode="Markdown" which might be causing issues
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=data_text,
                    reply_markup=markup
                )
            else:
                # No data found
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="No data found for your account.",
                    reply_markup=generate_main_menu()
                )
        except Exception as e:
            logger.error(f"Error displaying user data: {str(e)}")
            logger.error(traceback.format_exc())
        
            # Send a fallback message to the user
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Sorry, there was an error retrieving your data. Please try again later.",
                reply_markup=generate_main_menu()
            )
    
    elif call.data == "delete_my_data":
        # User clicked the "Delete My Data" button
        logger.info(f"User {user_id}: Requested data deletion")
        
        # Update the user's state
        user_sessions[user_id]['state'] = 'delete_confirmation'
        
        # Show confirmation dialog
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="⚠️ Are you sure you want to delete all your data? This action cannot be undone.",
            reply_markup=generate_delete_confirmation_menu()
        )
    
    elif call.data == "confirm_delete":
        # User confirmed data deletion
        logger.info(f"User {user_id}: Confirmed data deletion")
        
        # Perform the deletion
        success, messages_deleted, interactions_deleted = delete_user_data(user_id)
        
        if success:
            # Notify the user of successful deletion
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"✅ Your data has been deleted successfully.\n\n"
                     f"• {messages_deleted} messages\n"
                     f"• {interactions_deleted} interactions\n\n"
                     f"You can start using the bot again with /start."
            )
            # --- ADD THIS ---
            # Send the main menu as a new message after successful deletion
            send_main_menu_message(chat_id, text="Data deleted. Choose an option:")
            # --- END ADD ---
        else:
            # Notify the user of failure
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="❌ There was an error deleting your data. Please try again later.",
                reply_markup=generate_main_menu()
            )
    
    elif call.data == "cancel_delete":
        # User canceled data deletion
        logger.info(f"User {user_id}: Canceled data deletion")
        
        # Update the user's state back to main menu
        user_sessions[user_id]['state'] = 'main_menu'
        
        # Return to main menu
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Operation canceled. Your data has been kept.",
            reply_markup=generate_main_menu()
        )
    
    elif call.data == "menu1":
        # User clicked the "Menu 1" button
        logger.info(f"User {user_id}: Menu 1 was selected")  # Log this action with user ID
        
        # Update the user's state
        user_sessions[user_id]['state'] = 'menu1'
        
        # Show processing message
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Analyzing your messages... This may take a moment."
        )
        
        # Get user message history
        messages = get_user_message_history(user_id, limit=20)
        
        if not messages:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="You don't have any messages to analyze yet.",
                reply_markup=generate_main_menu()
            )
            return
        
        # Format messages for Gemini
        prompt = "Analyze the following user messages and check if there are questions or instructions about what you should do. Your response must include the answer(s) to all questions and instructions. Keep your response concise and friendly and ALLWAYS in Spanish:\n\n"
        for msg in messages:
            if 'message_text' in msg and msg['message_text']:
                # Skip command messages
                if isinstance(msg['message_text'], str) and msg['message_text'].startswith('/'):
                    continue
                    
                # Check if the message text is JSON
                try:
                    if isinstance(msg['message_text'], str) and msg['message_text'].startswith('{') and msg['message_text'].endswith('}'):
                        # Try to parse as JSON to make it more readable
                        json_data = json.loads(msg['message_text'])
                        # Format JSON data as a readable string
                        formatted_json = json.dumps(json_data, indent=2, ensure_ascii=False)
                        prompt += f"- JSON Data: {formatted_json}\n"
                    else:
                        # Regular text message
                        prompt += f"- {msg['message_text']}\n"
                except (json.JSONDecodeError, AttributeError):
                    # If it's not valid JSON or not a string, just add it as is
                    prompt += f"- {msg['message_text']}\n"
        
        # Log the complete prompt outside the loop (limited to first 500 chars)
        # logger.info(f"Enviando a Gemini (first 500 chars): {prompt[:500]}...")
        logger.info(f"Enviando a Gemini (first 500 chars): {prompt}")
        
        try:
            # Use the dedicated Gemini credentials function
            credentials = get_credentials_for_gemini()
            
            if not credentials:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="Sorry, I couldn't authenticate with the AI service. Please try again later.",
                    reply_markup=generate_main_menu()
                )
                return

            # Prepare the request to Gemini
            # --- Ensure credentials.token is accessed AFTER checking credentials is not None ---
            # This was implicitly correct before, but good to be explicit
            if not credentials.token:
                 logger.error("Credentials obtained but token is missing after refresh.")
                 # Handle error appropriately - maybe refresh again or return error message
                 bot.edit_message_text(
                     chat_id=call.message.chat.id,
                     message_id=call.message.message_id,
                     text="Authentication token issue. Please try again later.",
                     reply_markup=generate_main_menu()
                 )
                 return

            headers = {
                "Authorization": f"Bearer {credentials.token}", # Now safe to access token
                "Content-Type": "application/json"
            }

            # Log token information (without revealing the full token)
            token_preview = credentials.token[:10] + "..." if credentials.token else "None"
            logger.info(f"Using token starting with: {token_preview}")
            
            # Prepare the request payload
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.4,
                    "topK": 32,
                    "topP": 0.95,
                    "maxOutputTokens": 1024,
                }
            }
            
            # Log the request (without the full prompt for privacy)
            logger.info(f"Sending request to Gemini API for user {user_id} message analysis")
            
            # Send request to Gemini API
            logger.info(f"Sending request to Gemini API endpoint: {GEMINI_API_ENDPOINT}")
            response = requests.post(
                GEMINI_API_ENDPOINT,
                headers=headers,
                json=payload
            )
            
            # Process the response
            if response.status_code == 200:
                response_json = response.json()
                analysis_result = extract_text_from_gemini_response(response_json)
                
                # Log success
                logger.info(f"Successfully received Gemini analysis for user {user_id}")
                
                # Send the analysis result
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"📊 Analysis of your messages:\n\n{analysis_result}",
                    reply_markup=generate_main_menu()
                )
            else:
                # Log the error response for debugging
                logger.error(f"Gemini API error: {response.status_code} - {response.text}")
                
                # Check for specific error types
                error_message = "Sorry, I couldn't analyze your messages at this time."
                try:
                    error_json = response.json()
                    if 'error' in error_json:
                        error_code = error_json.get('error', {}).get('code')
                        error_message = error_json.get('error', {}).get('message', '')
                        logger.error(f"Gemini API error code: {error_code}, message: {error_message}")
                        
                        if 'ACCESS_TOKEN_TYPE_UNSUPPORTED' in error_message:
                            error_message = "Authentication error with AI service. Please contact support."
                except Exception as parse_e:
                    logger.error(f"Error parsing error response: {parse_e}")
                
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="Sorry, I couldn't analyze your messages at this time. The AI service returned an error.",
                    reply_markup=generate_main_menu()
                )
        
        except Exception as e:
            logger.error(f"Error processing messages with Gemini for user {user_id}: {str(e)}")
            logger.error(traceback.format_exc())
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="An error occurred while analyzing your messages. Please try again later.",
                reply_markup=generate_main_menu()
            )
    
    elif call.data == "menu2":
        # User clicked the "Menu 2" button
        logger.info(f"User {user_id}: Menu 2 was selected")
        
        # Update the user's state
        user_sessions[user_id]['state'] = 'menu2'
        
        # Edit the original message to show the submenu for Menu 2
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="You selected Menu 2. Choose a subitem:",
            reply_markup=generate_submenu("menu2")
        )
    
    elif call.data == "main_menu":
        # User clicked the "Back to Main Menu" button
        logger.info(f"User {user_id}: Returned to main menu")
        
        # Update the user's state
        user_sessions[user_id]['state'] = 'main_menu'
        
        # Edit the message to show the main menu again
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Main Menu:",
            reply_markup=generate_main_menu()
        )
    
    # Handle submenu item clicks
    
    elif call.data == "menu1_sub1":
        # User clicked "Menu 1 Subitem 1"
        logger.info(f"User {user_id}: Processing Menu 1 - Subitem 1 (API call)")
        
        # Store the selected subitem in the user's session
        user_sessions[user_id]['data']['selected_item'] = 'menu1_sub1'
        sub_item = call.data
        logger.info(f"User {user_id}: Processing {sub_item}")
        user_sessions[user_id]['data']['selected_item'] = sub_item

        # Use answer_callback_query for quick feedback
        bot.answer_callback_query(call.id, f"Processing {sub_item}...")

        # --- ADD THIS ---
        # Send the main menu as a new message after processing a sub-item action
        # You might want to send a result message *first* if the sub-item action has a visible result
        # For now, just sending the menu:
        send_main_menu_message(chat_id, text=f"{sub_item} processed. Choose next option:")
        # --- END ADD ---

# Flask route that receives updates from Telegram
# The URL includes the bot token to ensure only Telegram can send updates
@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    try:
        # Read the JSON data sent by Telegram
        json_string = request.stream.read().decode('utf-8')
        logger.info(f"Received update: {json_string}")
        
        # Convert the JSON string to a Telegram Update object
        update = telebot.types.Update.de_json(json_string)
        
        # Process the update with our bot
        bot.process_new_updates([update])
        
        # Return an empty response with status code 200 (OK)
        return '', 200
    except Exception as e:
        # If anything goes wrong, log the error
        logger.error(f"Error processing update: {str(e)}")
        
        # Return the error message with status code 500 (Internal Server Error)
        return jsonify({'error': str(e)}), 500

# Simple route to check if the bot is running
@app.route('/')
def index():
    return 'Bot is running!'  # Just returns a simple text message

# Route to set up the webhook with Telegram
@app.route('/set_webhook')
def set_webhook():
    # First remove any existing webhook
    bot.remove_webhook()
    
    # Set a new webhook
    # Don't upload the certificate to Telegram, just use the URL
    # This assumes your SSL certificate is properly set up with a trusted CA
    bot.set_webhook(url=WEBHOOK_URL)
    
    # Return a confirmation message
    return 'Webhook set!'

# Route to get information about the current webhook status
@app.route('/webhook_info')
def webhook_info():
    # Get webhook information from Telegram
    info = bot.get_webhook_info()
    
    # Return the information as JSON
    return jsonify({
        'url': info.url,  # The URL Telegram is sending updates to
        'has_custom_certificate': info.has_custom_certificate,  # Whether we're using a custom certificate
        'pending_update_count': info.pending_update_count,  # Number of updates waiting to be processed
        'last_error_date': info.last_error_date,  # When the last error occurred
        'last_error_message': info.last_error_message,  # What the last error was
        'max_connections': info.max_connections,  # Maximum allowed webhook connections
        'ip_address': info.ip_address  # IP address Telegram is connecting from
    })

# Route to manually check for updates using getUpdates method
# This is useful for debugging when webhooks aren't working
@app.route('/check_updates')
def check_updates():
    # Temporarily remove the webhook
    bot.remove_webhook()
    
    # Get updates directly using long polling
    updates = bot.get_updates()
    
    # Re-set the webhook before returning
    bot.set_webhook(url=WEBHOOK_URL)
    
    # Convert the updates to dictionaries and return as JSON
    return jsonify([u.to_dict() for u in updates])

# Route to view current user sessions (for debugging)
@app.route('/user_sessions')
def view_user_sessions():
    # Return a sanitized version of user sessions (remove sensitive data if any)
    return jsonify({
        'active_users': len(user_sessions),
        'sessions': {str(user_id): session['state'] for user_id, session in user_sessions.items()}
    })

# Route to view database users
@app.route('/db_users')
def view_db_users():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # This enables column access by name
        cursor = conn.cursor()
        
        # Get all users with their preferences
        cursor.execute("""
        SELECT u.user_id, u.username, u.first_name, u.last_name, 
               u.chat_id, u.created_at, u.last_activity,
               p.language, p.notifications, p.theme,
               (SELECT COUNT(*) FROM user_interactions WHERE user_id = u.user_id) as interaction_count
        FROM users u
        LEFT JOIN user_preferences p ON u.user_id = p.user_id
        ORDER BY u.last_activity DESC
        """)
        
        users = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return jsonify({
            'total_users': len(users),
            'users': users
        })
    except Exception as e:
        logger.error(f"Error retrieving users: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route to view image processing results
@app.route('/image_processing_results/<int:user_id>')
def view_image_processing_results(user_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get user details
        cursor.execute("""
        SELECT u.*, p.language, p.notifications, p.theme
        FROM users u
        LEFT JOIN user_preferences p ON u.user_id = p.user_id
        WHERE u.user_id = ?
        """, (user_id,))
        user = dict(cursor.fetchone() or {})
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get image processing results
        cursor.execute("""
        SELECT id, message_id, file_id, processed_at
        FROM image_processing_results 
        WHERE user_id = ? 
        ORDER BY processed_at DESC
        LIMIT 50
        """, (user_id,))
        
        results = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return jsonify({
            'user': user,
            'image_processing_results': results,
            'total_results': len(results)
        })
    except Exception as e:
        logger.error(f"Error retrieving image processing results: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route to view user messages
@app.route('/user_messages/<int:user_id>')
def view_user_messages(user_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get user details
        cursor.execute("""
        SELECT u.*, p.language, p.notifications, p.theme
        FROM users u
        LEFT JOIN user_preferences p ON u.user_id = p.user_id
        WHERE u.user_id = ?
        """, (user_id,))
        user = dict(cursor.fetchone() or {})
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user messages
        cursor.execute("""
        SELECT * FROM user_messages 
        WHERE user_id = ? 
        ORDER BY timestamp DESC
        LIMIT 100
        """, (user_id,))
        
        messages = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return jsonify({
            'user': user,
            'messages': messages,
            'total_messages': len(messages)
        })
    except Exception as e:
        logger.error(f"Error retrieving user messages: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route to view user interactions
@app.route('/user_interactions/<int:user_id>')
def view_user_interactions(user_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get user details with preferences
        cursor.execute("""
        SELECT u.*, p.language, p.notifications, p.theme
        FROM users u
        LEFT JOIN user_preferences p ON u.user_id = p.user_id
        WHERE u.user_id = ?
        """, (user_id,))
        user = dict(cursor.fetchone() or {})
        
        # Get user interactions
        cursor.execute("""
        SELECT * FROM user_interactions 
        WHERE user_id = ? 
        ORDER BY timestamp DESC
        LIMIT 100
        """, (user_id,))
        
        interactions = [dict(row) for row in cursor.fetchall()]
        
        # Get interaction statistics
        cursor.execute("""
        SELECT action_type, COUNT(*) as count
        FROM user_interactions
        WHERE user_id = ?
        GROUP BY action_type
        ORDER BY count DESC
        """, (user_id,))
        
        stats = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
            
        return jsonify({
            'user': user,
            'preferences': {
                'language': user.get('language', 'en'),
                'notifications': bool(user.get('notifications', True)),
                'theme': user.get('theme', 'default')
            },
            'interactions': interactions,
            'total_interactions': len(interactions),
            'interaction_stats': stats
        })
    except Exception as e:
        logger.error(f"Error retrieving user interactions: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route to update user preferences
@app.route('/update_preference/<int:user_id>', methods=['POST'])
def update_preference(user_id):
    try:
        data = request.json
        if not data or 'preference_name' not in data or 'preference_value' not in data:
            return jsonify({'error': 'Missing required fields'}), 400
        
        preference_name = data['preference_name']
        preference_value = data['preference_value']
        
        # Validate preference name
        valid_preferences = ['language', 'notifications', 'theme']
        if preference_name not in valid_preferences:
            return jsonify({'error': f'Invalid preference name. Must be one of: {valid_preferences}'}), 400
        
        # Update the preference
        success = update_user_preference(user_id, preference_name, preference_value)
        
        if success:
            # Update session if user is active
            if user_id in user_sessions:
                if 'preferences' not in user_sessions[user_id]:
                    user_sessions[user_id]['preferences'] = get_user_preferences(user_id)
                else:
                    user_sessions[user_id]['preferences'][preference_name] = preference_value
            
            return jsonify({
                'success': True,
                'message': f'Preference {preference_name} updated successfully',
                'user_id': user_id,
                'preference_name': preference_name,
                'preference_value': preference_value
            })
        else:
            return jsonify({'error': 'Failed to update preference'}), 500
            
    except Exception as e:
        logger.error(f"Error updating preference: {str(e)}")
        return jsonify({'error': str(e)}), 500


# --- Message Editing Web App Routes ---

@app.route('/webapp/edit_messages')
def webapp_edit_messages():
    """Serve the HTML page for the message editing web app."""
    logger.info("Serving edit_messages.html for Web App request")
    # Validation happens on data fetch/save, not here
    # Assuming validate_init_data exists and is imported/defined elsewhere
    # Assuming render_template is imported from flask
    return render_template('edit_messages.html')

@app.route('/webapp/get_messages', methods=['POST'])
def webapp_get_messages():
    """Provide user messages (with non-null text) to the web app after validating initData."""
    logger.info("Received request for /webapp/get_messages")
    try:
        init_data_str = request.headers.get('X-Telegram-Init-Data')
        if not init_data_str:
            logger.warning("Missing X-Telegram-Init-Data header for get_messages")
            return jsonify({'error': 'Authentication required'}), 401

        # !!! IMPORTANT: Ensure validate_init_data function is defined and imported correctly !!!
        # user_id, _ = validate_init_data(init_data_str, TOKEN)
        # Placeholder check - replace with actual validation
        try:
            from urllib.parse import parse_qs
            import hmac
            import hashlib
            data_check_string = "\n".join(sorted([f"{k}={v[0]}" for k, v in parse_qs(init_data_str).items() if k != 'hash']))
            secret_key = hmac.new("WebAppData".encode(), TOKEN.encode(), hashlib.sha256).digest()
            calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
            init_data_dict = parse_qs(init_data_str)
            if init_data_dict.get('hash', [''])[0] != calculated_hash:
                 raise ValueError("Invalid hash")
            user_data = json.loads(init_data_dict['user'][0])
            user_id = user_data.get('id')
            if not user_id:
                 raise ValueError("User ID not found in initData")
        except Exception as validation_e:
             logger.error(f"initData validation failed: {validation_e}", exc_info=True)
             user_id = None # Ensure user_id is None if validation fails

        if not user_id:
            logger.warning("Invalid initData received for get_messages request")
            return jsonify({'error': 'Invalid authentication data'}), 403

        logger.info(f"Fetching messages for validated user_id: {user_id}")
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Fetch recent messages with non-null/non-empty message_text
        limit = 20 # Adjust limit as needed
        cursor.execute("""
            SELECT id, message_id, message_text, timestamp
            FROM user_messages
            WHERE user_id = ? AND message_text IS NOT NULL AND message_text != '' AND message_text != '/start' -- Exclude /start messages
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, limit))
        messages = [dict(row) for row in cursor.fetchall()]

        conn.close()

        logger.info(f"Successfully fetched {len(messages)} messages for user_id: {user_id}")
        return jsonify(messages)

    except Exception as e:
        logger.error(f"Error fetching messages for web app: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/webapp/save_messages', methods=['POST'])
def webapp_save_messages():
    """Receive updated message data from the web app, validate, and save."""
    logger.info("Received request for /webapp/save_messages")
    try:
        init_data_str = request.headers.get('X-Telegram-Init-Data')
        if not init_data_str:
             logger.warning("Missing X-Telegram-Init-Data header for save_messages request")
             return jsonify({'error': 'Authentication required'}), 401

        # !!! IMPORTANT: Ensure validate_init_data function is defined and imported correctly !!!
        # user_id, _ = validate_init_data(init_data_str, TOKEN)
        # Placeholder check - replace with actual validation
        try:
            from urllib.parse import parse_qs
            import hmac
            import hashlib
            data_check_string = "\n".join(sorted([f"{k}={v[0]}" for k, v in parse_qs(init_data_str).items() if k != 'hash']))
            secret_key = hmac.new("WebAppData".encode(), TOKEN.encode(), hashlib.sha256).digest()
            calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
            init_data_dict = parse_qs(init_data_str)
            if init_data_dict.get('hash', [''])[0] != calculated_hash:
                 raise ValueError("Invalid hash")
            user_data = json.loads(init_data_dict['user'][0])
            user_id = user_data.get('id')
            if not user_id:
                 raise ValueError("User ID not found in initData")
        except Exception as validation_e:
             logger.error(f"initData validation failed: {validation_e}", exc_info=True)
             user_id = None # Ensure user_id is None if validation fails

        if not user_id:
             logger.warning("Invalid initData received for save_messages request")
             return jsonify({'error': 'Invalid authentication data'}), 403

        logger.info(f"Processing save_messages request for validated user_id: {user_id}")
        data = request.json # Expecting a list of objects: [{'id': db_id, 'text': new_text}, ...]
        if not data or not isinstance(data, list):
            logger.warning(f"Invalid or missing JSON data received in save_messages request for user_id: {user_id}")
            return jsonify({'error': 'Invalid data format received'}), 400

        # --- Update Database ---
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        success_count = 0
        fail_count = 0
        errors = []

        try:
            cursor.execute("BEGIN TRANSACTION")

            for item in data:
                db_id = item.get('id')
                new_text = item.get('text') # Allow empty string, but not null

                # Basic validation
                if db_id is None or not isinstance(db_id, int) or new_text is None:
                    logger.warning(s.LOG_WEBAPP_SKIPPING_INVALID_ITEM.format(user_id=user_id, item=item))
                    fail_count += 1
                    errors.append(s.ERROR_WEBAPP_INVALID_ITEM_FORMAT.format(item=item))
                    continue

                # Update the specific message, ensuring it belongs to the user
                cursor.execute("""
                    UPDATE user_messages
                    SET message_text = ?
                    WHERE id = ? AND user_id = ?
                """, (new_text, db_id, user_id))

                if cursor.rowcount > 0:
                    success_count += 1
                else:
                    # Log if a message wasn't updated (might belong to another user or ID is wrong)
                    logger.warning(s.WARN_WEBAPP_UPDATE_FAILED.format(db_id=db_id, user_id=user_id))
                    fail_count += 1
                    errors.append(s.ERROR_WEBAPP_MESSAGE_NOT_FOUND.format(db_id=db_id))


            conn.commit()
            logger.info(s.LOG_WEBAPP_FINISHED_SAVING.format(user_id=user_id, success_count=success_count, fail_count=fail_count))

        except Exception as db_e:
            conn.rollback()
            success_count = 0 # Reset counts on rollback
            fail_count = len(data) # Assume all failed on transaction error
            errors.append(s.WEBAPP_SAVE_ERROR_TRANSACTION.format(error=db_e))
            logger.error(s.ERROR_WEBAPP_DB_TRANSACTION.format(user_id=user_id, error=db_e), exc_info=True)
        finally:
            conn.close()

        if fail_count == 0:
            return jsonify({'status': s.WEBAPP_SAVE_STATUS_SUCCESS, 'updated': success_count})
        else:
            status_code = 500 if "Transaction failed" in errors else 400
            return jsonify({'status': s.WEBAPP_SAVE_STATUS_PARTIAL if success_count > 0 else s.WEBAPP_SAVE_STATUS_ERROR,
                            'message': s.WEBAPP_SAVE_MESSAGE_PARTIAL.format(fail_count=fail_count),
                            'updated': success_count,
                            'failed': fail_count,
                            'errors': errors}), status_code

    except Exception as e:
        logger.error(f"Error processing save_messages request: {e}", exc_info=True)
        return jsonify({'error': s.ERROR_WEBAPP_INTERNAL_SERVER}), 500

# --- End Message Editing Web App Routes ---


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
from bot_modules import strings as s # Import strings

# --- Initial Logging Setup ---
# Configure logging (this should be done early)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
