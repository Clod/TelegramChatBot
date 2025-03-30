# auth_telethon.py - Run this once to authenticate
from telethon import TelegramClient
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()
API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE = os.getenv("TELEGRAM_PHONE")
BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "")
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
