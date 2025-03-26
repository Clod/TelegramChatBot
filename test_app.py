import unittest
import app
import json
from unittest.mock import patch
import sqlite3
import os

class TestExtractTextFromGeminiResponse(unittest.TestCase):

    def test_extract_valid_response(self):
        """Test with a valid Gemini response"""
        with open('gemini_response.json', 'r') as f:
            gemini_response = json.load(f)
        extracted_text = app.extract_text_from_gemini_response(gemini_response)
        self.assertIsInstance(extracted_text, str)
        self.assertGreater(len(extracted_text), 0)
        self.assertTrue("full_name" in extracted_text)

    def test_extract_empty_response(self):
        """Test with an empty Gemini response"""
        gemini_response = {}
        extracted_text = app.extract_text_from_gemini_response(gemini_response)
        self.assertEqual(extracted_text, "No text content found in the response.")

    def test_extract_no_candidates(self):
        """Test with a response missing 'candidates'"""
        gemini_response = {"missing": "candidates"}
        extracted_text = app.extract_text_from_gemini_response(gemini_response)
        self.assertEqual(extracted_text, "No text content found in the response.")

    def test_extract_malformed_json(self):
        """Test with a malformed JSON string in the response"""
        gemini_response = '[{"candidates": [{"content": {"parts": [{"text": "{\'key\': \'value\'"}]}}]}]'
        extracted_text = app.extract_text_from_gemini_response(gemini_response)
        self.assertEqual(extracted_text, "Error processing response")

    def test_extract_no_text_in_parts(self):
        """Test with a response where the 'text' key is missing in 'parts'"""
        gemini_response = {"candidates": [{"content": {"parts": [{}]}}]}
        extracted_text = app.extract_text_from_gemini_response(gemini_response)
        self.assertEqual(extracted_text, "No text content found in the response.")

    def test_extract_pipe_separated_response(self):
        """Test with a response that already contains pipe-separated values"""
        gemini_response = {"candidates": [{"content": {"parts": [{"text": "name=test|age=30"}]}}]}
        extracted_text = app.extract_text_from_gemini_response(gemini_response)
        self.assertEqual(extracted_text, "name=test|age=30")

    def test_extract_json_response(self):
        """Test with a response containing a JSON object"""
        gemini_response = {"candidates": [{"content": {"parts": [{"text": '{"name": "test", "age": 30}'}]}}]}
        extracted_text = app.extract_text_from_gemini_response(gemini_response)
        self.assertEqual(extracted_text, "name=test|age=30")

    def test_extract_response_with_markdown(self):
        """Test with a response containing markdown formatting"""
        gemini_response = {"candidates": [{"content": {"parts": [{"text": "**name**: test"}]}}]}
        extracted_text = app.extract_text_from_gemini_response(gemini_response)
        self.assertEqual(extracted_text, "name: test")

    def test_extract_list_of_responses(self):
        """Test with a list of Gemini responses"""
        gemini_response = [
            {"candidates": [{"content": {"parts": [{"text": "name=test1"}]}}]},
            {"candidates": [{"content": {"parts": [{"text": "name=test2"}]}]}
        ]
        extracted_text = app.extract_text_from_gemini_response(gemini_response)
        self.assertEqual(extracted_text, "name=test1name=test2")

class TestFlaskRoutes(unittest.TestCase):

    def setUp(self):
        """Setup before each test (e.g., initialize a test database, mock objects)"""
        app.app.config['TESTING'] = True  # Configure Flask app for testing
        self.app = app.app.test_client()  # Create a test client for Flask

    def test_health_check(self):
        """Test the /health endpoint"""
        response = self.app.get('/health')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(data['status'], 'ok')

    def test_webhook_info(self):
        """Test the /webhook_info endpoint"""
        with patch('app.bot.get_webhook_info') as mock_get_webhook_info:
            mock_get_webhook_info.return_value = type('obj', (object,), {'url': 'test_url', 'has_custom_certificate': False, 'pending_update_count': 0, 'last_error_date': None, 'last_error_message': None, 'max_connections': 40, 'ip_address': None})()
            response = self.app.get('/webhook_info')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.get_data(as_text=True))
            self.assertEqual(data['url'], 'test_url')

class TestStartCommand(unittest.TestCase):

    def setUp(self):
        """Setup before each test (e.g., initialize a test database, mock objects)"""
        app.app.config['TESTING'] = True  # Configure Flask app for testing
        self.app = app.app.test_client()  # Create a test client for Flask
        # Use an in-memory SQLite database for testing
        app.DB_PATH = 'test.db'
        app.init_db()

    def tearDown(self):
        """Teardown after each test (e.g., clean up the test database)"""
        # Delete the test database file
        os.remove(app.DB_PATH)

    @patch('app.bot.reply_to')  # Mock the reply_to function
    def test_start_command(self, mock_reply_to):
        """Test the /start command"""
        message = type('obj', (object,), {'text': '/start', 'chat': type('obj', (object,), {'id': 123}), 'from_user': type('obj', (object,), {'id': 456, 'username': 'testuser', 'first_name': 'Test', 'last_name': 'User', 'language_code': 'en', 'is_bot': False})})() # Create a mock message object
        app.send_welcome(message)
        mock_reply_to.assert_called_once() #Verify that reply_to was called

        # Verify that the user was saved to the database
        conn = sqlite3.connect(app.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (456,))
        user = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(user)
        self.assertEqual(user[1], 'testuser') # Verify username

if __name__ == '__main__':
    unittest.main()
