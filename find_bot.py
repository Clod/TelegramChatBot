# find_bot.py - A simple script to find a bot in your Telegram dialogs
from telethon import TelegramClient
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE = os.getenv("TELEGRAM_PHONE")
BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "")
# Always add @ if it's not included in the environment variable
if BOT_USERNAME and not BOT_USERNAME.startswith('@'):
    BOT_USERNAME = '@' + BOT_USERNAME
print(f"Looking for bot username: {BOT_USERNAME}")
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
    
    print("Getting dialogs (recent conversations)...")
    dialogs = await client.get_dialogs()
    
    print("\nAll dialogs:")
    for i, dialog in enumerate(dialogs):
        print(f"{i+1}. {dialog.name} ({dialog.entity.id if hasattr(dialog.entity, 'id') else 'No ID'})")
    
    print("\nLooking for bot in dialogs...")
    bot_username_clean = BOT_USERNAME.replace('@', '').lower()
    for dialog in dialogs:
        if dialog.name and bot_username_clean in dialog.name.lower():
            print(f"Found bot: {dialog.name}")
            print(f"Bot ID: {dialog.entity.id if hasattr(dialog.entity, 'id') else 'No ID'}")
            print(f"Is bot: {getattr(dialog.entity, 'bot', False)}")
            
            # Try to send a test message
            print("\nTrying to send a test message...")
            try:
                await client.send_message(dialog.entity, "Test message from Telethon")
                print("Message sent successfully!")
            except Exception as e:
                print(f"Error sending message: {e}")
            
            break
    else:
        print(f"Bot {BOT_USERNAME} not found in recent dialogs.")
        print("You may need to start a conversation with the bot first.")
        print(f"Try opening Telegram and sending a message to {BOT_USERNAME}")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
