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

                                                                                                                          
import getpass                                                                                                                       
print(f"Effective UID: {os.geteuid()}")                                                                                              
print(f"Effective User: {getpass.getuser()}")                                                                                        

# Load environment variables from .env file
# This is a security best practice to avoid hardcoding sensitive information
load_dotenv()


# Configure logging to track what's happening in our application
# This helps with debugging and monitoring
logging.basicConfig(
    level=logging.INFO,  # Log level - INFO means we'll see general operational messages
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'  # Format of log messages
)
logger = logging.getLogger(__name__)  # Create a logger specific to this module

# Get DEBUG_MODE from environmet variables
DEBUG_MODE_STR = os.environ.get("DEBUG_MODE", "False").lower()
DEBUG_MODE = DEBUG_MODE_STR == "true"

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

# Function to get authenticated credentials
def get_credentials():
    """Get authenticated credentials from service account file"""
    try:
        if not SERVICE_ACCOUNT_FILE or not os.path.exists(SERVICE_ACCOUNT_FILE):
            logger.error("Service account file not found")
            return None
            
        # Create credentials from the service account file
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        
        # Refresh the credentials if needed
        if credentials.expired:
            credentials.refresh(GoogleAuthRequest())
            
        return credentials
    except Exception as e:
        logger.error(f"Error getting credentials: {str(e)}")
        logger.error(traceback.format_exc())
        return None

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

