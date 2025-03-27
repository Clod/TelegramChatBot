import unittest
import os
import json
import sqlite3
import tempfile
import base64
from unittest.mock import patch, MagicMock, mock_open
from io import BytesIO
from datetime import datetime

# Import the app module
from . import app

import sys                                                                                                                                                                                                  
print(sys.path)   

import sys                                                                                                                                                                                                  
import os                                                                                                                                                                                                   
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))                                                                                                                                              
                                                                       
      
class AppRegressionTest(unittest.TestCase):
    """Comprehensive regression tests for the Telegram bot application"""

    def setUp(self):
        """Set up test environment before each test"""
        # Create a temporary database file
        self.temp_db_fd, app.DB_PATH = tempfile.mkstemp()
        
        # Initialize the database
        app.init_db()
        
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'TELEGRAM_BOT_TOKEN': 'test_token',
            'DEBUG_MODE': 'False',
            'GOOGLE_APPLICATION_CREDENTIALS': 'test_credentials.json',
            'GEMINI_API_ENDPOINT': 'https://test-endpoint.com'
        })
        self.env_patcher.start()
        
        # Mock the bot
        self.bot_patcher = patch('app.bot')
        self.mock_bot = self.bot_patcher.start()
        
        # Create a test user
        self.test_user = MagicMock()
        self.test_user.id = 12345
        self.test_user.username = 'test_user'
        self.test_user.first_name = 'Test'
        self.test_user.last_name = 'User'
        self.test_user.language_code = 'en'
        self.test_user.is_bot = False
        
        # Create a test message
        self.test_message = MagicMock()
        self.test_message.from_user = self.test_user
        self.test_message.chat.id = 12345
        self.test_message.message_id = 67890
        self.test_message.text = 'Test message'
        self.test_message.content_type = 'text'
        
        # Create a test photo message
        self.test_photo_message = MagicMock()
        self.test_photo_message.from_user = self.test_user
        self.test_photo_message.chat.id = 12345
        self.test_photo_message.message_id = 67891
        self.test_photo_message.content_type = 'photo'
        self.test_photo_message.photo = [MagicMock(file_id='test_file_id')]
        self.test_photo_message.text = None

    def tearDown(self):
        """Clean up after each test"""
        # Close and remove the temporary database
        os.close(self.temp_db_fd)
        os.unlink(app.DB_PATH)
        
        # Stop all patches
        self.env_patcher.stop()
        self.bot_patcher.stop()

    def test_init_db(self):
        """Test database initialization"""
        # Re-initialize the database
        app.init_db()
        
        # Connect to the database and check if tables exist
        conn = sqlite3.connect(app.DB_PATH)
        cursor = conn.cursor()
        
        # Check users table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        self.assertIsNotNone(cursor.fetchone())
        
        # Check user_interactions table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_interactions'")
        self.assertIsNotNone(cursor.fetchone())
        
        # Check user_preferences table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'")
        self.assertIsNotNone(cursor.fetchone())
        
        # Check user_messages table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_messages'")
        self.assertIsNotNone(cursor.fetchone())
        
        # Check image_processing_results table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='image_processing_results'")
        self.assertIsNotNone(cursor.fetchone())
        
        conn.close()

    def test_save_user(self):
        """Test saving user information to the database"""
        # Save the test user
        app.save_user(self.test_user, self.test_message.chat.id)
        
        # Check if the user was saved
        conn = sqlite3.connect(app.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (self.test_user.id,))
        user = cursor.fetchone()
        conn.close()
        
        # Assert user data was saved correctly
        self.assertIsNotNone(user)
        self.assertEqual(user[0], self.test_user.id)  # user_id
        self.assertEqual(user[1], self.test_user.username)  # username
        self.assertEqual(user[2], self.test_user.first_name)  # first_name
        self.assertEqual(user[3], self.test_user.last_name)  # last_name
        self.assertEqual(user[4], self.test_user.language_code)  # language_code
        self.assertEqual(user[5], self.test_user.is_bot)  # is_bot
        self.assertEqual(user[6], self.test_message.chat.id)  # chat_id

    def test_log_interaction(self):
        """Test logging user interactions"""
        # Log an interaction
        app.log_interaction(self.test_user.id, "test_action", "test_data")
        
        # Check if the interaction was logged
        conn = sqlite3.connect(app.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_interactions WHERE user_id = ?", (self.test_user.id,))
        interaction = cursor.fetchone()
        conn.close()
        
        # Assert interaction was logged correctly
        self.assertIsNotNone(interaction)
        self.assertEqual(interaction[1], self.test_user.id)  # user_id
        self.assertEqual(interaction[2], "test_action")  # action_type
        self.assertEqual(interaction[3], "test_data")  # action_data

    def test_save_message(self):
        """Test saving user messages"""
        # Save a message
        app.save_message(self.test_message)
        
        # Check if the message was saved
        conn = sqlite3.connect(app.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_messages WHERE user_id = ?", (self.test_user.id,))
        message = cursor.fetchone()
        conn.close()
        
        # Assert message was saved correctly
        self.assertIsNotNone(message)
        self.assertEqual(message[1], self.test_user.id)  # user_id
        self.assertEqual(message[2], self.test_message.chat.id)  # chat_id
        self.assertEqual(message[3], self.test_message.message_id)  # message_id
        self.assertEqual(message[4], self.test_message.text)  # message_text
        self.assertEqual(message[5], self.test_message.content_type)  # message_type
        self.assertEqual(message[6], 0)  # has_media (0 for text messages)

    def test_get_user_preferences(self):
        """Test getting user preferences"""
        # First save the user to create default preferences
        app.save_user(self.test_user, self.test_message.chat.id)
        
        # Get user preferences
        prefs = app.get_user_preferences(self.test_user.id)
        
        # Assert default preferences are returned
        self.assertEqual(prefs['user_id'], self.test_user.id)
        self.assertEqual(prefs['language'], 'en')
        self.assertTrue(prefs['notifications'])
        self.assertEqual(prefs['theme'], 'default')

    def test_update_user_preference(self):
        """Test updating user preferences"""
        # First save the user to create default preferences
        app.save_user(self.test_user, self.test_message.chat.id)
        
        # Update a preference
        app.update_user_preference(self.test_user.id, 'language', 'es')
        
        # Get updated preferences
        prefs = app.get_user_preferences(self.test_user.id)
        
        # Assert preference was updated
        self.assertEqual(prefs['language'], 'es')

    def test_get_user_data_summary(self):
        """Test getting user data summary"""
        # First save the user and some data
        app.save_user(self.test_user, self.test_message.chat.id)
        app.save_message(self.test_message)
        app.log_interaction(self.test_user.id, "test_action", "test_data")
        
        # Get user data summary
        summary = app.get_user_data_summary(self.test_user.id)
        
        # Assert summary contains expected data
        self.assertIn('profile', summary)
        self.assertEqual(summary['profile']['user_id'], self.test_user.id)
        self.assertEqual(summary['message_count'], 1)
        self.assertEqual(summary['interaction_count'], 1)

    def test_delete_user_data(self):
        """Test deleting user data"""
        # First save the user and some data
        app.save_user(self.test_user, self.test_message.chat.id)
        app.save_message(self.test_message)
        app.log_interaction(self.test_user.id, "test_action", "test_data")
        
        # Delete user data
        success, messages_deleted, interactions_deleted = app.delete_user_data(self.test_user.id)
        
        # Assert deletion was successful
        self.assertTrue(success)
        self.assertEqual(messages_deleted, 1)
        self.assertEqual(interactions_deleted, 1)
        
        # Check if user data is gone
        conn = sqlite3.connect(app.DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (self.test_user.id,))
        self.assertIsNone(cursor.fetchone())
        
        cursor.execute("SELECT * FROM user_messages WHERE user_id = ?", (self.test_user.id,))
        self.assertIsNone(cursor.fetchone())
        
        cursor.execute("SELECT * FROM user_interactions WHERE user_id = ?", (self.test_user.id,))
        self.assertIsNone(cursor.fetchone())
        
        conn.close()

    def test_generate_main_menu(self):
        """Test generating the main menu"""
        # Get the main menu
        menu = app.generate_main_menu()
        
        # Assert menu is created correctly
        self.assertIsNotNone(menu)
        # Check that it's an InlineKeyboardMarkup
        self.assertEqual(menu.__class__.__name__, 'InlineKeyboardMarkup')

    def test_generate_submenu(self):
        """Test generating a submenu"""
        # Get a submenu
        submenu = app.generate_submenu("menu1")
        
        # Assert submenu is created correctly
        self.assertIsNotNone(submenu)
        # Check that it's an InlineKeyboardMarkup
        self.assertEqual(submenu.__class__.__name__, 'InlineKeyboardMarkup')

    @patch('app.bot.reply_to')
    def test_send_welcome(self, mock_reply_to):
        """Test the welcome message handler"""
        # Call the welcome handler
        app.send_welcome(self.test_message)
        
        # Assert bot.reply_to was called
        mock_reply_to.assert_called_once()
        
        # Check if user was saved
        conn = sqlite3.connect(app.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (self.test_user.id,))
        user = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(user)

    def test_get_user_message_history(self):
        """Test getting user message history"""
        # Save some messages
        app.save_message(self.test_message)
        
        # Get message history
        history = app.get_user_message_history(self.test_user.id)
        
        # Assert history contains the message
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['message_text'], self.test_message.text)

    @patch('app.bot.get_file')
    @patch('app.bot.download_file')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.getsize')
    def test_download_image_from_telegram(self, mock_getsize, mock_file, mock_download_file, mock_get_file):
        """Test downloading an image from Telegram"""
        # Mock file info
        file_info = MagicMock()
        file_info.file_path = 'test/path/to/file.jpg'
        mock_get_file.return_value = file_info
        
        # Mock download file
        mock_download_file.return_value = b'test image data'
        
        # Mock file size
        mock_getsize.return_value = 1024
        
        # Download image
        file_path = app.download_image_from_telegram('test_file_id', self.test_user.id, self.test_message.message_id)
        
        # Assert file was downloaded
        self.assertIsNotNone(file_path)
        mock_get_file.assert_called_once_with('test_file_id')
        mock_download_file.assert_called_once_with('test/path/to/file.jpg')
        mock_file.assert_called()

    @patch('app.get_credentials')
    @patch('requests.post')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test image data')
    def test_process_image_with_gemini(self, mock_file, mock_post, mock_get_credentials):
        """Test processing an image with Gemini API"""
        # Mock credentials
        mock_credentials = MagicMock()
        mock_credentials.token = 'test_token'
        mock_get_credentials.return_value = mock_credentials
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"candidates": [{"content": {"parts": [{"text": "full_name=Test User|date_of_birth=1/1/2000|age=24|email=test@example.com|phone_number=1234567890|city=Test City|state=Test State|gender=Male|preferred_contact_method=Email"}]}}]}'
        mock_response.json.return_value = json.loads(mock_response.text)
        mock_post.return_value = mock_response
        
        # Process image
        response = app.process_image_with_gemini('test_image.jpg', self.test_user.id)
        
        # Assert image was processed
        self.assertIsNotNone(response)
        mock_get_credentials.assert_called_once()
        mock_post.assert_called_once()
        mock_file.assert_called_once_with('test_image.jpg', 'rb')

    def test_save_image_processing_result(self):
        """Test saving image processing results"""
        # Mock Gemini response
        gemini_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "full_name=Test User|date_of_birth=1/1/2000|age=24|email=test@example.com|phone_number=1234567890|city=Test City|state=Test State|gender=Male|preferred_contact_method=Email"
                            }
                        ]
                    }
                }
            ]
        }
        
        # Save result
        success = app.save_image_processing_result(
            self.test_user.id, 
            self.test_message.message_id, 
            'test_file_id', 
            gemini_response
        )
        
        # Assert result was saved
        self.assertTrue(success)
        
        # Check database
        conn = sqlite3.connect(app.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM image_processing_results WHERE user_id = ?", (self.test_user.id,))
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(result)
        self.assertEqual(result[1], self.test_user.id)  # user_id
        self.assertEqual(result[2], self.test_message.message_id)  # message_id
        self.assertEqual(result[3], 'test_file_id')  # file_id

    def test_extract_text_from_gemini_response(self):
        """Test extracting text from Gemini API response"""
        # Test with dictionary response
        response_dict = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "full_name=Test User|date_of_birth=1/1/2000|age=24|email=test@example.com|phone_number=1234567890|city=Test City|state=Test State|gender=Male|preferred_contact_method=Email"
                            }
                        ]
                    }
                }
            ]
        }
        
        text = app.extract_text_from_gemini_response(response_dict)
        
        # Assert text was extracted correctly
        self.assertIn("full_name=Test User", text)
        self.assertIn("email=test@example.com", text)
        
        # Test with JSON string response
        response_str = json.dumps(response_dict)
        text = app.extract_text_from_gemini_response(response_str)
        
        # Assert text was extracted correctly
        self.assertIn("full_name=Test User", text)
        self.assertIn("email=test@example.com", text)

    @patch('os.path.exists')
    @patch('os.remove')
    def test_cleanup_temp_file(self, mock_remove, mock_exists):
        """Test cleaning up temporary files"""
        # Mock file exists
        mock_exists.return_value = True
        
        # Clean up file
        success = app.cleanup_temp_file('test_file.jpg')
        
        # Assert file was cleaned up
        self.assertTrue(success)
        mock_exists.assert_called_once_with('test_file.jpg')
        mock_remove.assert_called_once_with('test_file.jpg')

    @patch('app.bot.reply_to')
    @patch('app.get_user_message_history')
    def test_handle_text(self, mock_get_history, mock_reply_to):
        """Test handling text messages"""
        # Mock message history
        mock_get_history.return_value = [
            {
                'message_text': 'Test message',
                'timestamp': datetime.now().isoformat()
            }
        ]
        
        # Handle text message
        app.handle_text(self.test_message)
        
        # Assert message was handled
        mock_get_history.assert_called_once_with(self.test_user.id, limit=10)
        mock_reply_to.assert_called_once()
        
        # Check if message was saved
        conn = sqlite3.connect(app.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_messages WHERE user_id = ?", (self.test_user.id,))
        message = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(message)

    @patch('app.bot.edit_message_text')
    def test_handle_callback_query_main_menu(self, mock_edit_message):
        """Test handling callback queries for main menu"""
        # Create a mock callback query
        call = MagicMock()
        call.from_user = self.test_user
        call.message.chat.id = self.test_message.chat.id
        call.data = 'main_menu'
        
        # Handle callback query
        app.handle_callback_query(call)
        
        # Assert callback was handled
        mock_edit_message.assert_called_once()
        
        # Check if interaction was logged
        conn = sqlite3.connect(app.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_interactions WHERE user_id = ? AND action_type = ?", 
                      (self.test_user.id, 'button_click'))
        interaction = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(interaction)
        self.assertEqual(interaction[3], 'main_menu')  # action_data

    @patch('app.bot.edit_message_text')
    def test_handle_callback_query_view_data(self, mock_edit_message):
        """Test handling callback queries for viewing data"""
        # First save some user data
        app.save_user(self.test_user, self.test_message.chat.id)
        app.save_message(self.test_message)
        
        # Create a mock callback query
        call = MagicMock()
        call.from_user = self.test_user
        call.message.chat.id = self.test_message.chat.id
        call.data = 'view_my_data'
        
        # Handle callback query
        app.handle_callback_query(call)
        
        # Assert callback was handled
        mock_edit_message.assert_called_once()

    @patch('app.bot.edit_message_text')
    def test_handle_callback_query_delete_data(self, mock_edit_message):
        """Test handling callback queries for deleting data"""
        # Create a mock callback query
        call = MagicMock()
        call.from_user = self.test_user
        call.message.chat.id = self.test_message.chat.id
        call.data = 'delete_my_data'
        
        # Handle callback query
        app.handle_callback_query(call)
        
        # Assert callback was handled
        mock_edit_message.assert_called_once()

    @patch('app.bot.edit_message_text')
    def test_handle_callback_query_confirm_delete(self, mock_edit_message):
        """Test handling callback queries for confirming data deletion"""
        # First save some user data
        app.save_user(self.test_user, self.test_message.chat.id)
        app.save_message(self.test_message)
        
        # Create a mock callback query
        call = MagicMock()
        call.from_user = self.test_user
        call.message.chat.id = self.test_message.chat.id
        call.data = 'confirm_delete'
        
        # Handle callback query
        app.handle_callback_query(call)
        
        # Assert callback was handled
        mock_edit_message.assert_called_once()
        
        # Check if user data was deleted
        conn = sqlite3.connect(app.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (self.test_user.id,))
        user = cursor.fetchone()
        conn.close()
        
        self.assertIsNone(user)

    def test_webhook(self):
        """Test the webhook endpoint"""
        # Create a Flask test client
        client = app.app.test_client()
        
        # Create test data
        update_data = b'{"update_id": 123456789, "message": {"message_id": 67890, "from": {"id": 12345, "is_bot": false, "first_name": "Test", "last_name": "User", "username": "test_user", "language_code": "en"}, "chat": {"id": 12345, "first_name": "Test", "last_name": "User", "username": "test_user", "type": "private"}, "date": 1617123456, "text": "Test message"}}'
        
        # Mock bot.process_new_updates
        original_process_updates = app.bot.process_new_updates
        app.bot.process_new_updates = MagicMock()
        
        try:
            # Send a POST request to the webhook endpoint
            response = client.post(f'/{app.TOKEN}', data=update_data)
            print(f"Response status code: {response.status_code}")
            print(f"Response data: {response.data}")  # Print the response body
            # Assert response status code
            self.assertEqual(response.status_code, 200)
            
            # Assert bot.process_new_updates was called
            app.bot.process_new_updates.assert_called_once()
        finally:
            # Restore the original method
            app.bot.process_new_updates = original_process_updates

    def test_index(self):
        """Test the index endpoint"""
        # Call index
        response = app.index()
        
        # Assert response
        self.assertEqual(response, 'Bot is running!')

    @patch('app.bot.remove_webhook')
    @patch('app.bot.set_webhook')
    def test_set_webhook(self, mock_set_webhook, mock_remove_webhook):
        """Test setting the webhook"""
        # Call set_webhook
        response = app.set_webhook()
        
        # Assert webhook was set
        self.assertEqual(response, 'Webhook set!')
        mock_remove_webhook.assert_called_once()
        mock_set_webhook.assert_called_once_with(url=app.WEBHOOK_URL)

    @patch('app.bot.get_webhook_info')
    @patch('app.jsonify')
    def test_webhook_info(self, mock_jsonify, mock_get_webhook_info):
        """Test getting webhook info"""
        # Mock webhook info
        webhook_info = MagicMock()
        webhook_info.url = 'https://example.com/webhook'
        webhook_info.has_custom_certificate = False
        webhook_info.pending_update_count = 0
        webhook_info.last_error_date = None
        webhook_info.last_error_message = None
        webhook_info.max_connections = 40
        webhook_info.ip_address = '1.2.3.4'
        mock_get_webhook_info.return_value = webhook_info
        
        # Mock jsonify
        mock_jsonify.return_value = {'webhook_info': 'test'}
        
        # Call webhook_info
        response = app.webhook_info()
        
        # Assert webhook info was returned
        mock_get_webhook_info.assert_called_once()
        mock_jsonify.assert_called_once()
        self.assertEqual(response, {'webhook_info': 'test'})

    @patch('app.jsonify')
    def test_view_user_sessions(self, mock_jsonify):
        """Test viewing user sessions"""
        # Add a test session
        app.user_sessions[self.test_user.id] = {
            'state': 'main_menu',
            'data': {},
            'preferences': {
                'language': 'en',
                'notifications': True,
                'theme': 'default'
            }
        }
        
        # Mock jsonify
        mock_jsonify.return_value = {'sessions': 'test'}
        
        # Call view_user_sessions
        response = app.view_user_sessions()
        
        # Assert sessions were returned
        mock_jsonify.assert_called_once()
        self.assertEqual(response, {'sessions': 'test'})

    @patch('app.jsonify')
    def test_health_check(self, mock_jsonify):
        """Test the health check endpoint"""
        # Mock bot.get_me
        app.bot.get_me.return_value = MagicMock()
        app.bot.get_me.return_value.to_dict.return_value = {'id': 123456, 'username': 'test_bot'}
        
        # Mock jsonify
        mock_jsonify.return_value = {'status': 'ok'}
        
        # Call health_check
        response = app.health_check()
        
        # Assert health check was successful
        mock_jsonify.assert_called_once()
        self.assertEqual(response, {'status': 'ok'})

if __name__ == '__main__':
    unittest.main()
