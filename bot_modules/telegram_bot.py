import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import logging
import os
import tempfile
import uuid
import json
from datetime import datetime
import traceback

# Import from other modules using relative paths
from . import config
from . import database as db
from . import google_apis
from . import utils

logger = logging.getLogger(__name__)

# Initialize bot
bot = telebot.TeleBot(config.TOKEN)

# User sessions (kept in memory for simplicity, consider persistent storage for production)
user_sessions = {}

# --- Menu Generation ---
def generate_main_menu():
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("📊 Analyze My Messages", callback_data="menu1"),
        InlineKeyboardButton("📄 Retrieve Form Data", callback_data="retrieve_form"),
        InlineKeyboardButton("📈 Retrieve Sheet Data", callback_data="retrieve_sheet_data"), # <-- ADD THIS LINE
        InlineKeyboardButton("Menu 2", callback_data="menu2")
    )
    markup.add(InlineKeyboardButton("📊 View My Data", callback_data="view_my_data"))
    markup.add(InlineKeyboardButton("🗑️ Delete My Data", callback_data="delete_my_data"))

    logger.debug(f"generate_main_menu: DEBUG_MODE={config.DEBUG_MODE}, BASE_URL='{config.BASE_URL}'")
    if not config.DEBUG_MODE and config.BASE_URL and config.BASE_URL.startswith("https://"):
        logger.info("generate_main_menu: Conditions met for adding Web App buttons.")
        web_app_buttons = []
        logger.debug(f"Checking Messages URL: {config.WEBAPP_EDIT_MESSAGES_URL}")
        if config.WEBAPP_EDIT_MESSAGES_URL and config.WEBAPP_EDIT_MESSAGES_URL.startswith("https://"):
            logger.info("generate_main_menu: Adding 'Edit My Messages' button.")
            web_app_buttons.append(
                 InlineKeyboardButton("📝 Edit My Messages", web_app=WebAppInfo(config.WEBAPP_EDIT_MESSAGES_URL))
            )
        if web_app_buttons:
             logger.info(f"generate_main_menu: Calling markup.add() with {len(web_app_buttons)} web app button(s).")
             markup.add(*web_app_buttons)
        else:
             logger.warning("generate_main_menu: No valid Web App buttons created, skipping markup.add().")
    elif not config.BASE_URL or not config.BASE_URL.startswith("https://"):
        logger.warning("generate_main_menu: BASE_URL is not set or does not use HTTPS. Web App buttons will not be shown.")
    else:
         logger.info("generate_main_menu: DEBUG_MODE is True, skipping Web App buttons.")
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

def generate_delete_confirmation_menu():
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("✅ Yes, Delete My Data", callback_data="confirm_delete"),
        InlineKeyboardButton("❌ No, Keep My Data", callback_data="cancel_delete")
    )
    return markup

def send_main_menu_message(chat_id, text="Choose an option from the menu:"):
    """Sends a new message with the main menu."""
    try:
        bot.send_message(chat_id, text, reply_markup=generate_main_menu())
        logger.info(f"Sent main menu as a new message to chat {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send main menu message to chat {chat_id}: {e}")

