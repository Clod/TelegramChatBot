from flask import Flask, request, jsonify, render_template
import logging
import telebot # Needed for Update processing
from datetime import datetime
import os
import json # Needed for Web App save route
from urllib.parse import parse_qs # For initData validation
import hmac # For initData validation
import hashlib # For initData validation

# Import from other modules using relative paths
from . import config
from .telegram_bot import bot, user_sessions # Import bot instance and sessions
from . import database as db # Import database functions
# Remove the individual strings_en/es imports if they are only used for 's'
# from . import strings_en
# from . import strings_es
# Import the configured 's' object directly
from .config import s

# Language selection is handled in config.py where 's' is defined
# BOT_LANGUAGE = os.getenv('BOT_LANGUAGE', 'english').lower() # This is redundant here
# s = strings_es if BOT_LANGUAGE == 'spanish' else strings_en # This is redundant here

logger = logging.getLogger(__name__)

# Initialize Flask app
# Point template folder to the root directory's 'templates' folder
app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'))

# --- Webhook and Basic Routes ---
@app.route('/' + config.TOKEN, methods=['POST'])
def webhook():
    try:
        json_string = request.stream.read().decode('utf-8')
        logger.info(s.LOG_WEBHOOK_RECEIVED.format(json_preview=json_string[:500])) # Log truncated update
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    except Exception as e:
        logger.error(s.ERROR_WEBHOOK_PROCESSING.format(error=str(e)), exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    return s.BOT_IS_RUNNING

# --- Webhook Management Routes ---
@app.route('/set_webhook')
def set_webhook():
    try:
        bot.remove_webhook()
        # Set webhook without sending certificate parameter
        bot.set_webhook(url=config.WEBHOOK_URL)
        logger.info(s.LOG_WEBHOOK_SET.format(url=config.WEBHOOK_URL))
        return s.FLASK_WEBHOOK_SET_SUCCESS
    except Exception as e:
        logger.error(s.ERROR_WEBHOOK_SET.format(error=e), exc_info=True)
        return s.FLASK_WEBHOOK_SET_ERROR.format(error=e), 500

@app.route('/webhook_info')
def webhook_info():
    try:
        info = bot.get_webhook_info()
        return jsonify({
            'url': info.url, 'has_custom_certificate': info.has_custom_certificate,
            'pending_update_count': info.pending_update_count, 'last_error_date': info.last_error_date,
            'last_error_message': info.last_error_message, 'max_connections': info.max_connections,
            'ip_address': info.ip_address
        })
    except Exception as e:
        logger.error(s.ERROR_WEBHOOK_INFO.format(error=e), exc_info=True)
        return jsonify({'error': str(e)}), 500

# --- Debugging and Info Routes ---
@app.route('/check_updates')
def check_updates():
    # Only intended for temporary debugging if webhook fails
    try:
        bot.remove_webhook()
        updates = bot.get_updates()
        # Re-set webhook immediately
        bot.set_webhook(url=config.WEBHOOK_URL)
        return jsonify([u.to_dict() for u in updates])
    except Exception as e:
        logger.error(s.ERROR_CHECK_UPDATES.format(error=e), exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/user_sessions')
def view_user_sessions_route(): # Renamed function
    # Return a sanitized version of user sessions
    return jsonify({
        'active_users': len(user_sessions),
        'sessions': {str(user_id): session.get('state', 'N/A') for user_id, session in user_sessions.items()}
    })

@app.route('/db_users')
def view_db_users_route(): # Renamed function
    try:
        users = db.get_all_db_users()
        return jsonify({'total_users': len(users), 'users': users})
    except Exception as e:
        logger.error(s.ERROR_DB_RETRIEVING_USERS.format(error=str(e)), exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/image_processing_results/<int:user_id>')
def view_image_processing_results_route(user_id): # Renamed function
    try:
        user = db.get_db_user_details(user_id)
        if not user: return jsonify({'error': s.ERROR_USER_NOT_FOUND}), 404
        results = db.get_db_image_processing_results(user_id)
        return jsonify({'user': user, 'image_processing_results': results, 'total_results': len(results)})
    except Exception as e:
        logger.error(s.ERROR_DB_RETRIEVING_IMAGE_RESULTS.format(error=str(e)), exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/user_messages/<int:user_id>')
def view_user_messages_route(user_id): # Renamed function
    try:
        user = db.get_db_user_details(user_id)
        if not user: return jsonify({'error': s.ERROR_USER_NOT_FOUND}), 404
        messages = db.get_db_user_messages(user_id)
        return jsonify({'user': user, 'messages': messages, 'total_messages': len(messages)})
    except Exception as e:
        logger.error(s.ERROR_DB_RETRIEVING_MESSAGES.format(error=str(e)), exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/user_interactions/<int:user_id>')
def view_user_interactions_route(user_id): # Renamed function
    try:
        user = db.get_db_user_details(user_id)
        if not user: return jsonify({'error': s.ERROR_USER_NOT_FOUND}), 404
        interactions = db.get_db_user_interactions(user_id)
        stats = db.get_db_interaction_stats(user_id)
        return jsonify({
            'user': user,
            'preferences': {'language': user.get('language', s.DB_DEFAULT_LANGUAGE), 'notifications': bool(user.get('notifications', True)), 'theme': user.get('theme', s.DB_DEFAULT_THEME)},
            'interactions': interactions, 'total_interactions': len(interactions), 'interaction_stats': stats
        })
    except Exception as e:
        logger.error(s.ERROR_DB_RETRIEVING_INTERACTIONS.format(error=str(e)), exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/update_preference/<int:user_id>', methods=['POST'])
def update_preference_route(user_id): # Renamed function
    try:
        data = request.json
        if not data or 'preference_name' not in data or 'preference_value' not in data:
            return jsonify({'error': s.ERROR_MISSING_PREFERENCE_FIELDS}), 400
        pref_name = data['preference_name']
        pref_value = data['preference_value']
        valid_prefs = ['language', 'notifications', 'theme']
        if pref_name not in valid_prefs:
            return jsonify({'error': s.ERROR_INVALID_PREFERENCE_NAME.format(valid_prefs=valid_prefs)}), 400
        success = db.update_user_preference(user_id, pref_name, pref_value)
        if success:
            if user_id in user_sessions: # Update active session too
                if 'preferences' not in user_sessions[user_id]: user_sessions[user_id]['preferences'] = db.get_user_preferences(user_id)
                else: user_sessions[user_id]['preferences'][pref_name] = pref_value
            return jsonify({'success': True, 'message': s.PREFERENCE_UPDATE_SUCCESS.format(pref_name=pref_name)})
        else:
            return jsonify({'error': s.ERROR_DB_UPDATING_PREFERENCE}), 500
    except Exception as e:
        logger.error(s.ERROR_UPDATING_PREFERENCE.format(error=str(e)), exc_info=True)
        return jsonify({'error': str(e)}), 500

# --- Message Editing Web App Routes ---

def validate_init_data(init_data_str, bot_token):
    """Validates the initData string from Telegram Web App."""
    try:
        parsed_data = parse_qs(init_data_str)
        received_hash = parsed_data.pop('hash', [None])[0]
        if not received_hash:
            raise ValueError(s.VALIDATE_INIT_DATA_HASH_NOT_FOUND)

        data_check_string = "\n".join(sorted([f"{k}={v[0]}" for k, v in parsed_data.items()]))
        secret_key = hmac.new("WebAppData".encode(), bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if received_hash != calculated_hash:
            raise ValueError(s.VALIDATE_INIT_DATA_INVALID_HASH)

        user_data = json.loads(parsed_data['user'][0])
        user_id = user_data.get('id')
        if not user_id:
            raise ValueError(s.VALIDATE_INIT_DATA_USER_ID_NOT_FOUND)

        return user_id, user_data # Return user_id and parsed user data
    except Exception as e:
        logger.error(f"initData validation failed: {e}", exc_info=True)
        return None, None # Return None if validation fails

@app.route('/webapp/edit_messages')
def webapp_edit_messages():
    """Serve the HTML page for the message editing web app."""
    logger.info(s.LOG_SERVING_EDIT_MESSAGES_HTML)
    # Validation happens on data fetch/save, not here
    # Pass the strings object 's' to the template context
    return render_template('edit_messages.html', s=s)

@app.route('/webapp/get_messages', methods=['POST'])
def webapp_get_messages():
    """Provide user messages (with non-null text) to the web app after validating initData."""
    logger.info(s.LOG_WEBAPP_GET_MESSAGES_REQUEST)
    try:
        init_data_str = request.headers.get('X-Telegram-Init-Data')
        if not init_data_str:
            logger.warning(s.WARN_WEBAPP_MISSING_INIT_DATA.format(route='get_messages'))
            return jsonify({'error': s.ERROR_WEBAPP_AUTH_REQUIRED}), 401

        # !!! IMPORTANT: Ensure validate_init_data function is defined and imported correctly !!!
        user_id, _ = validate_init_data(init_data_str, config.TOKEN)
        # Placeholder check - replace with actual validation
        # try:
        #     # from urllib.parse import parse_qs # Already imported at top
        #     import hmac
        #     import hashlib
        #     data_check_string = "\n".join(sorted([f"{k}={v[0]}" for k, v in parse_qs(init_data_str).items() if k != 'hash']))
        #     secret_key = hmac.new("WebAppData".encode(), config.TOKEN.encode(), hashlib.sha256).digest()
        #     calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        #     init_data_dict = parse_qs(init_data_str)
        #     if init_data_dict.get('hash', [''])[0] != calculated_hash:
        #          raise ValueError("Invalid hash")
        #     user_data = json.loads(init_data_dict['user'][0])
        #     user_id = user_data.get('id')
        #     if not user_id:
        #          raise ValueError("User ID not found in initData")
        # except Exception as validation_e:
        #      logger.error(f"initData validation failed: {validation_e}", exc_info=True)
        #      user_id = None # Ensure user_id is None if validation fails

        if not user_id:
            logger.warning(s.ERROR_WEBAPP_INVALID_AUTH_DATA)
            return jsonify({'error': s.ERROR_WEBAPP_INVALID_AUTH_DATA}), 403

        logger.info(s.LOG_WEBAPP_FETCHING_MESSAGES.format(user_id=user_id))
        # Fetch recent messages with non-null/non-empty message_text
        messages = db.get_db_user_messages(user_id, limit=20) # Use DB function
        # Filter further if needed (e.g., exclude specific types)
        text_messages = [m for m in messages if m.get('message_text')]
        logger.info(s.LOG_WEBAPP_FETCHED_MESSAGES.format(count=len(text_messages), user_id=user_id))
        return jsonify(text_messages)

    except Exception as e:
        logger.error(s.ERROR_WEBAPP_FETCHING_MESSAGES.format(error=e), exc_info=True)
        return jsonify({'error': s.ERROR_WEBAPP_INTERNAL_SERVER}), 500

@app.route('/webapp/save_messages', methods=['POST'])
def webapp_save_messages():
    """Receive updated message data from the web app, validate, and save."""
    logger.info(s.LOG_WEBAPP_SAVE_MESSAGES_REQUEST)
    try:
        init_data_str = request.headers.get('X-Telegram-Init-Data')
        if not init_data_str:
             logger.warning(s.WARN_WEBAPP_MISSING_INIT_DATA.format(route='save_messages'))
             return jsonify({'error': s.ERROR_WEBAPP_AUTH_REQUIRED}), 401

        # !!! IMPORTANT: Ensure validate_init_data function is defined and imported correctly !!!
        user_id, _ = validate_init_data(init_data_str, config.TOKEN)
        # Placeholder check - replace with actual validation
        # try:
        #     # from urllib.parse import parse_qs # Already imported at top
        #     import hmac
        #     import hashlib
        #     data_check_string = "\n".join(sorted([f"{k}={v[0]}" for k, v in parse_qs(init_data_str).items() if k != 'hash']))
        #     secret_key = hmac.new("WebAppData".encode(), config.TOKEN.encode(), hashlib.sha256).digest()
        #     calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        #     init_data_dict = parse_qs(init_data_str)
        #     if init_data_dict.get('hash', [''])[0] != calculated_hash:
        #          raise ValueError("Invalid hash")
        #     user_data = json.loads(init_data_dict['user'][0])
        #     user_id = user_data.get('id')
        #     if not user_id:
        #          raise ValueError("User ID not found in initData")
        # except Exception as validation_e:
        #      logger.error(f"initData validation failed: {validation_e}", exc_info=True)
        #      user_id = None # Ensure user_id is None if validation fails

        if not user_id:
             logger.warning(s.ERROR_WEBAPP_INVALID_AUTH_DATA)
             return jsonify({'error': s.ERROR_WEBAPP_INVALID_AUTH_DATA}), 403

        logger.info(s.LOG_WEBAPP_PROCESSING_SAVE.format(user_id=user_id))
        data = request.json # Expecting a list of objects: [{'id': db_id, 'text': new_text}, ...]
        if not data or not isinstance(data, list):
            logger.warning(s.WARN_WEBAPP_INVALID_SAVE_DATA.format(user_id=user_id))
            return jsonify({'error': s.ERROR_WEBAPP_INVALID_DATA_FORMAT}), 400

        # --- Update Database ---
        conn = db.sqlite3.connect(db.DB_PATH) # Use db module's sqlite3 and path
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


# Health check endpoint to verify the bot is working correctly
@app.route('/health')
def health_check():
    db_status = 'unknown'
    user_count, message_count, interaction_count = -1, -1, -1
    try:
        conn = db.sqlite3.connect(db.DB_PATH)
        cursor = conn.cursor()
        # Get counts
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM user_messages")
        message_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM user_interactions")
        interaction_count = cursor.fetchone()[0]
        conn.close()
        db_status = s.DB_STATUS_OK
    except Exception as db_e:
        logger.error(s.HEALTH_CHECK_DB_ERROR.format(error=db_e))
        db_status = s.DB_STATUS_ERROR

    service_account_status = s.DB_STATUS_OK if (config.SERVICE_ACCOUNT_FILE and os.path.exists(config.SERVICE_ACCOUNT_FILE)) else s.DB_STATUS_MISSING

    try:
        bot_info_dict = bot.get_me().to_dict()
    except Exception as bot_e:
        logger.error(s.HEALTH_CHECK_BOT_ERROR.format(error=bot_e))
        bot_info_dict = {'error': str(bot_e)}

    return jsonify({
        'status': s.DB_STATUS_OK if db_status == s.DB_STATUS_OK else s.DB_STATUS_ERROR,
        'timestamp': datetime.now().isoformat(),
        'bot_info': bot_info_dict,
        'db_status': db_status,
        'service_account_status': service_account_status,
        'active_users_in_memory': len(user_sessions),
        'total_users_in_db': user_count,
        'total_messages_in_db': message_count,
        'total_interactions_in_db': interaction_count
    })
