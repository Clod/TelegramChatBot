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

# Import from other modules using relative paths
from . import config
from . import database as db
from . import google_apis
from . import utils
from . import strings as s # Import strings

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
        InlineKeyboardButton(s.BUTTON_ANALYZE_MESSAGES, callback_data=s.CALLBACK_DATA_MENU1),
        InlineKeyboardButton(s.BUTTON_RETRIEVE_FORM, callback_data=s.CALLBACK_DATA_RETRIEVE_FORM),
        InlineKeyboardButton(s.BUTTON_RETRIEVE_SHEET, callback_data=s.CALLBACK_DATA_RETRIEVE_SHEET),
        InlineKeyboardButton(s.BUTTON_MENU2, callback_data=s.CALLBACK_DATA_MENU2)
    )
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
        else:
             logger.warning(s.WARN_MENU_GENERATION_NO_WEBAPP_BUTTONS)
    elif not config.BASE_URL or not config.BASE_URL.startswith("https://"):
        logger.warning(s.WARN_MENU_GENERATION_NO_HTTPS)
    else:
         logger.info(s.LOG_MENU_GENERATION_DEBUG_SKIPPING_WEBAPPS)
    return markup

def generate_submenu(menu_id):
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton(s.BUTTON_SUBITEM_1.format(menu_id=menu_id), callback_data=s.CALLBACK_DATA_SUBITEM_1.format(menu_id=menu_id)),
        InlineKeyboardButton(s.BUTTON_SUBITEM_2.format(menu_id=menu_id), callback_data=s.CALLBACK_DATA_SUBITEM_2.format(menu_id=menu_id)),
        InlineKeyboardButton(s.BUTTON_BACK_MAIN_MENU, callback_data=s.CALLBACK_DATA_MAIN_MENU)
    )
    return markup

def generate_delete_confirmation_menu():
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton(s.BUTTON_CONFIRM_DELETE, callback_data=s.CALLBACK_DATA_CONFIRM_DELETE),
        InlineKeyboardButton(s.BUTTON_CANCEL_DELETE, callback_data=s.CALLBACK_DATA_CANCEL_DELETE)
    )
    return markup

def send_main_menu_message(chat_id, text="Choose an option from the menu:"): # Keep default text here for now
    """Sends a new message with the main menu."""
    try:
        bot.send_message(chat_id, text, reply_markup=generate_main_menu())
        logger.info(s.LOG_SENT_MAIN_MENU.format(chat_id=chat_id))
    except Exception as e:
        logger.error(s.ERROR_SENDING_MAIN_MENU.format(chat_id=chat_id, error=e))

# --- Telegram Utilities ---
def download_image_from_telegram(file_id, user_id, message_id):
    """Download an image from Telegram servers using file_id"""
    logger.info(s.LOG_IMAGE_DOWNLOAD_START.format(file_id=file_id, user_id=user_id, message_id=message_id))
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
        logger.info(s.LOG_IMAGE_DOWNLOAD_SUCCESS.format(path=local_file_path, size=file_size))
        return local_file_path
    except Exception as e:
        logger.error(s.ERROR_IMAGE_DOWNLOAD.format(error=str(e)), exc_info=True)
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
        logger.info(s.LOG_SENT_GENERATED_FILE.format(filename=file_name, chat_id=chat_id))
    except Exception as e:
        logger.error(s.ERROR_GENERATING_FILE.format(chat_id=chat_id, error=e))
        bot.reply_to(message, s.ERROR_GENERATING_FILE_USER_MSG)
    finally:
        if os.path.exists(file_name):
            os.remove(file_name) # Clean up the generated file

