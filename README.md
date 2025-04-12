# Telegram Bot with Flask Backend

## Overview

This is a **comprehensive** Telegram bot application built with Python, Flask, and the PyTeleBot library. The bot features a robust architecture with user session management, SQLite database storage, and a web interface for monitoring and administration.

## Features

### Core Functionality
- **Interactive Menu System**: Multi-level menu navigation with callback buttons
- **User Session Management**: Tracks individual user states to prevent message mixing
- **Database Storage**: Persistent storage of user data, messages, and interactions
- **User Privacy Controls**: Users can delete their own data from the system
- **Message History**: Stores user message history (text, processed images, form/sheet data, data entries)
- **AI Text Analysis**: Automatically analyzes incoming text messages (non-commands, non-keywords) using Gemini API for context/answers. Also available via menu.
- **Keyword Data Entry**: Recognizes messages starting with "dato" or "datos" (case-insensitive, optional colon) to store the subsequent text as structured data (`data_entry` type).
- **Image Processing**: Analyzes images using Gemini API (OCR and JSON extraction).
- **Google Form Integration**: Retrieves data from Google Forms based on IDs found in messages.
- **Google Sheet Integration**: Retrieves data from Google Sheets via Apps Script Web App based on IDs found in messages.
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
4. Bot processes the message:
    - Saves user info and logs interaction.
    - If it's an image, downloads it, sends to Gemini for OCR/JSON extraction, saves results, and replies.
    - If it starts with "dato[s][:]", strips the keyword, saves the content as `data_entry` type, confirms, and shows the menu.
    - If it's a command (`/start`, `/help`), handles the command.
    - If it's other text, saves it, then immediately triggers Gemini analysis including this message and recent history, replies with the analysis, and shows the menu.
    - If it's a callback query (button press), handles the corresponding action (menu navigation, data retrieval, deletion, AI analysis).
5. For AI/Google features, specialized authentication and API calls are made.
6. Response (menu, confirmation, analysis result, data) is sent back to the user via Telegram API.

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
- `message_text`: Content of the message (or processed/retrieved data)
- `message_type`: Type of message (`text`, `photo`, `processed_text_from_image`, `retrieved_form_data`, `retrieved_sheet_data`, `data_entry`)
- `has_media`, `media_type`: Media information (based on original message if text is overridden)
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
- **SSL Encryption**: All communication is encrypted with HTTPS (certificate and private key must be in certs directory)
- **Error Handling**: Comprehensive error catching and logging
- **Data Privacy**: Users can delete their own data
- **Web App Authentication**: Validates Telegram initData for web app requests
- **Service Account Security**: Proper handling of Google service account credentials

## User Experience

### Commands & Message Handling
- `/start`, `/help`: Initialize the bot and show the main menu.
- **Text Messages (Keywords)**: Messages starting with `dato`, `datos`, `dato:`, or `datos:` (case-insensitive) have the keyword prefix removed, and the remaining content is saved as a `data_entry` message type. A confirmation is sent, followed by the main menu.
- **Text Messages (Other)**: Regular text messages (not starting with keywords or '/') are saved and then immediately sent to the Gemini API (along with recent history) for analysis. The AI's response is sent back to the user, followed by the main menu.
- **Photos**: Processed with Gemini API for OCR and structured data extraction (JSON format). The result is saved and sent to the user, followed by the main menu.

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

## Note about Google Forms retrieval implemention:
The form needs to have a field named "id" that must be populated with a unique identifier for the data present in the form.
To retrieve the data from the form and add it to the database, the user first has to send a message form=\<unique id number\>
and then press the menu button to retrieve form data.

To be able to retrieve data directly from Google Forms via API a paid Google Account is needed. As this project is aimed
to non profit hospitals it uses a *horrible* workaround that allows form data retrieval for free. 

To that end:

- The form must be associated to a Google Sheet
- The Google Sheet must have associated a Google Apps Script that retrieves the line corresponding to the form (identified by id).
  Said script needs to be deployed as a Web App.  
