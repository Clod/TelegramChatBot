import logging
import os
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
    update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
    bot.process_new_updates([update])
    return '', 200

@app.route('/')
def index():
    return 'Bot is running!'

@app.route('/set_webhook')
def set_webhook():
    bot.remove_webhook()
    bot.set_webhook(
        url=WEBHOOK_URL,
        certificate=open(WEBHOOK_SSL_CERT, 'r')
    )
    return 'Webhook set!'

if __name__ == '__main__':
    # Remove any existing webhook first
    bot.remove_webhook()
    
    # Set the webhook
    bot.set_webhook(
        url=WEBHOOK_URL,
        certificate=open(WEBHOOK_SSL_CERT, 'r')
    )
    
    # Start the Flask app
    app.run(
        host='0.0.0.0',
        port=443,
        ssl_context=(WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV),
        debug=False
    )
