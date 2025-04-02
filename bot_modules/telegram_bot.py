import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import logging
import os
import tempfile
import uuid
import json
from datetime import datetime
import traceback
import re # Import re for regex matching
import time # Import time for timing checks

# Import from other modules using relative paths
from . import config
from . import database as db
from . import google_apis
from . import utils
from . import strings_es
from . import strings_en

# Somewhere early in your main bot script or __init__.py
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# Configure root logger for DEBUG level if not already done elsewhere
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
# Ensure logger level is set appropriately (e.g., in your main script or config)
# logger.setLevel(logging.DEBUG) # Example: Set level here if needed

# Set language based on environment
BOT_LANGUAGE = os.getenv('BOT_LANGUAGE', 'english').lower()
s = strings_es if BOT_LANGUAGE == 'spanish' else strings_en
logger.info(f"BOT_LANGUAGE set to: {BOT_LANGUAGE}")

# Initialize bot
bot = telebot.TeleBot(config.TOKEN)
logger.info("TeleBot initialized.")

# User sessions (kept in memory for simplicity, consider persistent storage for production)
user_sessions = {}
logger.info("In-memory user_sessions initialized.")

# --- Menu Generation ---
def generate_main_menu():
    logger.debug(">>> Entering generate_main_menu")
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    logger.debug("Adding main menu buttons: VIEW_DATA, DELETE_DATA")
    markup.add(InlineKeyboardButton(s.BUTTON_VIEW_DATA, callback_data=s.CALLBACK_DATA_VIEW_DATA))
    markup.add(InlineKeyboardButton(s.BUTTON_DELETE_DATA, callback_data=s.CALLBACK_DATA_DELETE_DATA))

    logger.debug(s.LOG_MENU_GENERATION_DEBUG.format(debug_mode=config.DEBUG_MODE, base_url=config.BASE_URL))
    if not config.DEBUG_MODE and config.BASE_URL and config.BASE_URL.startswith("https://"):
        logger.info(s.LOG_MENU_GENERATION_ADDING_WEBAPPS)
        web_app_buttons = []
        logger.debug(s.LOG_MENU_GENERATION_CHECKING_URL.format(url=config.WEBAPP_EDIT_MESSAGES_URL))
        if config.WEBAPP_EDIT_MESSAGES_URL and config.WEBAPP_EDIT_MESSAGES_URL.startswith("https://"):
            logger.info(s.LOG_MENU_GENERATION_ADDING_BUTTON.format(button_text=s.BUTTON_EDIT_MESSAGES))
            web_app_buttons.append(
                 InlineKeyboardButton(s.BUTTON_EDIT_MESSAGES, web_app=WebAppInfo(config.WEBAPP_EDIT_MESSAGES_URL))
            )
        if web_app_buttons:
             logger.info(s.LOG_MENU_GENERATION_ADDING_WEBAPP_BUTTONS.format(count=len(web_app_buttons)))
             markup.add(*web_app_buttons)
             logger.debug("Added Web App buttons to markup.")
        else:
             logger.warning(s.WARN_MENU_GENERATION_NO_WEBAPP_BUTTONS)
    elif not config.BASE_URL or not config.BASE_URL.startswith("https://"):
        logger.warning(s.WARN_MENU_GENERATION_NO_HTTPS)
    else:
         logger.info(s.LOG_MENU_GENERATION_DEBUG_SKIPPING_WEBAPPS)
    logger.debug("<<< Exiting generate_main_menu")
    return markup

def generate_submenu(menu_id):
    logger.debug(f">>> Entering generate_submenu for menu_id: {menu_id}")
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    logger.debug("Adding submenu buttons: SUBITEM_1, SUBITEM_2, BACK_MAIN_MENU")
    markup.add(
        InlineKeyboardButton(s.BUTTON_SUBITEM_1.format(menu_id=menu_id), callback_data=s.CALLBACK_DATA_SUBITEM_1.format(menu_id=menu_id)),
        InlineKeyboardButton(s.BUTTON_SUBITEM_2.format(menu_id=menu_id), callback_data=s.CALLBACK_DATA_SUBITEM_2.format(menu_id=menu_id)),
        InlineKeyboardButton(s.BUTTON_BACK_MAIN_MENU, callback_data=s.CALLBACK_DATA_MAIN_MENU)
    )
    logger.debug("<<< Exiting generate_submenu")
    return markup

def generate_delete_confirmation_menu():
    logger.debug(">>> Entering generate_delete_confirmation_menu")
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    logger.debug("Adding delete confirmation buttons: CONFIRM_DELETE, CANCEL_DELETE")
    markup.add(
        InlineKeyboardButton(s.BUTTON_CONFIRM_DELETE, callback_data=s.CALLBACK_DATA_CONFIRM_DELETE),
        InlineKeyboardButton(s.BUTTON_CANCEL_DELETE, callback_data=s.CALLBACK_DATA_CANCEL_DELETE)
    )
    logger.debug("<<< Exiting generate_delete_confirmation_menu")
    return markup

def send_main_menu_message(chat_id, text="Choose an option from the menu:"):
    """Sends a new message with the main menu."""
    logger.debug(f">>> Entering send_main_menu_message for chat_id: {chat_id}, text: '{text}'")
    try:
        logger.debug("Generating main menu markup...")
        markup = generate_main_menu()
        logger.debug(f"Attempting bot.send_message with chat_id={chat_id}, text='{text}'")
        bot.send_message(chat_id, text, reply_markup=markup)
        logger.info(s.LOG_SENT_MAIN_MENU.format(chat_id=chat_id))
    except Exception as e:
        logger.error(s.ERROR_SENDING_MAIN_MENU.format(chat_id=chat_id, error=e), exc_info=True)
    logger.debug("<<< Exiting send_main_menu_message")


