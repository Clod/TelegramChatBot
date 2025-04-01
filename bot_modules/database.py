import sqlite3
import json
import logging
import re
import os
from . import config
from . import strings_en
from . import strings_es

# Set language based on environment
BOT_LANGUAGE = os.getenv('BOT_LANGUAGE', 'english').lower()
s = strings_es if BOT_LANGUAGE == 'spanish' else strings_en

logger = logging.getLogger(__name__)

# Database setup
DB_PATH = config.DB_PATH

def init_db():
    """Initialize the SQLite database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT,
        language_code TEXT, is_bot BOOLEAN, chat_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    # Create user_interactions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action_type TEXT, action_data TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users (user_id)
    )''')
    # Create user_preferences table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_preferences (
        user_id INTEGER PRIMARY KEY, language TEXT DEFAULT 'en', notifications BOOLEAN DEFAULT 1,
        theme TEXT DEFAULT 'default', last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )''')
    # Create user_messages table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, chat_id INTEGER, message_id INTEGER,
        message_text TEXT, message_type TEXT, has_media BOOLEAN DEFAULT 0, media_type TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users (user_id)
    )''')
    # Create image_processing_results table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS image_processing_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, message_id INTEGER, file_id TEXT,
        gemini_response TEXT, processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )''')
    conn.commit()
    conn.close()
    logger.info(s.LOG_DB_INIT_SUCCESS)

def save_user(user, chat_id=None):
    """Save or update user information in the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user.id,))
    exists = cursor.fetchone()
    if exists:
        if chat_id:
            cursor.execute("""
            UPDATE users SET username = ?, first_name = ?, last_name = ?, language_code = ?,
                chat_id = ?, last_activity = CURRENT_TIMESTAMP WHERE user_id = ?
            """, (user.username, user.first_name, user.last_name, user.language_code, chat_id, user.id))
        else:
            cursor.execute("""
            UPDATE users SET username = ?, first_name = ?, last_name = ?, language_code = ?,
                last_activity = CURRENT_TIMESTAMP WHERE user_id = ?
            """, (user.username, user.first_name, user.last_name, user.language_code, user.id))
    else:
        cursor.execute("""
        INSERT INTO users (user_id, username, first_name, last_name, language_code, is_bot, chat_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user.id, user.username, user.first_name, user.last_name, user.language_code, user.is_bot, chat_id))
        cursor.execute("INSERT INTO user_preferences (user_id) VALUES (?)", (user.id,))
    conn.commit()
    conn.close()

def log_interaction(user_id, action_type, action_data=None):
    """Log user interaction in the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    action_data_str = None
    if action_data is not None:
        if isinstance(action_data, str):
            action_data_str = action_data
        else:
            try:
                action_data_str = json.dumps(action_data)
            except Exception as e:
                logger.error(f"Error converting action_data to JSON for user {user_id}, action {action_type}: {e}")
                action_data_str = str(action_data)
    cursor.execute("INSERT INTO user_interactions (user_id, action_type, action_data) VALUES (?, ?, ?)",
                   (user_id, action_type, action_data_str))
    conn.commit()
    conn.close()

def save_message(message, message_type_override=None, text_override=None):
    """Save a user message to the database, allowing overrides for type and text."""
    user_id = message.from_user.id
    chat_id = message.chat.id # Add this line back
    message_id = message.message_id

    # Determine final message type and text
    original_content_type = message.content_type
    final_message_type = message_type_override if message_type_override else original_content_type

    if text_override is not None:
        final_message_text = text_override
        # If text is overridden, it's not media, even if original was photo etc.
        has_media = False
        media_type = None
        # Ensure the final_message_type reflects it's text-based if overridden
        if final_message_type == s.DB_MESSAGE_TYPE_PHOTO: # Example: if original was photo but we save text
             final_message_type = message_type_override or s.DB_MESSAGE_TYPE_TEXT # Use override or default text
    elif original_content_type == s.DB_MESSAGE_TYPE_TEXT:
        final_message_text = message.text
        has_media = False
        media_type = None
    else: # Original message was media and no text override
        final_message_text = None
        has_media = True
        media_type = original_content_type

    # File ID logic remains the same (based on original content type)
    file_id = None
    if original_content_type == s.DB_MESSAGE_TYPE_PHOTO and message.photo:
        file_id = message.photo[-1].file_id # Note: file_id is not currently saved in the schema

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO user_messages (user_id, chat_id, message_id, message_text, message_type, has_media, media_type)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, chat_id, message_id, final_message_text, final_message_type, has_media, media_type))
    conn.commit()
    conn.close()

    # Adjust logging based on final content
    if final_message_text:
        logger.info(s.LOG_DB_SAVED_MESSAGE.format(user_id=user_id, text_preview=final_message_text[:50]))
    else:
        # Log the original type if it was media and not overridden, otherwise log the final type
        log_type = original_content_type if has_media and text_override is None else final_message_type
        logger.info(s.LOG_DB_SAVED_MEDIA_MESSAGE.format(message_type=log_type, user_id=user_id))


