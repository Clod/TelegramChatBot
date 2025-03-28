# Telegram Bot with Flask Backend

## Overview

This is a comprehensive Telegram bot application built with Python, Flask, and the PyTeleBot library. The bot features a robust architecture with user session management, SQLite database storage, and a web interface for monitoring and administration.

## Features

### Core Functionality
- **Interactive Menu System**: Multi-level menu navigation with callback buttons
- **User Session Management**: Tracks individual user states to prevent message mixing
- **Database Storage**: Persistent storage of user data, messages, and interactions
- **User Privacy Controls**: Users can delete their own data from the system
- **Message History**: Shows users their previous message history
- **Image Processing**: Analyzes images using Gemini 2.0 Lite API
- **Google Form Integration**: Retrieves data from Google Forms
- **Google Sheet Integration**: Retrieves data from Google Sheets via Apps Script
- **Web App Integration**: Allows users to edit their messages through Telegram Web Apps

### Technical Features
- **Webhook Integration**: Secure communication with Telegram API
- **SSL Support**: HTTPS encryption for secure data transmission
- **Database Schema**:
  - Users table (personal information)
  - User preferences (settings)
  - User messages (message history)
  - User interactions (action tracking)
  - Image processing results (AI analysis)
- **Admin Dashboard**: Web endpoints for monitoring and management
- **Health Monitoring**: Status checks and statistics
- **AI Integration**: Gemini 2.0 Lite API for image analysis
- **Google API Integration**: Separate authentication systems for Gemini and other Google APIs

## Architecture

### Components
1. **Flask Web Application**: Handles HTTP requests and serves admin interfaces
2. **Telegram Bot**: Processes user messages and commands
3. **SQLite Database**: Stores all persistent data
4. **Session Manager**: Maintains user state during conversations
5. **Google API Clients**: Interfaces with Google services (Forms, Sheets, Gemini AI)
6. **Telegram Web Apps**: Client-side applications embedded in Telegram

### Data Flow
1. User sends message to Telegram
2. Telegram forwards message to webhook endpoint
3. Flask receives the update and passes it to the bot handler
4. Bot processes the message, updates the database, and manages user sessions
5. For AI/Google features, specialized authentication and API calls are made
6. Response is sent back to the user via Telegram API

## Database Schema

### Users Table
- `user_id`: Primary key, Telegram user ID
- `username`: Telegram username
- `first_name`, `last_name`: User's name
- `language_code`: User's language preference
- `is_bot`: Boolean flag for bot accounts
- `chat_id`: Current chat ID
- `created_at`, `last_activity`: Timestamps

### User Preferences Table
- `user_id`: Primary key, references Users
- `language`: Preferred language (default: 'en')
- `notifications`: Boolean for notification settings
- `theme`: UI theme preference
- `last_updated`: Timestamp

### User Messages Table
- `id`: Auto-incrementing primary key
- `user_id`: References Users
- `chat_id`: Chat where message was sent
- `message_id`: Telegram message ID
- `message_text`: Content of the message
- `message_type`: Type of message (text, photo, processed_text_from_image, retrieved_form_data, retrieved_sheet_data)
- `has_media`, `media_type`: Media information
- `timestamp`: When message was received

### User Interactions Table
- `id`: Auto-incrementing primary key
- `user_id`: References Users
- `action_type`: Type of interaction
- `action_data`: Additional data about the interaction
- `timestamp`: When interaction occurred

### Image Processing Results Table
- `id`: Auto-incrementing primary key
- `user_id`: References Users
- `message_id`: Telegram message ID
- `file_id`: Telegram file ID for the image
- `gemini_response`: JSON response from Gemini API
- `processed_at`: When the image was processed

## API Endpoints

### Bot Endpoints
- `/{TOKEN}`: Webhook receiver for Telegram updates
- `/`: Simple status check
- `/set_webhook`: Configure the Telegram webhook
- `/webhook_info`: Get information about the current webhook
- `/check_updates`: Manually check for updates (debugging)

### Admin Endpoints
- `/user_sessions`: View active user sessions
- `/db_users`: List all users in the database
- `/user_messages/{user_id}`: View messages from a specific user
- `/user_interactions/{user_id}`: View interactions from a specific user
- `/image_processing_results/{user_id}`: View image processing results
- `/update_preference/{user_id}`: Update user preferences
- `/health`: System health check with statistics

### Web App Endpoints
- `/webapp/edit_messages`: Serves the HTML page for message editing
- `/webapp/get_messages`: Provides user messages to the web app
- `/webapp/save_messages`: Receives updated message data from the web app

## Authentication System

### Specialized Authentication for Different Google APIs
- **Gemini API Authentication**: Uses a dedicated function that tries multiple scopes (cloud-platform, aiplatform, generative-ai) with explicit token refresh
- **Google APIs Authentication**: Separate function for Forms, Apps Script, and other Google services
- **Fallback Mechanism**: If one authentication method fails, alternative approaches are attempted
- **Comprehensive Logging**: Detailed logging of authentication processes for troubleshooting

## Security Features

- **Token Protection**: Bot token is loaded from environment variables
- **SSL Encryption**: All communication is encrypted with HTTPS
- **Error Handling**: Comprehensive error catching and logging
- **Data Privacy**: Users can delete their own data
- **Web App Authentication**: Validates Telegram initData for web app requests
- **Service Account Security**: Proper handling of Google service account credentials

## User Experience

### Commands
- `/start`, `/help`: Initialize the bot and show the main menu
- Text messages: Automatically saved and history is displayed
- Photos: Processed with Gemini 2.0 Lite API for detailed analysis

### Menu Navigation
1. **Main Menu**: Choose between different options:
   - Analyze My Messages (AI analysis of message history)
   - Retrieve Form Data (fetch Google Form responses)
   - Retrieve Sheet Data (fetch Google Sheet data)
   - View My Data (see stored user information)
   - Delete My Data (remove all user data)
   - Edit My Messages (via Telegram Web App)
2. **Data Deletion**: Confirmation process to prevent accidental deletion

### Web App Integration
- **Edit Messages**: Users can edit their message history through a Telegram Web App
- **Seamless Experience**: Web App is embedded directly in the Telegram interface
- **Secure Authentication**: Uses Telegram's initData validation

## Deployment

The application is designed to run in two modes:
- **Debug Mode**: Uses polling for local development
- **Production Mode**: Uses webhooks for deployment

Requirements:
- Python 3.6+
- Flask
- PyTeleBot
- SQLite3
- SSL certificate (Let's Encrypt)
- Google Service Account with appropriate permissions
- Public HTTPS domain for webhook and Web Apps

## Environment Configuration
Required environment variables:
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `BASE_URL`: Public HTTPS URL for your webhook
- `DEBUG_MODE`: "True" for development, "False" for production
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account JSON file
- `GOOGLE_FORM_ID`: ID of the Google Form to retrieve data from
- `APPS_SCRIPT_ID`: ID of the Google Apps Script
- `APPS_SCRIPT_WEB_APP_URL`: URL of the deployed Apps Script Web App
- `APPS_SCRIPT_API_KEY`: API key for the Apps Script Web App

## Monitoring and Maintenance

- **Logging**: Comprehensive logging of operations and errors
- **Health Checks**: Regular verification of system status
- **Database Statistics**: Track user growth and engagement
- **Authentication Diagnostics**: Detailed logging of authentication processes

## Future Enhancements

Potential areas for expansion:
- User authentication for admin endpoints
- Message encryption for sensitive communications
- Additional media handling capabilities
- Natural language processing integration
- Analytics dashboard for user behavior
- More Telegram Web App integrations
- Enhanced Google Workspace integrations
