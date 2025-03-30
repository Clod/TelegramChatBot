import asyncio
import os
import pytest
import pytest_asyncio
from telethon import TelegramClient
from telethon.tl.custom import Button
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Enable more verbose logging for Telethon
telethon_logger = logging.getLogger('telethon')
telethon_logger.setLevel(logging.INFO)

# Load environment variables
load_dotenv()

# Read credentials from environment variables
API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
PHONE = os.getenv("TELEGRAM_PHONE", "")
BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "")
# Always add @ if it's not included in the environment variable
if BOT_USERNAME and not BOT_USERNAME.startswith('@'):
    BOT_USERNAME = '@' + BOT_USERNAME
SESSION_NAME = "menu_test_session"

# Define a global variable to store the bot entity
BOT_ENTITY = None
# Hardcoded bot ID from find_bot.py output as fallback
BOT_ID = 8166772639

# Skip all tests if credentials are missing
pytestmark = pytest.mark.skipif(
    not all([API_ID, API_HASH, PHONE, BOT_USERNAME]),
    reason="Telegram credentials not found in environment variables"
)

# Important: Use function scope for the client to avoid event loop issues
@pytest_asyncio.fixture(scope="function")
async def telegram_client():
    """Create a new client for each test function to avoid event loop issues."""
    # Create and connect the client
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()
    
    # Check if we're already authorized
    if not await client.is_user_authorized():
        logger.info("User not authorized. Please complete the login process manually first.")
        logger.info("Run a simple script with Telethon to log in before running tests.")
        pytest.skip("Authentication required")
    
    # Try to resolve the bot username to make sure it's valid
    logger.info(f"Testing connection to bot: {BOT_USERNAME}")
    try:
        # Use dialogs to find the bot instead of resolving username directly
        dialogs = await client.get_dialogs()
        bot_found = False
        bot_entity = None
        for dialog in dialogs:
            if dialog.name and BOT_USERNAME.replace('@', '') in dialog.name.lower():
                logger.info(f"Found bot in dialogs: {dialog.name}")
                logger.info(f"Bot entity ID: {dialog.entity.id}")
                bot_found = True
                bot_entity = dialog.entity
                break
        
        if not bot_found:
            logger.warning(f"Bot {BOT_USERNAME} not found in recent dialogs. Tests may fail.")
        else:
            # Store the bot entity ID globally for use in tests
            global BOT_ENTITY
            BOT_ENTITY = bot_entity
    except Exception as e:
        logger.warning(f"Error checking bot existence: {e}")
    
    # Return the connected client
    yield client
    
    # Disconnect after the test
    await client.disconnect()

@pytest.mark.asyncio
async def test_main_menu(telegram_client):
    """Test that the main menu appears and has expected buttons."""
    # Send the /start command to get the main menu
    # Use the bot entity if available, otherwise use the ID
    bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
    await telegram_client.send_message(bot_target, "/start")
    
    # Wait briefly for the response
    await asyncio.sleep(2)
    
    # Get the most recent message from the bot
    bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
    messages = await telegram_client.get_messages(bot_target, limit=5)
    menu_message = None
    
    # Find the message with buttons
    for msg in messages:
        if msg.buttons:
            menu_message = msg
            break
    
    # Verify we got a menu with buttons
    assert menu_message is not None, "No menu with buttons was received"
    
    # Log the buttons we found
    button_texts = []
    for row in menu_message.buttons:
        for button in row:
            button_texts.append(button.text)
    logger.info(f"Found buttons: {button_texts}")
    
    # Verify expected buttons exist based on your bot's menu
    expected_buttons = ["Help", "Process", "About"]  # Adjust these to match your actual button names
    for expected in expected_buttons:
        assert any(expected in btn for btn in button_texts), f"Expected button '{expected}' not found"

@pytest.mark.asyncio
async def test_help_button(telegram_client):
    """Test clicking the Help button in the main menu."""
    # First get the main menu
    # Use the bot entity if available, otherwise use the ID
    bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
    await telegram_client.send_message(bot_target, "/start")
    await asyncio.sleep(2)
    
    # Get the most recent message with buttons
    bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
    messages = await telegram_client.get_messages(bot_target, limit=5)
    menu_message = None
    for msg in messages:
        if msg.buttons:
            menu_message = msg
            break
    
    assert menu_message is not None, "No menu with buttons was received"
    
    # Find and click the Help button
    help_button = None
    for row in menu_message.buttons:
        for button in row:
            if "Help" in button.text:  # Adjust this to match your actual button name
                help_button = button
                break
        if help_button:
            break
    
    assert help_button is not None, "Help button not found"
    
    # Click the button
    await menu_message.click(text=help_button.text)
    
    # Wait for response
    await asyncio.sleep(2)
    
    # Check for help text in recent messages
    bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
    recent_messages = await telegram_client.get_messages(bot_target, limit=5)
    help_received = False
    
    for msg in recent_messages:
        if "help" in msg.text.lower() or "command" in msg.text.lower():
            help_received = True
            logger.info(f"Help message received: {msg.text[:100]}...")
            break
    
    assert help_received, "No help message was received after clicking Help button"