# --- Telegram Utilities ---
def download_image_from_telegram(file_id, user_id, message_id):
    """Download an image from Telegram servers using file_id"""
    logger.info(f"Starting image download process for file_id: {file_id}, user_id: {user_id}, message_id: {message_id}")
    try:
        file_info = bot.get_file(file_id)
        file_path = file_info.file_path
        temp_dir = tempfile.gettempdir()
        unique_filename = f"{uuid.uuid4().hex}.jpg"
        local_file_path = os.path.join(temp_dir, unique_filename)
        downloaded_file = bot.download_file(file_path)
        with open(local_file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        file_size = os.path.getsize(local_file_path)
        logger.info(f"Successfully downloaded image to {local_file_path} (Size: {file_size} bytes)")
        return local_file_path
    except Exception as e:
        logger.error(f"Error downloading image: {str(e)}", exc_info=True)
        return None

# --- Message Handlers ---
@bot.message_handler(commands=['generate_file'])
def handle_generate_file(message): # Renamed function
    chat_id = message.chat.id
    file_name = "example.txt"
    try:
        with open(file_name, "w") as file:
            file.write("Hello! This is your generated file.\n")
            file.write("This is an example of a Telegram bot sending files.")
        with open(file_name, "rb") as file:
            bot.send_document(chat_id, file)
        logger.info(f"Sent generated file {file_name} to chat {chat_id}")
    except Exception as e:
        logger.error(f"Error generating/sending file for chat {chat_id}: {e}")
        bot.reply_to(message, "Sorry, couldn't generate or send the file.")
    finally:
        if os.path.exists(file_name):
            os.remove(file_name) # Clean up the generated file

@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message): # Renamed function
    user_id = message.from_user.id
    chat_id = message.chat.id
    logger.info(f"Received /start or /help command from user {user_id} in chat {chat_id}")
    try:
        db.save_user(message.from_user, chat_id)
        db.save_message(message)
        command = message.text.split()[0].replace('/', '')
        db.log_interaction(user_id, f"command_{command}")
        prefs = db.get_user_preferences(user_id)
        user_sessions[user_id] = {'state': 'main_menu', 'data': {}, 'preferences': prefs}
        welcome_text = "Welcome to the bot! Choose an option:"
        if prefs.get('language') == 'es':
            welcome_text = "¡Bienvenido al bot! Elige una opción:"
        send_main_menu_message(chat_id, welcome_text)
        logger.info(f"Sent welcome message with main menu to user {user_id}")
    except Exception as e:
        logger.error(f"Error during handle_start_help for user {user_id}: {e}", exc_info=True)
        try:
            bot.reply_to(message, "Sorry, something went wrong. Please try /start again later.")
        except Exception as send_error:
            logger.error(f"Failed to send error message to user {user_id}: {send_error}")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    message_id = message.message_id
    logger.info(f"Received photo from user {user_id} in chat {chat_id}, message_id {message_id}")
    db.save_user(message.from_user, chat_id)
    db.save_message(message) # Saves the photo message entry
    db.log_interaction(user_id, "photo_message")

    if not message.photo:
        bot.reply_to(message, "I couldn't find any image data in your message.")
        db.log_interaction(user_id, 'photo_message_no_data')
        send_main_menu_message(chat_id)
        return

    file_id = message.photo[-1].file_id
    logger.info(f"Image received from user {user_id}, message ID {message_id}. File ID: {file_id}")
    processing_msg = bot.reply_to(message, "Processing your image...")

    image_path = None
    try:
        image_path = download_image_from_telegram(file_id, user_id, message_id)
        if not image_path:
            bot.edit_message_text("Sorry, I couldn't download your image.", chat_id, processing_msg.message_id)
            db.log_interaction(user_id, 'download_image_error', {'file_id': file_id})
            return

        logger.info(f"Starting image processing workflow for user {user_id}")
        gemini_response, error_msg = google_apis.process_image_with_gemini(image_path, user_id)

        if error_msg or not gemini_response:
            error_text = error_msg or "AI service returned no response."
            bot.edit_message_text(f"Sorry, I couldn't process your image. Error: {error_text}", chat_id, processing_msg.message_id)
            db.log_interaction(user_id, 'gemini_processing_error', {'error': error_text})
            return

        result_text = google_apis.extract_text_from_gemini_response(gemini_response)
        logger.info(f"Extracted text from Gemini for user {user_id}: {result_text[:100]}...")

        # Convert pipe-separated string to JSON string for storage
        json_to_save = result_text # Default to original text if conversion fails
        try:
            if result_text and '|' in result_text and '=' in result_text:
                pairs = result_text.strip().split('|')
                data_dict = {}
                for pair in pairs:
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        data_dict[key.strip()] = None if value.lower() == 'null' else value.strip()
                    else: logger.warning(f"Skipping invalid pair '{pair}' in Gemini response for user {user_id}")
                if data_dict:
                    json_to_save = json.dumps(data_dict, ensure_ascii=False, indent=2)
                    logger.info(f"Successfully converted extracted text to JSON for user {user_id}")
                else: logger.warning(f"Could not parse key-value pairs from Gemini response for user {user_id}. Saving original text.")
            else: logger.warning(f"Extracted text for user {user_id} not pipe-separated. Saving original text.")
        except Exception as e:
            logger.error(f"Error converting pipe-separated string to JSON for user {user_id}: {e}", exc_info=True)

        # Save result to image_processing_results table
        save_success = db.save_image_processing_result(user_id, message_id, file_id, json_to_save)
        if not save_success: logger.warning(f"Failed to save image processing result to DB for user {user_id}")

        # Save processed text to user_messages table
        db.save_processed_text(user_id, chat_id, message_id, json_to_save, 'processed_text_from_image')

        # Send result back to user
        final_message_text = f"Extracted Information:\n\n{result_text}"
        if len(final_message_text) > 4096:
            final_message_text = final_message_text[:4093] + "..."
            logger.warning(f"Truncated long extracted text message for user {user_id}")
        bot.edit_message_text(final_message_text, chat_id, processing_msg.message_id)
        db.log_interaction(user_id, 'sent_extracted_text', {'length': len(result_text)})
        logger.info(f"Successfully completed image processing workflow for user {user_id}")
        send_main_menu_message(chat_id, text="Image processed. What would you like to do next?")

    except Exception as e:
        logger.error(f"Error in image processing workflow: {str(e)}", exc_info=True)
        try:
            bot.edit_message_text("Sorry, an error occurred while processing your image.", chat_id, processing_msg.message_id)
        except Exception as api_e:
             logger.error(f"Failed to send error message to user {user_id}: {api_e}")
        db.log_interaction(user_id, 'photo_workflow_error', {'error': str(e)})
    finally:
        utils.cleanup_temp_file(image_path)
        logger.info(f"Completed image processing workflow cleanup for user {user_id}")