def save_processed_text(user_id, chat_id, original_message_id, text_to_save, message_type):
    """Saves processed text (like from Gemini, Forms, Sheets) to the user_messages table."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO user_messages (user_id, chat_id, message_id, message_text, message_type, has_media, media_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, chat_id, original_message_id, text_to_save, message_type, False, None))
        conn.commit()
        conn.close()
        logger.info(s.LOG_DB_SAVED_PROCESSED_TEXT.format(message_type=message_type, user_id=user_id, original_message_id=original_message_id))
    except Exception as db_err:
        logger.error(s.ERROR_DB_SAVING_PROCESSED_TEXT.format(message_type=message_type, user_id=user_id, db_err=db_err), exc_info=True)


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
        return {'user_id': user_id, 'language': s.DB_DEFAULT_LANGUAGE, 'notifications': True, 'theme': s.DB_DEFAULT_THEME}

def update_user_preference(user_id, preference_name, preference_value):
    """Update a specific user preference"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM user_preferences WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone()
    if exists:
        cursor.execute(f"UPDATE user_preferences SET {preference_name} = ?, last_updated = CURRENT_TIMESTAMP WHERE user_id = ?",
                       (preference_value, user_id))
    else:
        defaults = {'language': 'en', 'notifications': True, 'theme': 'default'}
        defaults[preference_name] = preference_value
        cursor.execute("INSERT INTO user_preferences (user_id, language, notifications, theme) VALUES (?, ?, ?, ?)",
                       (user_id, defaults['language'], defaults['notifications'], defaults['theme']))
    conn.commit()
    conn.close()
    return True

def get_user_data_summary(user_id):
    """Get a summary of all data stored for a user"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    summary = {}
    cursor.execute("""
    SELECT u.*, p.language, p.notifications, p.theme FROM users u
    LEFT JOIN user_preferences p ON u.user_id = p.user_id WHERE u.user_id = ?
    """, (user_id,))
    user = cursor.fetchone()
    if user:
        summary['profile'] = dict(user)
        cursor.execute("SELECT COUNT(*) as count FROM user_messages WHERE user_id = ?", (user_id,))
        message_count = cursor.fetchone()
        summary['message_count'] = message_count['count'] if message_count else 0
        cursor.execute("SELECT COUNT(*) as count FROM user_interactions WHERE user_id = ?", (user_id,))
        interaction_count = cursor.fetchone()
        summary['interaction_count'] = interaction_count['count'] if interaction_count else 0
        cursor.execute("SELECT action_type, COUNT(*) as count FROM user_interactions WHERE user_id = ? GROUP BY action_type ORDER BY count DESC", (user_id,))
        summary['interaction_types'] = [dict(row) for row in cursor.fetchall()]
        cursor.execute("SELECT message_text, timestamp FROM user_messages WHERE user_id = ? ORDER BY timestamp DESC LIMIT 20", (user_id,))
        summary['recent_messages'] = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return summary

def delete_user_data(user_id):
    """Delete all data associated with a user from the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    messages_deleted, interactions_deleted = 0, 0
    try:
        cursor.execute("BEGIN TRANSACTION")
        cursor.execute("DELETE FROM image_processing_results WHERE user_id = ?", (user_id,)) # Also delete image results
        cursor.execute("DELETE FROM user_messages WHERE user_id = ?", (user_id,))
        messages_deleted = cursor.rowcount
        cursor.execute("DELETE FROM user_interactions WHERE user_id = ?", (user_id,))
        interactions_deleted = cursor.rowcount
        cursor.execute("DELETE FROM user_preferences WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()
        logger.info(s.LOG_DB_DELETED_USER_DATA.format(user_id=user_id, messages_deleted=messages_deleted, interactions_deleted=interactions_deleted))
        return True, messages_deleted, interactions_deleted
    except Exception as e:
        conn.rollback()
        logger.error(s.ERROR_DB_DELETING_USER_DATA.format(error=str(e)))
        return False, 0, 0
    finally:
        conn.close()

def get_user_message_history(user_id, include_text=False, limit=20):
    """Get the message history for a specific user"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if include_text:   
        cursor.execute("""
        SELECT message_text, timestamp FROM user_messages
        WHERE user_id = ? AND message_text IS NOT NULL AND message_text != '' AND message_text != '/start'
        AND (message_type = ? OR message_type = ? OR message_type = ? OR message_type = ? OR message_type = ?) -- Added data_entry type
        ORDER BY timestamp DESC LIMIT ?
        """, (user_id, s.DB_MESSAGE_TYPE_TEXT, s.DB_MESSAGE_TYPE_PROCESSED_IMAGE, s.DB_MESSAGE_TYPE_RETRIEVED_SHEET, s.DB_MESSAGE_TYPE_RETRIEVED_FORM, s.DB_MESSAGE_TYPE_DATA_ENTRY, limit)) # Added data_entry constant
    else:
        cursor.execute("""
        SELECT message_text, timestamp FROM user_messages
        WHERE user_id = ? AND message_text IS NOT NULL AND message_text != '' AND message_text != '/start'
        AND (message_type = ? OR message_type = ? OR message_type = ? OR message_type = ?) -- Added data_entry type
        ORDER BY timestamp DESC LIMIT ?
        """, (user_id, s.DB_MESSAGE_TYPE_PROCESSED_IMAGE, s.DB_MESSAGE_TYPE_RETRIEVED_SHEET, s.DB_MESSAGE_TYPE_RETRIEVED_FORM, s.DB_MESSAGE_TYPE_DATA_ENTRY, limit)) # Added data_entry constant
 
    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()
    logger.info(s.LOG_DB_RETRIEVED_HISTORY.format(count=len(messages), user_id=user_id))
    return messages

def save_image_processing_result(user_id, message_id, file_id, gemini_response_json):
    """Save the Gemini API response (as JSON string) to the database"""
    logger.info(s.LOG_DB_INITIATING_IMAGE_RESULT_STORAGE.format(user_id=user_id, message_id=message_id))
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO image_processing_results (user_id, message_id, file_id, gemini_response)
        VALUES (?, ?, ?, ?)
        """, (user_id, message_id, file_id, gemini_response_json))
        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        logger.info(s.LOG_DB_IMAGE_RESULT_STORED.format(record_id=record_id))
        return True
    except Exception as e:
        logger.error(s.ERROR_DB_SAVING_IMAGE_RESULT.format(error=str(e)), exc_info=True)
        return False