@pytest.mark.asyncio
async def test_settings_submenu(telegram_client):
    """Test that the settings submenu appears when clicking Settings."""
    # First get the main menu
    # Use the bot entity if available, otherwise use the ID
    bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
    await telegram_client.send_message(bot_target, "/start")
    await asyncio.sleep(2)
    
    # Get the most recent message with buttons
    bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
    messages = await telegram_client.get_messages(bot_target, limit=5)
    menu_message = None
    for msg in messages:
        if msg.buttons:
            menu_message = msg
            break
    
    assert menu_message is not None, "No menu with buttons was received"
    
    # Find and click the Settings button
    settings_button = None
    for row in menu_message.buttons:
        for button in row:
            if "Settings" in button.text or "Config" in button.text:  # Adjust this to match your actual button name
                settings_button = button
                break
        if settings_button:
            break
    
    assert settings_button is not None, "Settings button not found"
    
    # Click the button
    await menu_message.click(text=settings_button.text)
    
    # Wait for response
    await asyncio.sleep(2)
    
    # Check for settings submenu in recent messages
    bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
    recent_messages = await telegram_client.get_messages(bot_target, limit=5)
    submenu_received = False
    
    for msg in recent_messages:
        # Check if this message has buttons (submenu)
        if msg.buttons and msg.id != menu_message.id:
            submenu_received = True
            
            # Log the submenu buttons
            submenu_buttons = []
            for row in msg.buttons:
                for button in row:
                    submenu_buttons.append(button.text)
            logger.info(f"Settings submenu buttons: {submenu_buttons}")
            
            # Verify expected submenu buttons (adjust based on your actual submenu)
            expected_submenu = ["Preferences", "Back"]  # Adjust these to match your actual button names
            for expected in expected_submenu:
                assert any(expected in btn for btn in submenu_buttons), f"Expected submenu button '{expected}' not found"
            break
    
    assert submenu_received, "No settings submenu was received after clicking Settings button"

@pytest.mark.asyncio
async def test_back_button(telegram_client):
    """Test that the Back button returns to the main menu."""
    # First navigate to a submenu
    # Use the bot entity if available, otherwise use the ID
    bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
    await telegram_client.send_message(bot_target, "/start")
    await asyncio.sleep(2)
    
    # Get the main menu message
    bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
    messages = await telegram_client.get_messages(bot_target, limit=5)
    menu_message = None
    for msg in messages:
        if msg.buttons:
            menu_message = msg
            break
    
    assert menu_message is not None, "No menu with buttons was received"
    
    # Find and click a submenu button (e.g., Settings)
    submenu_button = None
    for row in menu_message.buttons:
        for button in row:
            if "Settings" in button.text or "Config" in button.text:  # Adjust this to match your actual button name
                submenu_button = button
                break
        if submenu_button:
            break
    
    assert submenu_button is not None, "Submenu button not found"
    
    # Click to enter submenu
    await menu_message.click(text=submenu_button.text)
    await asyncio.sleep(2)
    
    # Find the submenu message with Back button
    bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
    messages = await telegram_client.get_messages(bot_target, limit=5)
    submenu_message = None
    for msg in messages:
        if msg.buttons and msg.id != menu_message.id:
            submenu_message = msg
            break
    
    assert submenu_message is not None, "No submenu message was received"
    
    # Find and click the Back button
    back_button = None
    for row in submenu_message.buttons:
        for button in row:
            if "Back" in button.text or "Return" in button.text:  # Adjust this to match your actual button name
                back_button = button
                break
        if back_button:
            break
    
    assert back_button is not None, "Back button not found in submenu"
    
    # Click the Back button
    await submenu_message.click(text=back_button.text)
    await asyncio.sleep(2)
    
    # Verify we're back at the main menu
    bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
    messages = await telegram_client.get_messages(bot_target, limit=5)
    back_to_main = False
    
    for msg in messages:
        # Check if this is a main menu message
        if msg.buttons:
            # Check for main menu buttons
            main_menu_buttons = []
            for row in msg.buttons:
                for button in row:
                    main_menu_buttons.append(button.text)
            
            # If we find expected main menu buttons, we're back
            if any("Help" in btn for btn in main_menu_buttons) and any(("Settings" in btn or "Config" in btn) for btn in main_menu_buttons):
                back_to_main = True
                break
    
    assert back_to_main, "Did not return to main menu after clicking Back button"
