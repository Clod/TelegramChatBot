# Import necessary libraries
import logging  # For logging messages and errors
import os  # For accessing environment variables and file paths
from datetime import datetime  # For timestamps in health checks
from flask import Flask, request, jsonify  # Web framework for creating API endpoints
import telebot  # Python Telegram Bot API wrapper
from dotenv import load_dotenv  # For loading environment variables from .env file
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton  # For creating interactive buttons

# Configure logging to track what's happening in our application
# This helps with debugging and monitoring
logging.basicConfig(
    level=logging.INFO,  # Log level - INFO means we'll see general operational messages
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'  # Format of log messages
)
logger = logging.getLogger(__name__)  # Create a logger specific to this module

# Load environment variables from .env file
# This is a security best practice to avoid hardcoding sensitive information
load_dotenv()

# Get the Telegram Bot Token from environment variables
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    # If the token isn't set, raise an error - the bot can't work without it
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")
# Create the webhook URL that Telegram will use to send updates to our bot
WEBHOOK_URL = f"https://precarina.com.ar/{TOKEN}"

# Paths to SSL certificate files
# These are needed for secure HTTPS communication
WEBHOOK_SSL_CERT = "/etc/letsencrypt/live/precarina.com.ar/fullchain.pem"  # Public certificate
WEBHOOK_SSL_PRIV = "/etc/letsencrypt/live/precarina.com.ar/privkey.pem"     # Private key

# Initialize our web application and Telegram bot
app = Flask(__name__)  # Create a Flask web application
bot = telebot.TeleBot(TOKEN)  # Create a Telegram bot instance with our token

# Dictionary to store user sessions
user_sessions = {}  # Key: user_id, Value: dict with user state and data

# Function to create the main menu with interactive buttons
def generate_main_menu():
    # Create a new inline keyboard markup (buttons that appear in the message)
    markup = InlineKeyboardMarkup()
    markup.row_width = 2  # Set how many buttons to show in each row
    
    # Add two buttons to the markup
    markup.add(
        InlineKeyboardButton("Menu 1", callback_data="menu1"),  # First button
        InlineKeyboardButton("Menu 2", callback_data="menu2")   # Second button
        # callback_data is what the bot receives when a user clicks the button
    )
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

# Handler for /start and /help commands
# This decorator tells the bot to call this function when users send these commands
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    # Get the user ID to track this specific user's session
    user_id = message.from_user.id
    
    # Initialize or reset the user's session
    user_sessions[user_id] = {
        'state': 'main_menu',
        'data': {}
    }
    
    # Reply to the user with a welcome message and show the main menu
    bot.reply_to(
        message,  # The original message from the user
        "Welcome to the bot! Choose an option:",  # Text to send
        reply_markup=generate_main_menu()  # Attach the main menu buttons
    )

# Handler for button clicks (callback queries)
# This decorator tells the bot to call this function when users click any button
@bot.callback_query_handler(func=lambda call: True)  # The lambda function means "handle all callbacks"
def handle_callback_query(call):
    # Get the user ID to ensure we're handling the correct user's session
    user_id = call.from_user.id
    
    # Ensure the user has a session, create one if not
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            'state': 'main_menu',
            'data': {}
        }
    
    # Check which button was clicked by examining the callback_data
    
    if call.data == "menu1":
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
        
        # Show a notification to the user that we're processing their request
        bot.answer_callback_query(call.id, "Processing Menu 1 - Subitem 1...")
        # Placeholder for API call - this is where you would add actual functionality
        
    elif call.data == "menu1_sub2":
        # User clicked "Menu 1 Subitem 2"
        logger.info(f"User {user_id}: Processing Menu 1 - Subitem 2 (API call)")
        
        # Store the selected subitem in the user's session
        user_sessions[user_id]['data']['selected_item'] = 'menu1_sub2'
        
        bot.answer_callback_query(call.id, "Processing Menu 1 - Subitem 2...")
        # Placeholder for API call
        
    elif call.data == "menu2_sub1":
        # User clicked "Menu 2 Subitem 1"
        logger.info(f"User {user_id}: Processing Menu 2 - Subitem 1 (API call)")
        
        # Store the selected subitem in the user's session
        user_sessions[user_id]['data']['selected_item'] = 'menu2_sub1'
        
        bot.answer_callback_query(call.id, "Processing Menu 2 - Subitem 1...")
        # Placeholder for API call
        
    elif call.data == "menu2_sub2":
        # User clicked "Menu 2 Subitem 2"
        logger.info(f"User {user_id}: Processing Menu 2 - Subitem 2 (API call)")
        
        # Store the selected subitem in the user's session
        user_sessions[user_id]['data']['selected_item'] = 'menu2_sub2'
        
        bot.answer_callback_query(call.id, "Processing Menu 2 - Subitem 2...")
        # Placeholder for API call

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

# Health check endpoint to verify the bot is working correctly
@app.route('/health')
def health_check():
    return jsonify({
        'status': 'ok',  # Simple status indicator
        'timestamp': datetime.now().isoformat(),  # Current time
        'bot_info': bot.get_me().to_dict()  # Information about the bot from Telegram
    })

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
