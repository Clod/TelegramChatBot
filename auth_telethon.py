"""
Authentication script for Telegram API using Telethon.

This script handles the authentication process for the Telegram API using the Telethon library.
It should be run once before executing any Telethon-based tests or scripts that require
authentication with the Telegram API.

The script:
1. Loads environment variables from a .env file
2. Connects to Telegram using API credentials
3. Checks if the user is already authorized
4. If not authorized, requests a verification code to be sent to the user's phone
5. Prompts the user to enter the code received
6. Completes the sign-in process
7. Creates a session file that can be reused by other scripts (./telegram_test_session.session)

Environment variables required in .env file:
- TELEGRAM_API_ID: Your Telegram API ID (integer)
- TELEGRAM_API_HASH: Your Telegram API hash (string)
- TELEGRAM_PHONE: Your phone number in international format (e.g., +12345678901)
- TELEGRAM_BOT_USERNAME: Username of the bot to test (optional)

The session is saved to a file named "menu_test_session.session" which will be
used by other scripts to avoid re-authentication.

Usage:
    python auth_telethon.py

Note: This script must be run interactively as it may require user input for the verification code.
"""
from telethon import TelegramClient
import os
from dotenv import load_dotenv
import asyncio
import sys # Import sys for exiting

load_dotenv()

# --- Environment Variable Loading and Validation ---
required_vars = ["TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_PHONE"]
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
    print("Please ensure TELEGRAM_API_ID, TELEGRAM_API_HASH, and TELEGRAM_PHONE are set in your .env file.")
    sys.exit(1) # Exit if required variables are missing

try:
    API_ID = int(os.getenv("TELEGRAM_API_ID"))
except (ValueError, TypeError):
    print("Error: TELEGRAM_API_ID environment variable must be a valid integer.")
    sys.exit(1)

API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE = os.getenv("TELEGRAM_PHONE")
BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "")
# --- End Validation ---
# Always add @ if it's not included in the environment variable
if BOT_USERNAME and not BOT_USERNAME.startswith('@'):
    BOT_USERNAME = '@' + BOT_USERNAME
print(f"Using bot username: {BOT_USERNAME}")
SESSION_NAME = "menu_test_session"

async def main():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        await client.send_code_request(PHONE)
        code = input("Enter the code you received: ")
        await client.sign_in(PHONE, code)
        print("Successfully authenticated")
    else:
        print("Already authenticated")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
