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

### Technical Features
- **Webhook Integration**: Secure communication with Telegram API
- **SSL Support**: HTTPS encryption for secure data transmission
- **Database Schema**:
  - Users table (personal information)
  - User preferences (settings)
  - User messages (message history)
  - User interactions (action tracking)
- **Admin Dashboard**: Web endpoints for monitoring and management
- **Health Monitoring**: Status checks and statistics

## Architecture

### Components
1. **Flask Web Application**: Handles HTTP requests and serves admin interfaces
2. **Telegram Bot**: Processes user messages and commands
3. **SQLite Database**: Stores all persistent data
4. **Session Manager**: Maintains user state during conversations

### Data Flow
1. User sends message to Telegram
2. Telegram forwards message to webhook endpoint
3. Flask receives the update and passes it to the bot handler
4. Bot processes the message, updates the database, and manages user sessions
5. Response is sent back to the user via Telegram API

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
- `message_type`: Type of message (text, photo, etc.)
- `has_media`, `media_type`: Media information
- `timestamp`: When message was received

### User Interactions Table
- `id`: Auto-incrementing primary key
- `user_id`: References Users
- `action_type`: Type of interaction
- `action_data`: Additional data about the interaction
- `timestamp`: When interaction occurred

## API Endpoints

### Bot Endpoints
- `/{TOKEN}`: Webhook receiver for Telegram updates
- `/`: Simple status check
- `/set_webhook`: Configure the Telegram webhook
- `/webhook_info`: Get information about the current webhook

### Admin Endpoints
- `/user_sessions`: View active user sessions
- `/db_users`: List all users in the database
- `/user_messages/{user_id}`: View messages from a specific user
- `/user_interactions/{user_id}`: View interactions from a specific user
- `/update_preference/{user_id}`: Update user preferences
- `/health`: System health check with statistics

## Security Features

- **Token Protection**: Bot token is loaded from environment variables
- **SSL Encryption**: All communication is encrypted with HTTPS
- **Error Handling**: Comprehensive error catching and logging
- **Data Privacy**: Users can delete their own data

## User Experience

### Commands
- `/start`, `/help`: Initialize the bot and show the main menu
- Text messages: Automatically saved and history is displayed

### Menu Navigation
1. **Main Menu**: Choose between different options or delete data
2. **Submenus**: Each main menu option has its own submenu items
3. **Data Deletion**: Confirmation process to prevent accidental deletion

## Deployment

The application is designed to run on a server with:
- Python 3.6+
- Flask
- PyTeleBot
- SQLite3
- SSL certificate (Let's Encrypt)

## Monitoring and Maintenance

- **Logging**: Comprehensive logging of operations and errors
- **Health Checks**: Regular verification of system status
- **Database Statistics**: Track user growth and engagement

## Future Enhancements

Potential areas for expansion:
- User authentication for admin endpoints
- Message encryption for sensitive communications
- Media handling capabilities
- Natural language processing integration
- Analytics dashboard for user behavior