@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    db.save_user(message.from_user, chat_id)
    db.save_message(message)
    db.log_interaction(user_id, "text_message")

    if message.text.startswith('/'):
        bot.reply_to(message, "Sorry, I don't understand that command.")
        logger.info(f"Skipped sending main menu from handle_text for command '{message.text}' in chat {chat_id}")
    else:
        if config.DEBUG_MODE:
            message_history = db.get_user_message_history(user_id, limit=10)
            if message_history:
                history_text = "📝 Your message history:\n\n"
                for i, msg in enumerate(message_history[1:], 1): # Skip current message
                    timestamp = datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00'))
                    formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    history_text += f"{i}. [{formatted_time}] {msg['message_text']}\n"
                if len(message_history) <= 1: history_text += "No previous messages found."
                bot.reply_to(message, history_text)
            else:
                bot.reply_to(message, "Received your message. No history found.")
        else:
             bot.reply_to(message, "Received your message.") # Simplified reply in production

        # Send main menu only for non-command text messages
        send_main_menu_message(chat_id)
        logger.info(f"Sent main menu after handling non-command text from chat {chat_id}")


# --- Callback Query Handler ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id # Message where the button was clicked
    callback_data = call.data

    db.save_user(call.from_user, chat_id)
    db.log_interaction(user_id, "button_click", callback_data)

    # Ensure user session exists
    if user_id not in user_sessions:
        prefs = db.get_user_preferences(user_id)
        user_sessions[user_id] = {'state': 'main_menu', 'data': {}, 'preferences': prefs}

    try: # Wrap handler logic in try/except
        # --- Retrieve Form Data ---
        if callback_data == "retrieve_form":
            logger.info(f"User {user_id}: Clicked 'Retrieve Form Data'")
            if not config.GOOGLE_FORM_ID:
                bot.answer_callback_query(call.id, "Form retrieval not configured.", show_alert=True)
                return
            bot.edit_message_text("Searching for form response ID...", chat_id, message_id)
            response_id = db.find_form_response_id(user_id)
            if not response_id:
                bot.edit_message_text("Could not find 'form=<number>' in recent history.", chat_id, message_id, reply_markup=generate_main_menu())
                return
            bot.edit_message_text(f"Found ID: {response_id}. Retrieving data...", chat_id, message_id)
            form_data, error_message = google_apis.get_google_form_response(config.GOOGLE_FORM_ID, response_id)
            if form_data:
                try:
                    form_data_json_string = json.dumps(form_data, indent=2, ensure_ascii=False)
                    db.save_processed_text(user_id, chat_id, message_id, form_data_json_string, 'retrieved_form_data')
                    display_text = f"📄 Form Response Data (ID: {response_id}):\n\n```json\n{form_data_json_string}\n```"
                    if len(display_text) > 4000: display_text = display_text[:4000] + "... (truncated)\n```"
                    bot.edit_message_text(display_text, chat_id, message_id, reply_markup=generate_main_menu(), parse_mode="Markdown")
                    db.log_interaction(user_id, "form_retrieval_success", {'response_id': response_id})
                except Exception as display_e:
                     logger.error(f"Error formatting/displaying form data: {display_e}", exc_info=True)
                     bot.edit_message_text(f"Retrieved data for {response_id}, but failed to display.", chat_id, message_id, reply_markup=generate_main_menu())
            else:
                bot.edit_message_text(f"❌ Failed to retrieve form data:\n{error_message}", chat_id, message_id, reply_markup=generate_main_menu())
                db.log_interaction(user_id, "form_retrieval_failed", {'response_id': response_id, 'error': error_message})

        # --- Retrieve Sheet Data ---
        elif callback_data == "retrieve_sheet_data":
            logger.info(f"User {user_id}: Clicked 'Retrieve Sheet Data'")
            if not config.APPS_SCRIPT_WEB_APP_URL: # Check Web App URL as primary method
                bot.answer_callback_query(call.id, "Sheet retrieval via Web App not configured.", show_alert=True)
                return
            bot.edit_message_text("Searching for ID (form=<number>)...", chat_id, message_id)
            id_to_find = db.find_form_response_id(user_id)
            if not id_to_find:
                bot.edit_message_text("Could not find 'form=<number>' in recent history.", chat_id, message_id, reply_markup=generate_main_menu())
                return
            logger.info(f"Calling get_sheet_data_via_webapp for ID: {id_to_find}")
            sheet_data, error_message = google_apis.get_sheet_data_via_webapp(id_to_find)
            if sheet_data is not None:
                try:
                    sheet_data_json_string = json.dumps(sheet_data, indent=2, ensure_ascii=False)
                    db.save_processed_text(user_id, chat_id, message_id, sheet_data_json_string, 'retrieved_sheet_data')
                    display_text = f"📈 Sheet Data (ID: {id_to_find}):\n\n```json\n{sheet_data_json_string}\n```"
                    if len(display_text) > 4000: display_text = display_text[:4000] + "... (truncated)\n```"
                    bot.edit_message_text(display_text, chat_id, message_id, reply_markup=generate_main_menu(), parse_mode="Markdown")
                    db.log_interaction(user_id, "sheet_retrieval_success", {'id_found': id_to_find})
                except Exception as display_e:
                     logger.error(f"Error formatting/displaying sheet data: {display_e}", exc_info=True)
                     bot.edit_message_text(f"Retrieved sheet data for {id_to_find}, but failed to display.", chat_id, message_id, reply_markup=generate_main_menu())
            else:
                bot.edit_message_text(f"❌ Failed to retrieve sheet data:\n{error_message}", chat_id, message_id, reply_markup=generate_main_menu())
                db.log_interaction(user_id, "sheet_retrieval_failed", {'id_found': id_to_find, 'error': error_message})

        # --- View My Data ---
        elif callback_data == "view_my_data":
            logger.info(f"User {user_id}: Requested to view their data")
            user_data = db.get_user_data_summary(user_id)
            if user_data and 'profile' in user_data:
                profile = user_data['profile']
                data_text = "📊 Your Data Summary\n\nProfile:\n"
                data_text += f"• Username: @{profile.get('username') or 'N/A'}\n"
                data_text += f"• Name: {profile.get('first_name', '')} {profile.get('last_name', '')}\n"
                data_text += f"• Joined: {profile.get('created_at', 'N/A')}\n\nPreferences:\n"
                data_text += f"• Language: {profile.get('language', 'en')}\n\nActivity:\n"
                data_text += f"• Messages: {user_data.get('message_count', 0)}\n"
                data_text += f"• Interactions: {user_data.get('interaction_count', 0)}\n\nRecent Messages:\n"
                if user_data.get('recent_messages'):
                    for i, msg in enumerate(user_data['recent_messages'], 1):
                        msg_text = msg.get('message_text', '[Media]')
                        if msg_text: # Check if msg_text is not None
                            data_text += f"{i}. {msg_text[:30]}{'...' if len(msg_text)>30 else ''}\n"
                        else:
                            data_text += f"{i}. [Media message]\n" # Handle None case
                else: data_text += "None\n"
                markup = InlineKeyboardMarkup().add(InlineKeyboardButton("Back to Main Menu", callback_data="main_menu"))
                bot.edit_message_text(data_text, chat_id, message_id, reply_markup=markup)
            else:
                bot.edit_message_text("No data found.", chat_id, message_id, reply_markup=generate_main_menu())

        # --- Delete My Data ---
        elif callback_data == "delete_my_data":
            logger.info(f"User {user_id}: Requested data deletion")
            user_sessions[user_id]['state'] = 'delete_confirmation'
            bot.edit_message_text("⚠️ Sure you want to delete all data? Cannot be undone.", chat_id, message_id, reply_markup=generate_delete_confirmation_menu())

        elif callback_data == "confirm_delete":
            logger.info(f"User {user_id}: Confirmed data deletion")
            success, msg_del, int_del = db.delete_user_data(user_id)
            if user_id in user_sessions: del user_sessions[user_id] # Clear session
            if success:
                bot.edit_message_text(f"✅ Data deleted ({msg_del} msgs, {int_del} interactions). Use /start again.", chat_id, message_id)
                # Send new menu message after edit
                send_main_menu_message(chat_id, text="Data deleted. Choose an option:")
            else:
                bot.edit_message_text("❌ Error deleting data.", chat_id, message_id, reply_markup=generate_main_menu())

        elif callback_data == "cancel_delete":
            logger.info(f"User {user_id}: Canceled data deletion")
            user_sessions[user_id]['state'] = 'main_menu'
            bot.edit_message_text("Operation canceled.", chat_id, message_id, reply_markup=generate_main_menu())

        # --- Menu 1 (Analyze Messages) ---
        elif callback_data == "menu1":
            logger.info(f"User {user_id}: Menu 1 (Analyze Messages) selected")
            user_sessions[user_id]['state'] = 'menu1'
            bot.edit_message_text("Analyzing messages...", chat_id, message_id)
            messages = db.get_user_message_history(user_id, limit=20)
            if not messages:
                bot.edit_message_text("No messages to analyze.", chat_id, message_id, reply_markup=generate_main_menu())
                return

            prompt = "Analyze the following user messages and check if there are questions or instructions about what you should do. Your response must include the answer(s) to all questions and instructions. Keep your response concise and friendly and ALLWAYS in Spanish:\n\n"
            for msg in messages:
                msg_text = msg.get('message_text')
                if msg_text and not (isinstance(msg_text, str) and msg_text.startswith('/')):
                    try: # Format JSON nicely if possible
                        if isinstance(msg_text, str) and msg_text.startswith('{') and msg_text.endswith('}'):
                            json_data = json.loads(msg_text)
                            formatted_json = json.dumps(json_data, indent=2, ensure_ascii=False)
                            prompt += f"- JSON Data: {formatted_json}\n"
                        else: prompt += f"- {msg_text}\n"
                    except: prompt += f"- {msg_text}\n" # Fallback

            logger.info(f"Sending prompt to Gemini for analysis (user {user_id}): {prompt[:500]}...")
            analysis_result, error_msg = google_apis.analyze_text_with_gemini(prompt, user_id)

            if error_msg or not analysis_result:
                 error_text = error_msg or "AI service returned no response."
                 bot.edit_message_text(f"Sorry, couldn't analyze messages. Error: {error_text}", chat_id, message_id, reply_markup=generate_main_menu())
            else:
                 bot.edit_message_text(f"📊 Analysis:\n\n{analysis_result}", chat_id, message_id, reply_markup=generate_main_menu())

        # --- Menu 2 (Example) ---
        elif callback_data == "menu2":
            logger.info(f"User {user_id}: Menu 2 selected")
            user_sessions[user_id]['state'] = 'menu2'
            bot.edit_message_text("Selected Menu 2. Choose subitem:", chat_id, message_id, reply_markup=generate_submenu("menu2"))

        # --- Back to Main Menu ---
        elif callback_data == "main_menu":
            logger.info(f"User {user_id}: Returned to main menu")
            user_sessions[user_id]['state'] = 'main_menu'
            bot.edit_message_text("Main Menu:", chat_id, message_id, reply_markup=generate_main_menu())

        # --- Submenu Items (Example) ---
        elif callback_data.endswith(("_sub1", "_sub2")):
            logger.info(f"User {user_id}: Processing {callback_data}")
            user_sessions[user_id]['data']['selected_item'] = callback_data
            bot.answer_callback_query(call.id, f"Processing {callback_data}...")
            # Example: Send result/confirmation then menu
            # bot.send_message(chat_id, f"Action {callback_data} completed.")
            send_main_menu_message(chat_id, text=f"{callback_data} processed. Choose next option:")
            # Edit original message to remove buttons or show confirmation
            bot.edit_message_text(f"Action '{callback_data}' processed.", chat_id, message_id, reply_markup=None)


        # --- Default Fallback ---
        else:
            logger.warning(f"Unhandled callback data from user {user_id}: {callback_data}")
            bot.answer_callback_query(call.id, "Action not recognized.")

    except telebot.apihelper.ApiTelegramException as api_ex:
         # Handle cases where the message might have been deleted or cannot be edited
         if "message to edit not found" in str(api_ex) or "message can't be edited" in str(api_ex):
              logger.warning(f"Could not edit message {message_id} for chat {chat_id}. It might have been deleted or is too old. Sending new message instead.")
              # Try sending a new message with the main menu as a fallback
              send_main_menu_message(chat_id, "Please choose an option:")
         else:
              # Log other API errors
              logger.error(f"Telegram API error handling callback '{callback_data}' for user {user_id}: {api_ex}", exc_info=True)
              bot.answer_callback_query(call.id, "Sorry, a Telegram error occurred.", show_alert=True)
    except Exception as e:
        logger.error(f"Error handling callback query '{callback_data}' for user {user_id}: {e}", exc_info=True)
        try:
            # Try to answer the callback query even if processing failed
            bot.answer_callback_query(call.id, "An error occurred processing your request.", show_alert=True)
            # Optionally try to reset the menu
            bot.edit_message_text("An error occurred. Please try again.", chat_id, message_id, reply_markup=generate_main_menu())
        except Exception as nested_e:
            logger.error(f"Failed to send error feedback for callback '{callback_data}' to user {user_id}: {nested_e}")