@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message): # Renamed function
    user_id = message.from_user.id
    chat_id = message.chat.id
    command = message.text.split()[0].replace('/', '')
    logger.info(s.LOG_RECEIVED_COMMAND.format(command=command, user_id=user_id, chat_id=chat_id))
    try:
        db.save_user(message.from_user, chat_id)
        db.save_message(message)
        db.log_interaction(user_id, f"command_{command}")
        prefs = db.get_user_preferences(user_id)
        user_sessions[user_id] = {'state': s.USER_STATE_MAIN_MENU, 'data': {}, 'preferences': prefs}
        welcome_text = "Welcome to the bot! Choose an option:" # Keep default, localization can be complex
        if prefs.get('language') == 'es':
            welcome_text = "¡Bienvenido al bot! Elige una opción:" # Keep default, localization can be complex
        send_main_menu_message(chat_id, welcome_text)
        logger.info(s.LOG_SENT_WELCOME_MENU.format(user_id=user_id))
    except Exception as e:
        logger.error(s.ERROR_START_HELP_FAILED.format(user_id=user_id, error=e), exc_info=True)
        try:
            bot.reply_to(message, s.ERROR_START_HELP_USER_MSG)
        except Exception as send_error:
            logger.error(s.ERROR_SENDING_ERROR_MSG.format(user_id=user_id, error=send_error))

