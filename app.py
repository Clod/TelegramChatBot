import logging
import os
from datetime import datetime
from flask import Flask, request, jsonify
import telebot
from dotenv import load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Telegram Bot Token
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")
WEBHOOK_URL = f"https://precarina.com.ar/{TOKEN}"

# SSL Certificate paths
WEBHOOK_SSL_CERT = "/etc/letsencrypt/live/precarina.com.ar/fullchain.pem"
WEBHOOK_SSL_PRIV = "/etc/letsencrypt/live/precarina.com.ar/privkey.pem"

# Initialize Flask app and Telebot
app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

def generate_main_menu():
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("Menu 1", callback_data="menu1"),
        InlineKeyboardButton("Menu 2", callback_data="menu2")
    )
    return markup

def generate_submenu(menu_id):
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton(f"{menu_id} Subitem 1", callback_data=f"{menu_id}_sub1"),
        InlineKeyboardButton(f"{menu_id} Subitem 2", callback_data=f"{menu_id}_sub2"),
        InlineKeyboardButton("Back to Main Menu", callback_data="main_menu")
    )
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Welcome to the bot! Choose an option:", reply_markup=generate_main_menu())

@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    if call.data == "menu1":
        logger.info("Menu 1 was selected")
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="You selected Menu 1. Choose a subitem:",
            reply_markup=generate_submenu("menu1")
        )
    
    elif call.data == "menu2":
        logger.info("Menu 2 was selected")
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="You selected Menu 2. Choose a subitem:",
            reply_markup=generate_submenu("menu2")
        )
    
    elif call.data == "main_menu":
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Main Menu:",
            reply_markup=generate_main_menu()
        )
    
    elif call.data == "menu1_sub1":
        logger.info("Processing Menu 1 - Subitem 1 (API call)")
        bot.answer_callback_query(call.id, "Processing Menu 1 - Subitem 1...")
        # Placeholder for API call
        
    elif call.data == "menu1_sub2":
        logger.info("Processing Menu 1 - Subitem 2 (API call)")
        bot.answer_callback_query(call.id, "Processing Menu 1 - Subitem 2...")
        # Placeholder for API call
        
    elif call.data == "menu2_sub1":
        logger.info("Processing Menu 2 - Subitem 1 (API call)")
        bot.answer_callback_query(call.id, "Processing Menu 2 - Subitem 1...")
        # Placeholder for API call
        
    elif call.data == "menu2_sub2":
        logger.info("Processing Menu 2 - Subitem 2 (API call)")
        bot.answer_callback_query(call.id, "Processing Menu 2 - Subitem 2...")
        # Placeholder for API call

@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    try:
        json_string = request.stream.read().decode('utf-8')
        logger.info(f"Received update: {json_string}")
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    except Exception as e:
        logger.error(f"Error processing update: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    return 'Bot is running!'

@app.route('/set_webhook')
def set_webhook():
    bot.remove_webhook()
    # Don't upload the certificate to Telegram, just use the URL
    # This assumes your SSL certificate is properly set up with a trusted CA
    bot.set_webhook(url=WEBHOOK_URL)
    return 'Webhook set!'

@app.route('/webhook_info')
def webhook_info():
    info = bot.get_webhook_info()
    return jsonify({
        'url': info.url,
        'has_custom_certificate': info.has_custom_certificate,
        'pending_update_count': info.pending_update_count,
        'last_error_date': info.last_error_date,
        'last_error_message': info.last_error_message,
        'max_connections': info.max_connections,
        'ip_address': info.ip_address
    })

@app.route('/check_updates')
def check_updates():
    bot.remove_webhook()
    updates = bot.get_updates()
    # Re-set the webhook before returning
    bot.set_webhook(url=WEBHOOK_URL)
    return jsonify([u.to_dict() for u in updates])

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'bot_info': bot.get_me().to_dict()
    })

if __name__ == '__main__':
    # Remove any existing webhook first
    bot.remove_webhook()
    
    # Set the webhook without uploading the certificate
    bot.set_webhook(url=WEBHOOK_URL)
    
    # Start the Flask app
    app.run(
        host='0.0.0.0',
        port=443,
        ssl_context=(WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV),
        debug=False
    )