# --- Telegram Utilities ---
def download_image_from_telegram(file_id, user_id, message_id):
    """Download an image from Telegram servers using file_id"""
    logger.debug(f">>> Entering download_image_from_telegram for file_id: {file_id}, user_id: {user_id}")
    logger.info(s.LOG_IMAGE_DOWNLOAD_START.format(file_id=file_id, user_id=user_id, message_id=message_id))
    local_file_path = None
    try:
        logger.debug("Calling bot.get_file...")
        file_info = bot.get_file(file_id)
        file_path = file_info.file_path
        logger.debug(f"Got file_info, file_path: {file_path}")
        temp_dir = tempfile.gettempdir()
        unique_filename = f"{uuid.uuid4().hex}.jpg"
        local_file_path = os.path.join(temp_dir, unique_filename)
        logger.debug(f"Generated local_file_path: {local_file_path}")
        logger.debug("Calling bot.download_file...")
        downloaded_file = bot.download_file(file_path)
        logger.debug(f"Downloaded file size (in memory): {len(downloaded_file)} bytes")
        logger.debug(f"Writing downloaded file to {local_file_path}...")
        with open(local_file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        file_size = os.path.getsize(local_file_path)
        logger.info(s.LOG_IMAGE_DOWNLOAD_SUCCESS.format(path=local_file_path, size=file_size))
        logger.debug("<<< Exiting download_image_from_telegram (Success)")
        return local_file_path
    except Exception as e:
        logger.error(s.ERROR_IMAGE_DOWNLOAD.format(error=str(e)), exc_info=True)
        logger.debug("<<< Exiting download_image_from_telegram (Failure)")
        return None

# --- Message Handlers ---
@bot.message_handler(commands=['generate_file'])
def handle_generate_file(message):
    logger.debug(f">>> Entering handle_generate_file for chat_id: {message.chat.id}")
    chat_id = message.chat.id
    file_name = "example.txt"
    try:
        logger.debug(f"Writing to temporary file: {file_name}")
        with open(file_name, "w") as file:
            file.write("Hello! This is your generated file.\n")
            file.write("This is an example of a Telegram bot sending files.")
        logger.debug(f"Sending document: {file_name}")
        with open(file_name, "rb") as file:
            bot.send_document(chat_id, file)
        logger.info(s.LOG_SENT_GENERATED_FILE.format(filename=file_name, chat_id=chat_id))
    except Exception as e:
        logger.error(s.ERROR_GENERATING_FILE.format(chat_id=chat_id, error=e), exc_info=True)
        try:
            logger.debug("Replying with error message.")
            bot.reply_to(message, s.ERROR_GENERATING_FILE_USER_MSG)
        except Exception as reply_err:
             logger.error(f"Failed to send error reply in handle_generate_file: {reply_err}")
    finally:
        if os.path.exists(file_name):
            logger.debug(f"Cleaning up temporary file: {file_name}")
            os.remove(file_name)
    logger.debug("<<< Exiting handle_generate_file")


@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    command = message.text.split()[0].replace('/', '')
    logger.debug(f">>> Entering handle_start_help for user: {user_id}, chat: {chat_id}, command: {command}")
    logger.info(s.LOG_RECEIVED_COMMAND.format(command=command, user_id=user_id, chat_id=chat_id))
    try:
        logger.debug(f"Saving user {user_id}...")
        db.save_user(message.from_user, chat_id)
        logger.debug(f"Saving message for user {user_id}...")
        db.save_message(message)
        logger.debug(f"Logging interaction 'command_{command}' for user {user_id}...")
        db.log_interaction(user_id, f"command_{command}")
        logger.debug(f"Getting preferences for user {user_id}...")
        prefs = db.get_user_preferences(user_id)
        logger.debug(f"User {user_id} preferences: {prefs}")
        logger.debug(f"Initializing session for user {user_id}...")
        user_sessions[user_id] = {'state': s.USER_STATE_MAIN_MENU, 'data': {}, 'preferences': prefs}
        welcome_text_key = s.WELCOME_MESSAGE_DEFAULT_ES if prefs.get('language') == 'es' else s.WELCOME_MESSAGE_DEFAULT
        logger.debug(f"Determined welcome text key: {welcome_text_key}")
        logger.debug(f"Calling send_main_menu_message for chat_id {chat_id}...")
        send_main_menu_message(chat_id, welcome_text_key)
        logger.info(s.LOG_SENT_WELCOME_MENU.format(user_id=user_id))
    except Exception as e:
        logger.error(s.ERROR_START_HELP_FAILED.format(user_id=user_id, error=e), exc_info=True)
        try:
            logger.debug(f"Replying with error message to user {user_id}...")
            bot.reply_to(message, s.ERROR_START_HELP_USER_MSG)
        except Exception as send_error:
            logger.error(s.ERROR_SENDING_ERROR_MSG.format(user_id=user_id, error=send_error), exc_info=True)
    logger.debug("<<< Exiting handle_start_help")


@bot.message_handler(content_types=[s.DB_MESSAGE_TYPE_PHOTO])
def handle_photo(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    message_id = message.message_id
    logger.debug(f">>> Entering handle_photo for user: {user_id}, chat: {chat_id}, msg_id: {message_id}")
    logger.info(s.LOG_RECEIVED_PHOTO.format(user_id=user_id, chat_id=chat_id, message_id=message_id))
    logger.debug(f"Saving user {user_id}...")
    db.save_user(message.from_user, chat_id)
    logger.debug(f"Saving photo message for user {user_id}...")
    db.save_message(message) # Saves the photo message entry
    logger.debug(f"Logging interaction '{s.DB_MESSAGE_TYPE_PHOTO}' for user {user_id}...")
    db.log_interaction(user_id, s.DB_MESSAGE_TYPE_PHOTO)

    if not message.photo:
        logger.warning(f"No photo data found in message {message_id} from user {user_id}.")
        bot.reply_to(message, s.PHOTO_NO_DATA_USER_MSG)
        db.log_interaction(user_id, s.LOG_PHOTO_NO_DATA)
        logger.debug(f"Calling send_main_menu_message for chat_id {chat_id} after no photo data.")
        send_main_menu_message(chat_id)
        logger.debug("<<< Exiting handle_photo (No photo data)")
        return

    file_id = message.photo[-1].file_id
    logger.info(s.LOG_IMAGE_RECEIVED_DETAILS.format(user_id=user_id, message_id=message_id, file_id=file_id))
    logger.debug(f"Replying with processing message to user {user_id}...")
    processing_msg = bot.reply_to(message, s.PHOTO_PROCESSING_USER_MSG)
    logger.debug(f"Processing message sent, ID: {processing_msg.message_id}")

    image_path = None
    try:
        logger.debug(f"Attempting to download image for file_id: {file_id}")
        image_path = download_image_from_telegram(file_id, user_id, message_id)
        if not image_path:
            logger.warning(f"Image download failed for file_id: {file_id}")
            logger.debug(f"Editing message {processing_msg.message_id} to show download failed.")
            bot.edit_message_text(s.PHOTO_DOWNLOAD_FAILED_USER_MSG, chat_id, processing_msg.message_id)
            db.log_interaction(user_id, s.LOG_DOWNLOAD_IMAGE_ERROR, {'file_id': file_id})
            logger.debug("<<< Exiting handle_photo (Download failed)")
            return

        logger.info(s.LOG_IMAGE_PROCESSING_WORKFLOW_START.format(user_id=user_id))
        logger.debug(f"Calling google_apis.process_image_with_gemini for path: {image_path}")
        gemini_response, error_msg = google_apis.process_image_with_gemini(image_path, user_id)
        logger.debug(f"Gemini response received. Error msg: '{error_msg}'. Response exists: {gemini_response is not None}")

        if error_msg or not gemini_response:
            error_text = error_msg or s.ERROR_AI_NO_RESPONSE
            logger.warning(f"Gemini processing failed or no response for user {user_id}. Error: {error_text}")
            logger.debug(f"Editing message {processing_msg.message_id} to show processing failed.")
            bot.edit_message_text(s.PHOTO_PROCESSING_FAILED_USER_MSG.format(error_text=error_text), chat_id, processing_msg.message_id)
            db.log_interaction(user_id, s.LOG_GEMINI_PROCESSING_ERROR, {'error': error_text})
            logger.debug("<<< Exiting handle_photo (Gemini processing failed)")
            return

        logger.debug("Extracting text from Gemini response...")
        result_text = google_apis.extract_text_from_gemini_response(gemini_response)
        logger.info(s.LOG_EXTRACTED_TEXT_PREVIEW.format(user_id=user_id, text_preview=result_text[:100]))

        # Convert pipe-separated string to JSON string for storage
        json_to_save = result_text # Default
        logger.debug("Attempting to convert extracted text to JSON...")
        try:
            if result_text and '|' in result_text and '=' in result_text:
                logger.debug("Text seems pipe-separated, splitting...")
                pairs = result_text.strip().split('|')
                data_dict = {}
                for pair in pairs:
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        data_dict[key.strip()] = None if value.lower() == 'null' else value.strip()
                    else: logger.warning(s.WARN_CONVERSION_INVALID_PAIR.format(pair=pair, user_id=user_id))
                if data_dict:
                    logger.debug(f"Conversion successful, dict: {data_dict}")
                    json_to_save = json.dumps(data_dict, ensure_ascii=False, indent=2)
                    logger.info(s.LOG_CONVERTED_TO_JSON.format(user_id=user_id))
                else: logger.warning(s.WARN_CONVERSION_NO_PAIRS.format(user_id=user_id))
            else: logger.warning(s.WARN_CONVERSION_NOT_PIPE_SEPARATED.format(user_id=user_id))
        except Exception as e:
            logger.error(s.ERROR_CONVERTING_TO_JSON.format(user_id=user_id, error=e), exc_info=True)
        logger.debug(f"Final data to save (JSON or original text): {json_to_save[:100]}...")

        # Save result to image_processing_results table
        logger.debug(f"Saving image processing result to DB for user {user_id}, msg_id {message_id}...")
        save_success = db.save_image_processing_result(user_id, message_id, file_id, json_to_save)
        if not save_success: logger.warning(s.WARN_FAILED_SAVING_IMAGE_RESULT.format(user_id=user_id))
        else: logger.debug("Image processing result saved successfully.")

        # Save processed text to user_messages table
        logger.debug(f"Saving processed text to user_messages DB for user {user_id}, original msg_id {message_id}...")
        db.save_processed_text(user_id, chat_id, message_id, json_to_save, s.DB_MESSAGE_TYPE_PROCESSED_IMAGE)
        logger.debug("Processed text saved to user_messages.")

        # Send result back to user
        final_message_text = s.PHOTO_EXTRACTED_INFO_USER_MSG.format(result_text=result_text)
        logger.debug(f"Prepared final message text (len: {len(final_message_text)}).")
        if len(final_message_text) > 4096:
            final_message_text = final_message_text[:4093] + "..."
            logger.warning(s.WARN_TRUNCATED_MESSAGE.format(user_id=user_id))
        logger.debug(f"Editing message {processing_msg.message_id} to show final result.")
        bot.edit_message_text(final_message_text, chat_id, processing_msg.message_id)
        db.log_interaction(user_id, s.LOG_SENT_EXTRACTED_TEXT, {'length': len(result_text)})
        logger.info(s.LOG_IMAGE_PROCESSING_WORKFLOW_SUCCESS.format(user_id=user_id))
        logger.debug(f"Calling send_main_menu_message for chat_id {chat_id} after photo processing.")
        send_main_menu_message(chat_id, text=s.PHOTO_PROCESSED_NEXT_ACTION_USER_MSG)

    except Exception as e:
        logger.error(s.ERROR_IMAGE_WORKFLOW.format(error=str(e)), exc_info=True)
        try:
            logger.debug(f"Editing message {processing_msg.message_id} to show generic photo error.")
            bot.edit_message_text(s.PHOTO_ERROR_USER_MSG, chat_id, processing_msg.message_id)
        except Exception as api_e:
             logger.error(s.ERROR_SENDING_ERROR_MSG.format(user_id=user_id, error=api_e), exc_info=True)
        db.log_interaction(user_id, s.LOG_PHOTO_WORKFLOW_ERROR, {'error': str(e)})
    finally:
        logger.debug(f"Cleaning up temporary image file: {image_path}")
        utils.cleanup_temp_file(image_path)
        logger.info(s.LOG_IMAGE_WORKFLOW_CLEANUP_COMPLETE.format(user_id=user_id))
    logger.debug("<<< Exiting handle_photo")


# --- Helper Function for Gemini Analysis ---
def _trigger_gemini_analysis(user_id, chat_id, message_id_to_edit=None, latest_message_text=None):
    """Fetches history, optionally adds latest message, calls Gemini, and replies/edits."""
    logger.debug(f">>> Entering _trigger_gemini_analysis for user: {user_id}, chat: {chat_id}, edit_id: {message_id_to_edit}, latest_text: {latest_message_text is not None}")
    processing_message_id = None
    try:
        # Send "Analyzing..." message
        if message_id_to_edit is None:
            logger.debug("Sending new 'Analyzing...' message.")
            processing_msg = bot.send_message(chat_id, s.CALLBACK_ANALYZING_MESSAGES)
            processing_message_id = processing_msg.message_id
            logger.debug(f"New processing message ID: {processing_message_id}")
        else:
            logger.debug(f"Editing message {message_id_to_edit} to 'Analyzing...'.")
            bot.edit_message_text(s.CALLBACK_ANALYZING_MESSAGES, chat_id, message_id_to_edit)
            processing_message_id = message_id_to_edit
            logger.debug(f"Using existing message ID for processing: {processing_message_id}")

        # Fetch history
        logger.debug(f"Fetching message history for user {user_id}...")
        messages = db.get_user_message_history(user_id, include_text=True, limit=20) # Ensure include_text=True
        logger.debug(f"Fetched {len(messages)} messages from history.")

        if not messages and not latest_message_text:
            logger.warning(f"No messages found to analyze for user {user_id}.")
            bot.edit_message_text(s.CALLBACK_NO_MESSAGES_TO_ANALYZE, chat_id, processing_message_id, reply_markup=generate_main_menu())
            logger.debug("<<< Exiting _trigger_gemini_analysis (No messages)")
            return

        # Construct the prompt
        prompt = s.GEMINI_PROMPT_TEXT_ANALYSIS
        logger.debug("Base prompt set.")

        # Add the latest message text first
        if latest_message_text and not latest_message_text.startswith('/'):
             logger.debug("Adding latest_message_text to prompt.")
             prompt += s.CALLBACK_ANALYSIS_PROMPT_TEXT.format(text=latest_message_text)

        # Add historical messages
        logger.debug("Adding historical messages to prompt...")
        history_added_count = 0
        for msg in messages:
            msg_text = msg.get('message_text')
            if msg_text and msg_text != latest_message_text and not (isinstance(msg_text, str) and msg_text.startswith('/')):
                history_added_count += 1
                try: # Format JSON nicely
                    if isinstance(msg_text, str) and msg_text.startswith('{') and msg_text.endswith('}'):
                        json_data = json.loads(msg_text)
                        formatted_json = json.dumps(json_data, indent=2, ensure_ascii=False)
                        prompt += s.CALLBACK_ANALYSIS_PROMPT_JSON.format(formatted_json=formatted_json)
                    else: prompt += s.CALLBACK_ANALYSIS_PROMPT_TEXT.format(text=msg_text)
                except Exception as format_err:
                    logger.warning(f"Could not format message text, adding as raw string. Error: {format_err}")
                    prompt += s.CALLBACK_ANALYSIS_PROMPT_TEXT.format(text=str(msg_text)) # Add as string
        logger.debug(f"Added {history_added_count} historical messages to prompt.")

        logger.info(s.LOG_SENDING_PROMPT_TO_GEMINI.format(user_id=user_id, prompt_preview=prompt[:500]))
        logger.debug("Calling google_apis.analyze_text_with_gemini...")
        analysis_result, error_msg = google_apis.analyze_text_with_gemini(prompt, user_id)
        logger.debug(f"Gemini text analysis result received. Error msg: '{error_msg}'. Result exists: {analysis_result is not None}")

        if error_msg or not analysis_result:
             error_text = error_msg or s.ERROR_AI_NO_RESPONSE
             logger.warning(f"Gemini text analysis failed for user {user_id}. Error: {error_text}")
             logger.debug(f"Editing message {processing_message_id} to show analysis error.")
             bot.edit_message_text(s.CALLBACK_ANALYSIS_ERROR_USER_MSG.format(error_text=error_text), chat_id, processing_message_id, reply_markup=generate_main_menu())
        else:
             logger.debug(f"Gemini analysis successful. Result length: {len(analysis_result)}")
             final_text = s.CALLBACK_ANALYSIS_RESULT_USER_MSG.format(analysis_result=analysis_result)
             if len(final_text) > 4096:
                 final_text = final_text[:4093] + "..."
                 logger.warning(s.LOG_GEMINI_ANALYSIS_TRUNCATED.format(user_id=user_id))
             logger.debug(f"Editing message {processing_message_id} to show analysis result.")
             bot.edit_message_text(final_text, chat_id, processing_message_id, reply_markup=generate_main_menu())
             logger.debug("Analysis result sent to user.")

    except Exception as e:
        logger.error(s.LOG_TRIGGER_GEMINI_ERROR.format(user_id=user_id, error=e), exc_info=True)
        try:
            error_edit_id = processing_message_id if processing_message_id else message_id_to_edit
            if error_edit_id:
                logger.debug(f"Attempting to edit message {error_edit_id} to show generic error.")
                bot.edit_message_text(s.ERROR_PROCESSING_REQUEST, chat_id, error_edit_id, reply_markup=generate_main_menu())
            else:
                logger.warning("No message ID available to edit for error message, sending new message.")
                bot.send_message(chat_id, s.ERROR_PROCESSING_REQUEST, reply_markup=generate_main_menu())
        except Exception as nested_e:
            logger.error(s.LOG_TRIGGER_GEMINI_RECOVERY_FAIL.format(nested_error=nested_e), exc_info=True)
    logger.debug("<<< Exiting _trigger_gemini_analysis")


@bot.message_handler(func=lambda message: True, content_types=[s.DB_MESSAGE_TYPE_TEXT])
def handle_text(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    logger.debug(f">>> Entering handle_text for user: {user_id}, chat: {chat_id}. Text: '{message.text[:50]}...'")
    logger.debug(f"Saving user {user_id}...")
    db.save_user(message.from_user, chat_id)

    # --- Keyword Detection ---
    data_entry_keyword_pattern = re.compile(r"^(dato|datos)(:)?\s*", re.IGNORECASE)
    match = data_entry_keyword_pattern.match(message.text)
    logger.debug(f"Checking for data entry keyword. Match found: {match is not None}")

    if match:
        keyword_length = match.end()
        data_content = message.text[keyword_length:].strip()
        logger.info(s.LOG_DATA_ENTRY_DETECTED.format(content_preview=data_content[:50]))
        logger.debug(f"Saving message as data_entry for user {user_id}. Content: '{data_content[:50]}...'")
        db.save_message(message, message_type_override=s.DB_MESSAGE_TYPE_DATA_ENTRY, text_override=data_content)
        logger.debug(f"Logging interaction '{s.DB_MESSAGE_TYPE_DATA_ENTRY}' for user {user_id}.")
        db.log_interaction(user_id, s.DB_MESSAGE_TYPE_DATA_ENTRY, {'original_text': message.text})
        logger.debug(f"Replying with data entry confirmation to user {user_id}.")
        bot.reply_to(message, s.CONFIRM_DATA_ENTRY_SAVED)
        logger.debug(f"Calling send_main_menu_message for chat_id {chat_id} after data entry.")
        send_main_menu_message(chat_id)
        logger.debug("<<< Exiting handle_text (Data entry handled)")
        return

    # --- Default Text Handling ---
    logger.debug(f"No data entry keyword found. Saving message as text for user {user_id}.")
    db.save_message(message)
    logger.debug(f"Logging interaction '{s.DB_MESSAGE_TYPE_TEXT}' for user {user_id}.")
    db.log_interaction(user_id, s.DB_MESSAGE_TYPE_TEXT)

    if message.text.startswith('/'):
        logger.warning(f"Received unknown command '{message.text}' from user {user_id}.")
        bot.reply_to(message, s.TEXT_UNKNOWN_COMMAND_USER_MSG)
        logger.info(s.LOG_SKIPPED_MENU_FOR_COMMAND.format(command=message.text, chat_id=chat_id))
    else:
       logger.info(s.LOG_TRIGGER_GEMINI_TEXT_MSG.format(user_id=user_id))
       logger.debug(f"Calling _trigger_gemini_analysis for user {user_id} with latest text.")
       _trigger_gemini_analysis(user_id, chat_id, latest_message_text=message.text)
       # Menu is sent by the helper function now
    logger.debug("<<< Exiting handle_text (Default handling)")


# --- Callback Query Handler ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    # --- START: INSANE LOGGING ---
    start_time = time.monotonic()
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    callback_data = call.data
    callback_id = call.id
    logger.debug(f"-------------------------------------------------------------")
    logger.debug(f">>> Entering handle_callback_query at {datetime.now()}")
    logger.debug(f"    User ID: {user_id}, Chat ID: {chat_id}, Message ID: {message_id}")
    logger.debug(f"    Callback ID: {callback_id}, Callback Data: '{callback_data}'")
    logger.debug(f"    Original Message Text (preview): {call.message.text[:100] if call.message.text else '[No Text]'}")
    logger.debug(f"    Original Message Buttons: {call.message.reply_markup is not None}")
    # --- END: INSANE LOGGING ---

    logger.debug(f"Saving user {user_id} from callback...")
    db.save_user(call.from_user, chat_id)
    logger.debug(f"Logging interaction '{s.LOG_BUTTON_CLICK}' for user {user_id}, data: '{callback_data}'")
    db.log_interaction(user_id, s.LOG_BUTTON_CLICK, callback_data)

    # Ensure user session exists
    if user_id not in user_sessions:
        logger.warning(f"User session for {user_id} not found! Reinitializing.")
        prefs = db.get_user_preferences(user_id)
        user_sessions[user_id] = {'state': s.USER_STATE_MAIN_MENU, 'data': {}, 'preferences': prefs}
        logger.debug(f"Reinitialized session for {user_id}: {user_sessions[user_id]}")
    else:
        logger.debug(f"Existing session found for user {user_id}: {user_sessions[user_id]}")


    try: # Wrap handler logic in try/except
        logger.debug(f"Callback Handler: Entering main try block for callback_data '{callback_data}'")
        # --- Retrieve Form Data ---
        if callback_data == s.CALLBACK_DATA_RETRIEVE_FORM:
            # ... (Keep existing logging or add more if needed) ...
            logger.info(s.LOG_CALLBACK_RETRIEVE_FORM.format(user_id=user_id))
            # ... rest of the logic ...

        # --- Retrieve Sheet Data ---
        elif callback_data == s.CALLBACK_DATA_RETRIEVE_SHEET:
            # ... (Keep existing logging or add more if needed) ...
            logger.info(s.LOG_CALLBACK_RETRIEVE_SHEET.format(user_id=user_id))
            # ... rest of the logic ...

        # --- View My Data ---
        elif callback_data == s.CALLBACK_DATA_VIEW_DATA:
            # --- START: INSANE LOGGING for view_my_data ---
            logger.debug(f"Callback Handler: Matched '{s.CALLBACK_DATA_VIEW_DATA}'")
            logger.info(s.LOG_CALLBACK_VIEW_DATA.format(user_id=user_id))
            logger.debug(f"Attempting to get user data summary from DB for user {user_id}...")
            db_start_time = time.monotonic()
            user_data = db.get_user_data_summary(user_id)
            db_end_time = time.monotonic()
            logger.debug(f"DB get_user_data_summary took {db_end_time - db_start_time:.4f} seconds.")
            logger.debug(f"DB Result user_data type: {type(user_data)}")
            # Log first few chars if it's a dict/list, or the value itself otherwise
            if isinstance(user_data, (dict, list)):
                 logger.debug(f"DB Result user_data (preview): {str(user_data)[:200]}")
            else:
                 logger.debug(f"DB Result user_data: {user_data}")

            if user_data and 'profile' in user_data:
                logger.debug("Callback Handler: Path A (user_data and profile found)")
                profile = user_data['profile']
                logger.debug(f"Profile data: {profile}")
                data_text = s.CALLBACK_DATA_SUMMARY_HEADER
                logger.debug("Starting data_text construction...")
                data_text += s.CALLBACK_DATA_SUMMARY_PROFILE.format(
                    username=profile.get('username') or 'N/A',
                    first_name=profile.get('first_name', ''),
                    last_name=profile.get('last_name', ''),
                    created_at=profile.get('created_at', 'N/A')
                )
                data_text += s.CALLBACK_DATA_SUMMARY_PREFS.format(language=profile.get('language', 'en'))
                data_text += s.CALLBACK_DATA_SUMMARY_ACTIVITY.format(
                    message_count=user_data.get('message_count', 0),
                    interaction_count=user_data.get('interaction_count', 0)
                )
                logger.debug("Constructed profile/prefs/activity part of data_text.")
                if user_data.get('recent_messages'):
                    logger.debug(f"Processing {len(user_data['recent_messages'])} recent messages...")
                    for i, msg in enumerate(user_data['recent_messages'], 1):
                        logger.debug(f"  Processing recent message #{i}: {str(msg)[:100]}")
                        msg_text = msg.get('message_text')
                        logger.debug(f"    msg_text type: {type(msg_text)}, value (preview): {str(msg_text)[:50]}")
                        if msg_text is None:
                            text_preview = s.CALLBACK_DATA_SUMMARY_NO_TEXT
                            ellipsis = ''
                        elif isinstance(msg_text, str):
                            if msg_text.lower() == "/start":
                                logger.debug("    Skipping /start message.")
                                continue
                            ellipsis = '...' if len(msg_text) > 30 else ''
                            text_preview = msg_text[:30]
                        else:
                            logger.warning(s.LOG_VIEW_DATA_UNEXPECTED_TYPE.format(type=type(msg_text), value_repr=repr(msg_text)))
                            text_preview = s.CALLBACK_DATA_SUMMARY_NO_TEXT
                            ellipsis = ''
                        logger.debug(f"    Adding to data_text: index={i}, preview='{text_preview}', ellipsis='{ellipsis}'")
                        data_text += s.CALLBACK_DATA_SUMMARY_RECENT_MSG.format(index=i, text_preview=text_preview, ellipsis=ellipsis)
                    logger.debug("Finished processing recent messages.")
                else:
                    logger.debug("No recent messages found.")
                    data_text += s.CALLBACK_DATA_SUMMARY_NO_RECENT

                logger.debug("Generating 'Back' button markup...")
                markup = InlineKeyboardMarkup().add(InlineKeyboardButton(s.BUTTON_BACK_MAIN_MENU, callback_data=s.CALLBACK_DATA_MAIN_MENU))
                logger.debug(f"Attempting bot.edit_message_text for message_id {message_id} (Path A - Success)")
                logger.debug(f"  Text (preview): {data_text[:200]}...")
                logger.debug(f"  Markup buttons: {[btn.text for row in markup.keyboard for btn in row]}")
                bot.edit_message_text(data_text, chat_id, message_id, reply_markup=markup)
                logger.debug(f"Successfully edited message {message_id} with data view.")
            else:
                logger.warning(f"Callback Handler: Path B (user_data is None, empty, or missing 'profile') for user {user_id}")
                logger.debug(f"Attempting bot.edit_message_text for message_id {message_id} (Path B - No Data)")
                logger.debug(f"  Text: {s.CALLBACK_NO_DATA_FOUND}")
                logger.debug(f"  Markup: Main Menu")
                bot.edit_message_text(s.CALLBACK_NO_DATA_FOUND, chat_id, message_id, reply_markup=generate_main_menu())
                logger.debug(f"Successfully edited message {message_id} with 'No data found' + Main Menu.")
            logger.debug(f"Finished processing '{s.CALLBACK_DATA_VIEW_DATA}' block.")
            # --- END: INSANE LOGGING for view_my_data ---

        # --- Delete My Data ---
        elif callback_data == s.CALLBACK_DATA_DELETE_DATA:
            logger.debug(f"Callback Handler: Matched '{s.CALLBACK_DATA_DELETE_DATA}'")
            logger.info(s.LOG_CALLBACK_DELETE_DATA.format(user_id=user_id))
            logger.debug(f"Setting user {user_id} state to '{s.USER_STATE_DELETE_CONFIRMATION}'")
            user_sessions[user_id]['state'] = s.USER_STATE_DELETE_CONFIRMATION
            logger.debug(f"Attempting bot.edit_message_text for message_id {message_id} (Delete Confirmation)")
            bot.edit_message_text(s.CALLBACK_DELETE_CONFIRMATION_USER_MSG, chat_id, message_id, reply_markup=generate_delete_confirmation_menu())
            logger.debug(f"Successfully edited message {message_id} with delete confirmation.")

        elif callback_data == s.CALLBACK_DATA_CONFIRM_DELETE:
            logger.debug(f"Callback Handler: Matched '{s.CALLBACK_DATA_CONFIRM_DELETE}'")
            logger.info(s.LOG_CALLBACK_CONFIRM_DELETE.format(user_id=user_id))
            logger.debug(f"Attempting to delete data for user {user_id} from DB...")
            db_del_start = time.monotonic()
            success, msg_del, int_del = db.delete_user_data(user_id)
            db_del_end = time.monotonic()
            logger.debug(f"DB delete_user_data took {db_del_end - db_del_start:.4f} seconds. Success: {success}, Counts: {msg_del}, {int_del}")
            if user_id in user_sessions:
                logger.debug(f"Deleting in-memory session for user {user_id}")
                del user_sessions[user_id]
            if success:
                logger.debug(f"Attempting bot.edit_message_text for message_id {message_id} (Delete Success)")
                bot.edit_message_text(s.CALLBACK_DELETE_SUCCESS_USER_MSG.format(msg_del=msg_del, int_del=int_del), chat_id, message_id)
                logger.debug(f"Successfully edited message {message_id} with delete success.")
                logger.debug(f"Calling send_main_menu_message for chat_id {chat_id} after delete success.")
                send_main_menu_message(chat_id, text=s.CALLBACK_DELETE_SUCCESS_NEXT_ACTION)
            else:
                logger.error(f"Data deletion failed in DB for user {user_id}.")
                logger.debug(f"Attempting bot.edit_message_text for message_id {message_id} (Delete Error)")
                bot.edit_message_text(s.CALLBACK_DELETE_ERROR_USER_MSG, chat_id, message_id, reply_markup=generate_main_menu())
                logger.debug(f"Successfully edited message {message_id} with delete error + Main Menu.")

        elif callback_data == s.CALLBACK_DATA_CANCEL_DELETE:
            logger.debug(f"Callback Handler: Matched '{s.CALLBACK_DATA_CANCEL_DELETE}'")
            logger.info(s.LOG_CALLBACK_CANCEL_DELETE.format(user_id=user_id))
            logger.debug(f"Setting user {user_id} state back to '{s.USER_STATE_MAIN_MENU}'")
            user_sessions[user_id]['state'] = s.USER_STATE_MAIN_MENU
            logger.debug(f"Attempting bot.edit_message_text for message_id {message_id} (Cancel Delete)")
            bot.edit_message_text(s.OPERATION_CANCELED, chat_id, message_id, reply_markup=generate_main_menu())
            logger.debug(f"Successfully edited message {message_id} with cancel confirmation + Main Menu.")

        # --- Menu 1 (Analyze Messages) ---
        elif callback_data == s.CALLBACK_DATA_MENU1:
            logger.debug(f"Callback Handler: Matched '{s.CALLBACK_DATA_MENU1}'")
            logger.info(s.LOG_CALLBACK_MENU1.format(user_id=user_id))
            logger.debug(f"Setting user {user_id} state to '{s.USER_STATE_MENU1}'")
            user_sessions[user_id]['state'] = s.USER_STATE_MENU1
            logger.debug(f"Calling _trigger_gemini_analysis for user {user_id}, editing message {message_id}")
            _trigger_gemini_analysis(user_id, chat_id, message_id_to_edit=message_id)
            logger.debug(f"Returned from _trigger_gemini_analysis for '{s.CALLBACK_DATA_MENU1}'")

        # --- Menu 2 (Example) ---
        elif callback_data == s.CALLBACK_DATA_MENU2:
            logger.debug(f"Callback Handler: Matched '{s.CALLBACK_DATA_MENU2}'")
            logger.info(s.LOG_CALLBACK_MENU2.format(user_id=user_id))
            logger.debug(f"Setting user {user_id} state to '{s.USER_STATE_MENU2}'")
            user_sessions[user_id]['state'] = s.USER_STATE_MENU2
            logger.debug(f"Attempting bot.edit_message_text for message_id {message_id} (Menu 2)")
            bot.edit_message_text(s.CALLBACK_MENU2_USER_MSG, chat_id, message_id, reply_markup=generate_submenu(s.CALLBACK_DATA_MENU2))
            logger.debug(f"Successfully edited message {message_id} with Menu 2 submenu.")

        # --- Back to Main Menu ---
        elif callback_data == s.CALLBACK_DATA_MAIN_MENU:
            logger.debug(f"Callback Handler: Matched '{s.CALLBACK_DATA_MAIN_MENU}'")
            logger.info(s.LOG_CALLBACK_MAIN_MENU.format(user_id=user_id))
            logger.debug(f"Setting user {user_id} state to '{s.USER_STATE_MAIN_MENU}'")
            user_sessions[user_id]['state'] = s.USER_STATE_MAIN_MENU
            logger.debug(f"Attempting bot.edit_message_text for message_id {message_id} (Back to Main)")
            bot.edit_message_text(s.CALLBACK_MAIN_MENU_USER_MSG, chat_id, message_id, reply_markup=generate_main_menu())
            logger.debug(f"Successfully edited message {message_id} with main menu.")

        # --- Submenu Items (Example) ---
        elif callback_data.endswith(("_sub1", "_sub2")):
            logger.debug(f"Callback Handler: Matched submenu item '{callback_data}'")
            logger.info(s.LOG_CALLBACK_SUBMENU.format(user_id=user_id, callback_data=callback_data))
            logger.debug(f"Setting user {user_id} data 'selected_item' to '{callback_data}'")
            user_sessions[user_id]['data']['selected_item'] = callback_data
            logger.debug(f"Answering callback query {callback_id}...")
            bot.answer_callback_query(call.id, s.CALLBACK_PROCESSING_SUBMENU.format(callback_data=callback_data))
            logger.debug(f"Calling send_main_menu_message for chat_id {chat_id} after submenu action.")
            send_main_menu_message(chat_id, text=s.CALLBACK_SUBMENU_PROCESSED_NEXT_ACTION.format(callback_data=callback_data))
            logger.debug(f"Attempting bot.edit_message_text for message_id {message_id} (Submenu Action Processed)")
            bot.edit_message_text(s.CALLBACK_SUBMENU_ACTION_PROCESSED.format(callback_data=callback_data), chat_id, message_id, reply_markup=None)
            logger.debug(f"Successfully edited message {message_id} after submenu action.")

        # --- Default Fallback ---
        else:
            logger.warning(s.WARN_UNHANDLED_CALLBACK.format(user_id=user_id, callback_data=callback_data))
            logger.debug(f"Answering callback query {callback_id} with Action Not Recognized.")
            bot.answer_callback_query(call.id, s.ACTION_NOT_RECOGNIZED)

        logger.debug(f"Callback Handler: Reached end of main try block for callback_data '{callback_data}'")

    except telebot.apihelper.ApiTelegramException as api_ex:
         logger.error(f"Callback Handler: Caught ApiTelegramException: {api_ex}", exc_info=True) # Log exception info
         if "message to edit not found" in str(api_ex) or "message can't be edited" in str(api_ex):
              logger.warning(s.WARN_EDIT_MESSAGE_NOT_FOUND.format(message_id=message_id, chat_id=chat_id))
              logger.debug(f"Calling send_main_menu_message for chat_id {chat_id} as fallback.")
              send_main_menu_message(chat_id, s.CALLBACK_DEFAULT_USER_MSG)
         else:
              logger.error(s.ERROR_CALLBACK_API.format(callback_data=callback_data, user_id=user_id, api_ex=api_ex), exc_info=True)
              try:
                  logger.debug(f"Answering callback query {callback_id} with API Error.")
                  bot.answer_callback_query(call.id, s.ERROR_CALLBACK_API_USER_MSG, show_alert=True)
              except Exception as nested_ans_err:
                   logger.error(f"Failed to answer callback query during API error handling: {nested_ans_err}")

    except Exception as e:
        logger.error(f"Callback Handler: Caught generic Exception: {e}", exc_info=True) # Log exception info
        logger.error(s.ERROR_CALLBACK_GENERAL.format(callback_data=callback_data, user_id=user_id, error=e), exc_info=True)
        try:
            logger.debug(f"Answering callback query {callback_id} with General Error.")
            bot.answer_callback_query(call.id, s.ERROR_CALLBACK_GENERAL_USER_MSG, show_alert=True)
            logger.debug(f"Attempting bot.edit_message_text for message_id {message_id} (General Error Fallback)")
            bot.edit_message_text(s.ERROR_CALLBACK_GENERAL_EDIT_MSG, chat_id, message_id, reply_markup=generate_main_menu())
            logger.debug(f"Successfully edited message {message_id} with general error + Main Menu.")
        except Exception as nested_e:
            logger.error(s.ERROR_SENDING_CALLBACK_FEEDBACK.format(callback_data=callback_data, user_id=user_id, nested_error=nested_e), exc_info=True)

    finally:
        # --- START: INSANE LOGGING ---
        end_time = time.monotonic()
        duration = end_time - start_time
        logger.debug(f"<<< Exiting handle_callback_query for callback_data '{callback_data}' at {datetime.now()}. Duration: {duration:.4f} seconds.")
        logger.debug(f"-------------------------------------------------------------")
        # --- END: INSANE LOGGING ---