def find_form_response_id(user_id, search_limit=20):
    """Search recent user messages for the form=ID pattern."""
    logger.info(s.LOG_DB_SEARCHING_FORM_ID.format(search_limit=search_limit, user_id=user_id))
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT message_text FROM user_messages
        WHERE user_id = ? AND message_text IS NOT NULL ORDER BY timestamp DESC LIMIT ?
    """, (user_id, search_limit))
    response_id = None
    pattern = re.compile(r"form=(\d+)", re.IGNORECASE)
    for row in cursor.fetchall():
        message_text = row[0]
        match = pattern.search(message_text)
        if match:
            response_id = match.group(1)
            logger.info(s.LOG_DB_FOUND_FORM_ID.format(response_id=response_id, message_text=message_text))
            break
    conn.close()
    if not response_id:
        logger.warning(s.WARN_DB_FORM_ID_NOT_FOUND.format(user_id=user_id))
    return response_id

# --- Functions for viewing data via Flask routes ---
def get_all_db_users():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
    SELECT u.user_id, u.username, u.first_name, u.last_name, u.chat_id, u.created_at, u.last_activity,
           p.language, p.notifications, p.theme,
           (SELECT COUNT(*) FROM user_interactions WHERE user_id = u.user_id) as interaction_count
    FROM users u LEFT JOIN user_preferences p ON u.user_id = p.user_id ORDER BY u.last_activity DESC
    """)
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users

def get_db_user_details(user_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
    SELECT u.*, p.language, p.notifications, p.theme FROM users u
    LEFT JOIN user_preferences p ON u.user_id = p.user_id WHERE u.user_id = ?
    """, (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def get_db_image_processing_results(user_id, limit=50):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, message_id, file_id, processed_at FROM image_processing_results
    WHERE user_id = ? ORDER BY processed_at DESC LIMIT ?
    """, (user_id, limit))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

def get_db_user_messages(user_id, limit=100):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_messages WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?", (user_id, limit))
    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return messages

def get_db_user_interactions(user_id, limit=100):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_interactions WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?", (user_id, limit))
    interactions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return interactions

def get_db_interaction_stats(user_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
    SELECT action_type, COUNT(*) as count FROM user_interactions
    WHERE user_id = ? GROUP BY action_type ORDER BY count DESC
    """, (user_id,))
    stats = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return stats