# Function to create the main menu with interactive buttons
def generate_main_menu():
    # Create a new inline keyboard markup (buttons that appear in the message)
    markup = InlineKeyboardMarkup()
    markup.row_width = 2  # Set how many buttons to show in each row
    
    # Add buttons to the markup
    markup.add(
        InlineKeyboardButton("Menu 1", callback_data="menu1"),  # First button
        InlineKeyboardButton("Menu 2", callback_data="menu2")   # Second button
        # callback_data is what the bot receives when a user clicks the button
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
    if not DEBUG_MODE and BASE_URL and BASE_URL.startswith("https://"):
        web_app_buttons = []
        # Check if the URLs seem valid (basic check) - Assuming profile URL might exist
        # if WEBAPP_EDIT_PROFILE_URL and WEBAPP_EDIT_PROFILE_URL.startswith("https://"):
        #     web_app_buttons.append(
        #         InlineKeyboardButton("✏️ Edit My Profile", web_app=WebAppInfo(WEBAPP_EDIT_PROFILE_URL))
        #     )
        if WEBAPP_EDIT_MESSAGES_URL and WEBAPP_EDIT_MESSAGES_URL.startswith("https://"):
            web_app_buttons.append(
                 InlineKeyboardButton("📝 Edit My Messages", web_app=WebAppInfo(WEBAPP_EDIT_MESSAGES_URL))
            )

        if web_app_buttons:
             # Add buttons in a new row or append to existing logic as needed
             markup.add(*web_app_buttons) # Adds buttons in a row
        else:
             logger.warning("Web App URLs not configured or invalid (must be HTTPS), skipping Web App buttons in menu.")
    elif not BASE_URL or not BASE_URL.startswith("https://"):
        logger.warning("BASE_URL is not set or does not use HTTPS. Web App buttons will not be shown.")


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

# Handler for /start and /help commands
# This decorator tells the bot to call this function when users send these commands
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    # Get the user ID to track this specific user's session
    user_id = message.from_user.id
    chat_id = message.chat.id
    
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
    
    # Reply to the user with a welcome message and show the main menu
    welcome_text = "Welcome to the bot! Choose an option:"
    if prefs['language'] == 'es':
        welcome_text = "¡Bienvenido al bot! Elige una opción:"
    
    bot.reply_to(
        message,  # The original message from the user
        welcome_text,  # Text to send
        reply_markup=generate_main_menu()  # Attach the main menu buttons
    )

# Function to get user's message history
def get_user_message_history(user_id, limit=10):
    """Get the message history for a specific user"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get user messages ordered by timestamp (newest first)
    cursor.execute("""
    SELECT message_text, timestamp 
    FROM user_messages 
    WHERE user_id = ? AND message_type = 'text'
    ORDER BY timestamp DESC
    LIMIT ?
    """, (user_id, limit))
    
    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
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
        # Get authenticated credentials
        credentials = get_credentials()
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
                    "parts": [{"text": "Analyze the image and extract the following personal information: full name, date of birth, age, email, phone number, city, state, gender, and preferred contact method.  Return the extracted information as a **single string** with **key-value pairs separated by pipe symbols (|)**.  The format should be: `key=value|key=value|key=value|...`. Use the following keys: `full_name`, `date_of_birth`, `age`, `email`, `phone_number`, `city`, `state`, `gender`, and `preferred_contact_method`. For example: `full_name=LUIGI CADORNA|date_of_birth=8/2/1962|age=63|email=luigi.cadorna@ymail.com|phone_number=1234567890|city=Buenos Aires|state=JALISCO|gender=Male|preferred_contact_method=Mail` If any piece of information cannot be confidently extracted from the image, leave the corresponding value **empty** (for strings) or `null` (for numbers like age), but still include the key in the output string. For example, if the email is not found, it should be `email=|...` and if the age is not found, it should be `age=null|...`. Ensure the response is **only the single string** with pipe-separated key-value pairs, without any markdown formatting, code blocks, or extraneous text."},
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
        traceback.print_exc()  # Print the full traceback for debugging
        return "Error processing response"

def cleanup_temp_file(file_path):
    """
    Delete a temporary file
    """
    logger.info(f"Initiating cleanup of temporary file: {file_path}")
    
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Successfully deleted temporary file: {file_path}")
            return True
        return False
    
    except Exception as e:
        logger.error(f"Error cleaning up temporary file: {str(e)}")
        return False

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

    # --- ADD THIS ---
    # Always send the main menu after handling any text message
    send_main_menu_message(chat_id)
    # --- END ADD ---

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
    
    if call.data == "view_my_data":
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
        
        # Edit the original message to show the submenu for Menu 1
        bot.edit_message_text(
            chat_id=call.message.chat.id,  # Which chat to update
            message_id=call.message.message_id,  # Which message to edit
            text="You selected Menu 1. Choose a subitem:",  # New text
            reply_markup=generate_submenu("menu1")  # New buttons (submenu)
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
            WHERE user_id = ? AND message_text IS NOT NULL AND message_text != ''
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
                    logger.warning(f"Skipping invalid item format in save_messages for user {user_id}: {item}")
                    fail_count += 1
                    errors.append(f"Invalid item format: {item}")
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
                    logger.warning(f"Failed to update message with db_id {db_id} for user {user_id}. Rowcount: {cursor.rowcount}. Might not exist or belong to user.")
                    fail_count += 1
                    errors.append(f"Message ID {db_id} not found or doesn't belong to user.")


            conn.commit()
            logger.info(f"Finished saving messages for user_id: {user_id}. Success: {success_count}, Failed: {fail_count}")

        except Exception as db_e:
            conn.rollback()
            success_count = 0 # Reset counts on rollback
            fail_count = len(data) # Assume all failed on transaction error
            errors.append(f"Transaction failed: {db_e}")
            logger.error(f"Database transaction error saving messages for user_id {user_id}: {db_e}", exc_info=True)
        finally:
            conn.close()

        if fail_count == 0:
            return jsonify({'status': 'success', 'updated': success_count})
        else:
            status_code = 500 if "Transaction failed" in errors else 400
            return jsonify({'status': 'partial_error' if success_count > 0 else 'error',
                            'message': f'Failed to save {fail_count} message(s).',
                            'updated': success_count,
                            'failed': fail_count,
                            'errors': errors}), status_code

    except Exception as e:
        logger.error(f"Error processing save_messages request: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

# --- End Message Editing Web App Routes ---


# Health check endpoint to verify the bot is working correctly
@app.route('/health')
def health_check():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get counts
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM user_messages")
        message_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM user_interactions")
        interaction_count = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'status': 'ok',  # Simple status indicator
            'timestamp': datetime.now().isoformat(),  # Current time
            'bot_info': bot.get_me().to_dict(),  # Information about the bot from Telegram
            'db_status': 'ok' if os.path.exists(DB_PATH) else 'missing',
            'service_account_status': 'ok' if (SERVICE_ACCOUNT_FILE and os.path.exists(SERVICE_ACCOUNT_FILE)) else 'missing',
            'active_users': len(user_sessions),
            'total_users': user_count,
            'total_messages': message_count,
            'total_interactions': interaction_count
        })
    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# This code only runs if the script is executed directly (not imported)
if __name__ == '__main__':
    # Remove any existing webhook first
    bot.remove_webhook()
    
    # Set the webhook without uploading the certificate
    bot.set_webhook(url=WEBHOOK_URL)
    
    # Start the Flask web server
    app.run(
        host='0.0.0.0',  # Listen on all available network interfaces
        port=443,  # Use the standard HTTPS port
        ssl_context=(WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV),  # Use SSL for secure HTTPS
        debug=False  # Don't run in debug mode in production
    )