@bot.message_handler(content_types=[s.DB_MESSAGE_TYPE_PHOTO])
def handle_photo(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    message_id = message.message_id
    logger.info(s.LOG_RECEIVED_PHOTO.format(user_id=user_id, chat_id=chat_id, message_id=message_id))
    db.save_user(message.from_user, chat_id)
    db.save_message(message) # Saves the photo message entry
    db.log_interaction(user_id, s.DB_MESSAGE_TYPE_PHOTO)

    if not message.photo:
        bot.reply_to(message, s.PHOTO_NO_DATA_USER_MSG)
        db.log_interaction(user_id, s.LOG_PHOTO_NO_DATA)
        send_main_menu_message(chat_id)
        return

    file_id = message.photo[-1].file_id
    logger.info(s.LOG_IMAGE_RECEIVED_DETAILS.format(user_id=user_id, message_id=message_id, file_id=file_id))
    processing_msg = bot.reply_to(message, s.PHOTO_PROCESSING_USER_MSG)

    image_path = None
    try:
        image_path = download_image_from_telegram(file_id, user_id, message_id)
        if not image_path:
            bot.edit_message_text(s.PHOTO_DOWNLOAD_FAILED_USER_MSG, chat_id, processing_msg.message_id)
            db.log_interaction(user_id, s.LOG_DOWNLOAD_IMAGE_ERROR, {'file_id': file_id})
            return

        logger.info(s.LOG_IMAGE_PROCESSING_WORKFLOW_START.format(user_id=user_id))
        gemini_response, error_msg = google_apis.process_image_with_gemini(image_path, user_id)

        if error_msg or not gemini_response:
            error_text = error_msg or "AI service returned no response." # Keep default
            bot.edit_message_text(s.PHOTO_PROCESSING_FAILED_USER_MSG.format(error_text=error_text), chat_id, processing_msg.message_id)
            db.log_interaction(user_id, s.LOG_GEMINI_PROCESSING_ERROR, {'error': error_text})
            return

        result_text = google_apis.extract_text_from_gemini_response(gemini_response)
        logger.info(s.LOG_EXTRACTED_TEXT_PREVIEW.format(user_id=user_id, text_preview=result_text[:100]))

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
                    else: logger.warning(s.WARN_CONVERSION_INVALID_PAIR.format(pair=pair, user_id=user_id))
                if data_dict:
                    json_to_save = json.dumps(data_dict, ensure_ascii=False, indent=2)
                    logger.info(s.LOG_CONVERTED_TO_JSON.format(user_id=user_id))
                else: logger.warning(s.WARN_CONVERSION_NO_PAIRS.format(user_id=user_id))
            else: logger.warning(s.WARN_CONVERSION_NOT_PIPE_SEPARATED.format(user_id=user_id))
        except Exception as e:
            logger.error(s.ERROR_CONVERTING_TO_JSON.format(user_id=user_id, error=e), exc_info=True)

        # Save result to image_processing_results table
        save_success = db.save_image_processing_result(user_id, message_id, file_id, json_to_save)
        if not save_success: logger.warning(s.WARN_FAILED_SAVING_IMAGE_RESULT.format(user_id=user_id))

        # Save processed text to user_messages table
        db.save_processed_text(user_id, chat_id, message_id, json_to_save, s.DB_MESSAGE_TYPE_PROCESSED_IMAGE)

        # Send result back to user
        final_message_text = s.PHOTO_EXTRACTED_INFO_USER_MSG.format(result_text=result_text)
        if len(final_message_text) > 4096:
            final_message_text = final_message_text[:4093] + "..."
            logger.warning(s.WARN_TRUNCATED_MESSAGE.format(user_id=user_id))
        bot.edit_message_text(final_message_text, chat_id, processing_msg.message_id)
        db.log_interaction(user_id, s.LOG_SENT_EXTRACTED_TEXT, {'length': len(result_text)})
        logger.info(s.LOG_IMAGE_PROCESSING_WORKFLOW_SUCCESS.format(user_id=user_id))
        send_main_menu_message(chat_id, text=s.PHOTO_PROCESSED_NEXT_ACTION_USER_MSG)

    except Exception as e:
        logger.error(s.ERROR_IMAGE_WORKFLOW.format(error=str(e)), exc_info=True)
        try:
            bot.edit_message_text(s.PHOTO_ERROR_USER_MSG, chat_id, processing_msg.message_id)
        except Exception as api_e:
             logger.error(s.ERROR_SENDING_ERROR_MSG.format(user_id=user_id, error=api_e))
        db.log_interaction(user_id, s.LOG_PHOTO_WORKFLOW_ERROR, {'error': str(e)})
    finally:
        utils.cleanup_temp_file(image_path)
        logger.info(s.LOG_IMAGE_WORKFLOW_CLEANUP_COMPLETE.format(user_id=user_id))


@bot.message_handler(func=lambda message: True, content_types=[s.DB_MESSAGE_TYPE_TEXT])
def handle_text(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    db.save_user(message.from_user, chat_id)

    # --- Keyword Detection and Saving Logic ---
    data_entry_keyword_pattern = re.compile(r"^(dato|datos)(:)?\s*", re.IGNORECASE)
    match = data_entry_keyword_pattern.match(message.text)

    if match:
        # Keyword found, strip it and save as data_entry
        keyword_length = match.end() # Get the length of the matched keyword part
        data_content = message.text[keyword_length:].strip()
        logger.info(f"Detected data entry keyword. Saving content: '{data_content[:50]}...'")
        db.save_message(message, message_type_override=s.DB_MESSAGE_TYPE_DATA_ENTRY, text_override=data_content)
        db.log_interaction(user_id, s.DB_MESSAGE_TYPE_DATA_ENTRY, {'original_text': message.text}) # Log type and original text
        # Optionally, send a confirmation specific to data entry
        bot.reply_to(message, "Data entry saved.") # Example confirmation
        # Decide if you want to send the main menu after data entry or not
        # send_main_menu_message(chat_id) # Uncomment if you want the menu after data entry
        return # Stop further processing in this handler for data entry

    # --- Default Text Handling (No Keyword Match) ---
    # Save as regular text message
    db.save_message(message) # No overrides needed, uses default text type
    db.log_interaction(user_id, s.DB_MESSAGE_TYPE_TEXT) # Log as regular text interaction

    if message.text.startswith('/'):
        bot.reply_to(message, s.TEXT_UNKNOWN_COMMAND_USER_MSG)
        logger.info(s.LOG_SKIPPED_MENU_FOR_COMMAND.format(command=message.text, chat_id=chat_id))
    else:
        if config.DEBUG_MODE:
            message_history = db.get_user_message_history(user_id, limit=10)
            if message_history:
                history_text = s.TEXT_HISTORY_HEADER
                for i, msg in enumerate(message_history[1:], 1): # Skip current message
                    timestamp = datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00'))
                    formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    history_text += f"{i}. [{formatted_time}] {msg['message_text']}\n"
                if len(message_history) <= 1: history_text += s.TEXT_HISTORY_NO_PREVIOUS
                bot.reply_to(message, history_text)
            else:
                bot.reply_to(message, s.TEXT_RECEIVED_NO_HISTORY_USER_MSG)
        else:
             bot.reply_to(message, s.TEXT_RECEIVED_USER_MSG) # Simplified reply in production

        # Send main menu only for non-command text messages
        send_main_menu_message(chat_id)
        logger.info(s.LOG_SENT_MENU_AFTER_TEXT.format(chat_id=chat_id))


# --- Callback Query Handler ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id # Message where the button was clicked
    callback_data = call.data

    db.save_user(call.from_user, chat_id)
    db.log_interaction(user_id, s.LOG_BUTTON_CLICK, callback_data)

    # Ensure user session exists
    if user_id not in user_sessions:
        prefs = db.get_user_preferences(user_id)
        user_sessions[user_id] = {'state': s.USER_STATE_MAIN_MENU, 'data': {}, 'preferences': prefs}

    try: # Wrap handler logic in try/except
        # --- Retrieve Form Data ---
        if callback_data == s.CALLBACK_DATA_RETRIEVE_FORM:
            logger.info(s.LOG_CALLBACK_RETRIEVE_FORM.format(user_id=user_id))
            if not config.GOOGLE_FORM_ID:
                bot.answer_callback_query(call.id, s.CALLBACK_FORM_NOT_CONFIGURED, show_alert=True)
                return
            bot.edit_message_text(s.CALLBACK_SEARCHING_FORM_ID, chat_id, message_id)
            response_id = db.find_form_response_id(user_id)
            if not response_id:
                bot.edit_message_text(s.CALLBACK_FORM_ID_NOT_FOUND, chat_id, message_id, reply_markup=generate_main_menu())
                return
            bot.edit_message_text(s.CALLBACK_FOUND_FORM_ID.format(response_id=response_id), chat_id, message_id)
            form_data, error_message = google_apis.get_google_form_response(config.GOOGLE_FORM_ID, response_id)
            if form_data:
                try:
                    form_data_json_string = json.dumps(form_data, indent=2, ensure_ascii=False)
                    db.save_processed_text(user_id, chat_id, message_id, form_data_json_string, s.DB_MESSAGE_TYPE_RETRIEVED_FORM)
                    display_text = s.CALLBACK_FORM_DATA_DISPLAY.format(response_id=response_id, json_string=form_data_json_string)
                    if len(display_text) > 4000: display_text = display_text[:4000] + s.CALLBACK_FORM_DATA_TRUNCATED
                    bot.edit_message_text(display_text, chat_id, message_id, reply_markup=generate_main_menu(), parse_mode="Markdown")
                    db.log_interaction(user_id, s.LOG_FORM_RETRIEVAL_SUCCESS, {'response_id': response_id})
                except Exception as display_e:
                     logger.error(s.ERROR_DISPLAYING_FORM_DATA.format(error=display_e), exc_info=True)
                     bot.edit_message_text(s.CALLBACK_FORM_DISPLAY_ERROR_USER_MSG.format(response_id=response_id), chat_id, message_id, reply_markup=generate_main_menu())
            else:
                bot.edit_message_text(s.CALLBACK_FORM_RETRIEVAL_FAILED_USER_MSG.format(error_message=error_message), chat_id, message_id, reply_markup=generate_main_menu())
                db.log_interaction(user_id, s.LOG_FORM_RETRIEVAL_FAILED, {'response_id': response_id, 'error': error_message})

        # --- Retrieve Sheet Data ---
        elif callback_data == s.CALLBACK_DATA_RETRIEVE_SHEET:
            logger.info(s.LOG_CALLBACK_RETRIEVE_SHEET.format(user_id=user_id))
            if not config.APPS_SCRIPT_WEB_APP_URL: # Check Web App URL as primary method
                bot.answer_callback_query(call.id, s.CALLBACK_SHEET_NOT_CONFIGURED, show_alert=True)
                return
            bot.edit_message_text(s.CALLBACK_SEARCHING_SHEET_ID, chat_id, message_id)
            id_to_find = db.find_form_response_id(user_id)
            if not id_to_find:
                bot.edit_message_text(s.CALLBACK_FORM_ID_NOT_FOUND, chat_id, message_id, reply_markup=generate_main_menu()) # Re-use form ID not found message
                return
            logger.info(s.LOG_CALLING_WEB_APP.format(id_to_find=id_to_find))
            sheet_data, error_message = google_apis.get_sheet_data_via_webapp(id_to_find)
            if sheet_data is not None:
                try:
                    sheet_data_json_string = json.dumps(sheet_data, indent=2, ensure_ascii=False)
                    db.save_processed_text(user_id, chat_id, message_id, sheet_data_json_string, s.DB_MESSAGE_TYPE_RETRIEVED_SHEET)
                    display_text = s.CALLBACK_SHEET_DATA_DISPLAY.format(id_to_find=id_to_find, json_string=sheet_data_json_string)
                    if len(display_text) > 4000: display_text = display_text[:4000] + s.CALLBACK_FORM_DATA_TRUNCATED # Re-use truncation string
                    bot.edit_message_text(display_text, chat_id, message_id, reply_markup=generate_main_menu(), parse_mode="Markdown")
                    db.log_interaction(user_id, s.LOG_SHEET_RETRIEVAL_SUCCESS, {'id_found': id_to_find})
                except Exception as display_e:
                     logger.error(s.ERROR_DISPLAYING_SHEET_DATA.format(error=display_e), exc_info=True)
                     bot.edit_message_text(s.CALLBACK_SHEET_DISPLAY_ERROR_USER_MSG.format(id_to_find=id_to_find), chat_id, message_id, reply_markup=generate_main_menu())
            else:
                bot.edit_message_text(s.CALLBACK_SHEET_RETRIEVAL_FAILED_USER_MSG.format(error_message=error_message), chat_id, message_id, reply_markup=generate_main_menu())
                db.log_interaction(user_id, s.LOG_SHEET_RETRIEVAL_FAILED, {'id_found': id_to_find, 'error': error_message})

        # --- View My Data ---
        elif callback_data == s.CALLBACK_DATA_VIEW_DATA:
            logger.info(s.LOG_CALLBACK_VIEW_DATA.format(user_id=user_id))
            user_data = db.get_user_data_summary(user_id)
            if user_data and 'profile' in user_data:
                profile = user_data['profile']
                data_text = s.CALLBACK_DATA_SUMMARY_HEADER
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
                if user_data.get('recent_messages'):
                    for i, msg in enumerate(user_data['recent_messages'], 1):
                        msg_text = msg.get('message_text') # Get text, might be None or other type
                        if msg_text is None:
                            text_preview = s.CALLBACK_DATA_SUMMARY_NO_TEXT # Use placeholder for None
                            ellipsis = ''
                        elif isinstance(msg_text, str):
                            # Only calculate len() and slice if it's a string
                            ellipsis = '...' if len(msg_text) > 30 else ''
                            text_preview = msg_text[:30]
                        else:
                            # Handle unexpected non-string, non-None type
                            logger.warning(f"Unexpected type for message_text in view_my_data: {type(msg_text)}, value: {repr(msg_text)}")
                            text_preview = s.CALLBACK_DATA_SUMMARY_NO_TEXT # Use placeholder
                            ellipsis = ''
                        data_text += s.CALLBACK_DATA_SUMMARY_RECENT_MSG.format(index=i, text_preview=text_preview, ellipsis=ellipsis)
                else: data_text += s.CALLBACK_DATA_SUMMARY_NO_RECENT
                markup = InlineKeyboardMarkup().add(InlineKeyboardButton(s.BUTTON_BACK_MAIN_MENU, callback_data=s.CALLBACK_DATA_MAIN_MENU))
                bot.edit_message_text(data_text, chat_id, message_id, reply_markup=markup)
            else:
                bot.edit_message_text(s.CALLBACK_NO_DATA_FOUND, chat_id, message_id, reply_markup=generate_main_menu())

        # --- Delete My Data ---
        elif callback_data == s.CALLBACK_DATA_DELETE_DATA:
            logger.info(s.LOG_CALLBACK_DELETE_DATA.format(user_id=user_id))
            user_sessions[user_id]['state'] = s.USER_STATE_DELETE_CONFIRMATION
            bot.edit_message_text(s.CALLBACK_DELETE_CONFIRMATION_USER_MSG, chat_id, message_id, reply_markup=generate_delete_confirmation_menu())

        elif callback_data == s.CALLBACK_DATA_CONFIRM_DELETE:
            logger.info(s.LOG_CALLBACK_CONFIRM_DELETE.format(user_id=user_id))
            success, msg_del, int_del = db.delete_user_data(user_id)
            if user_id in user_sessions: del user_sessions[user_id] # Clear session
            if success:
                bot.edit_message_text(s.CALLBACK_DELETE_SUCCESS_USER_MSG.format(msg_del=msg_del, int_del=int_del), chat_id, message_id)
                # Send new menu message after edit
                send_main_menu_message(chat_id, text=s.CALLBACK_DELETE_SUCCESS_NEXT_ACTION)
            else:
                bot.edit_message_text(s.CALLBACK_DELETE_ERROR_USER_MSG, chat_id, message_id, reply_markup=generate_main_menu())

        elif callback_data == s.CALLBACK_DATA_CANCEL_DELETE:
            logger.info(s.LOG_CALLBACK_CANCEL_DELETE.format(user_id=user_id))
            user_sessions[user_id]['state'] = s.USER_STATE_MAIN_MENU
            bot.edit_message_text(s.OPERATION_CANCELED, chat_id, message_id, reply_markup=generate_main_menu())

        # --- Menu 1 (Analyze Messages) ---
        elif callback_data == s.CALLBACK_DATA_MENU1:
            logger.info(s.LOG_CALLBACK_MENU1.format(user_id=user_id))
            user_sessions[user_id]['state'] = s.USER_STATE_MENU1
            bot.edit_message_text(s.CALLBACK_ANALYZING_MESSAGES, chat_id, message_id)
            messages = db.get_user_message_history(user_id, limit=20)
            if not messages:
                bot.edit_message_text(s.CALLBACK_NO_MESSAGES_TO_ANALYZE, chat_id, message_id, reply_markup=generate_main_menu())
                return

            prompt = s.GEMINI_PROMPT_TEXT_ANALYSIS
            for msg in messages:
                msg_text = msg.get('message_text')
                if msg_text and not (isinstance(msg_text, str) and msg_text.startswith('/')):
                    try: # Format JSON nicely if possible
                        if isinstance(msg_text, str) and msg_text.startswith('{') and msg_text.endswith('}'):
                            json_data = json.loads(msg_text)
                            formatted_json = json.dumps(json_data, indent=2, ensure_ascii=False)
                            prompt += s.CALLBACK_ANALYSIS_PROMPT_JSON.format(formatted_json=formatted_json)
                        else: prompt += s.CALLBACK_ANALYSIS_PROMPT_TEXT.format(text=msg_text)
                    except: prompt += s.CALLBACK_ANALYSIS_PROMPT_TEXT.format(text=msg_text) # Fallback

            logger.info(s.LOG_SENDING_PROMPT_TO_GEMINI.format(user_id=user_id, prompt_preview=prompt[:500]))
            analysis_result, error_msg = google_apis.analyze_text_with_gemini(prompt, user_id)

            if error_msg or not analysis_result:
                 error_text = error_msg or "AI service returned no response." # Keep default
                 bot.edit_message_text(s.CALLBACK_ANALYSIS_ERROR_USER_MSG.format(error_text=error_text), chat_id, message_id, reply_markup=generate_main_menu())
            else:
                 bot.edit_message_text(s.CALLBACK_ANALYSIS_RESULT_USER_MSG.format(analysis_result=analysis_result), chat_id, message_id, reply_markup=generate_main_menu())

        # --- Menu 2 (Example) ---
        elif callback_data == s.CALLBACK_DATA_MENU2:
            logger.info(s.LOG_CALLBACK_MENU2.format(user_id=user_id))
            user_sessions[user_id]['state'] = s.USER_STATE_MENU2
            bot.edit_message_text(s.CALLBACK_MENU2_USER_MSG, chat_id, message_id, reply_markup=generate_submenu(s.CALLBACK_DATA_MENU2))

        # --- Back to Main Menu ---
        elif callback_data == s.CALLBACK_DATA_MAIN_MENU:
            logger.info(s.LOG_CALLBACK_MAIN_MENU.format(user_id=user_id))
            user_sessions[user_id]['state'] = s.USER_STATE_MAIN_MENU
            bot.edit_message_text(s.CALLBACK_MAIN_MENU_USER_MSG, chat_id, message_id, reply_markup=generate_main_menu())

        # --- Submenu Items (Example) ---
        elif callback_data.endswith(("_sub1", "_sub2")): # Keep this logic simple for example
            logger.info(s.LOG_CALLBACK_SUBMENU.format(user_id=user_id, callback_data=callback_data))
            user_sessions[user_id]['data']['selected_item'] = callback_data
            bot.answer_callback_query(call.id, s.CALLBACK_PROCESSING_SUBMENU.format(callback_data=callback_data))
            # Example: Send result/confirmation then menu
            # bot.send_message(chat_id, f"Action {callback_data} completed.")
            send_main_menu_message(chat_id, text=s.CALLBACK_SUBMENU_PROCESSED_NEXT_ACTION.format(callback_data=callback_data))
            # Edit original message to remove buttons or show confirmation
            bot.edit_message_text(s.CALLBACK_SUBMENU_ACTION_PROCESSED.format(callback_data=callback_data), chat_id, message_id, reply_markup=None)


        # --- Default Fallback ---
        else:
            logger.warning(s.WARN_UNHANDLED_CALLBACK.format(user_id=user_id, callback_data=callback_data))
            bot.answer_callback_query(call.id, s.ACTION_NOT_RECOGNIZED)

    except telebot.apihelper.ApiTelegramException as api_ex:
         # Handle cases where the message might have been deleted or cannot be edited
         if "message to edit not found" in str(api_ex) or "message can't be edited" in str(api_ex):
              logger.warning(s.WARN_EDIT_MESSAGE_NOT_FOUND.format(message_id=message_id, chat_id=chat_id))
              # Try sending a new message with the main menu as a fallback
              send_main_menu_message(chat_id, s.CALLBACK_DEFAULT_USER_MSG)
         else:
              # Log other API errors
              logger.error(s.ERROR_CALLBACK_API.format(callback_data=callback_data, user_id=user_id, api_ex=api_ex), exc_info=True)
              bot.answer_callback_query(call.id, s.ERROR_CALLBACK_API_USER_MSG, show_alert=True)
    except Exception as e:
        logger.error(s.ERROR_CALLBACK_GENERAL.format(callback_data=callback_data, user_id=user_id, error=e), exc_info=True)
        try:
            # Try to answer the callback query even if processing failed
            bot.answer_callback_query(call.id, s.ERROR_CALLBACK_GENERAL_USER_MSG, show_alert=True)
            # Optionally try to reset the menu
            bot.edit_message_text(s.ERROR_CALLBACK_GENERAL_EDIT_MSG, chat_id, message_id, reply_markup=generate_main_menu())
        except Exception as nested_e:
            logger.error(s.ERROR_SENDING_CALLBACK_FEEDBACK.format(callback_data=callback_data, user_id=user_id, nested_error=nested_e))
