"""
Telegram Bot Menu Button Tests

This module contains automated tests for Telegram bot menu button interactions using Telethon.
It tests the functionality of various menu buttons and navigation flows in a Telegram bot.

The tests verify:
1. Main menu appears with expected buttons
2. View My Data button works and displays user data
3. Settings submenu appears when clicking the Settings button
4. Back button returns to the main menu from submenus

Requirements:
- Python 3.7+
- pytest
- pytest-asyncio
- telethon
- python-dotenv

Environment variables (in .env file):
- TELEGRAM_API_ID: Your Telegram API ID (integer)
- TELEGRAM_API_HASH: Your Telegram API hash (string)
- TELEGRAM_PHONE: Your phone number in international format
- TELEGRAM_BOT_USERNAME: Username of the bot to test

Before running:
1. Create a .env file with the required environment variables
2. Run auth_telethon.py to authenticate with Telegram
3. Ensure the bot is running and accessible

Usage:
    # Run all tests
    pytest test_menu_buttons.py -v
    
    # Run a specific test
    pytest test_menu_buttons.py::test_main_menu -v
    
    # Run with auto mode for asyncio
    pytest test_menu_buttons.py -v --asyncio-mode=auto

Notes:
- Tests use a function-scoped fixture to avoid event loop issues
- The bot entity is stored globally to improve performance
- Tests will be skipped if required credentials are missing
- Increase sleep durations if your bot has slow response times
"""
import asyncio
import os
import pytest
import pytest_asyncio
from telethon import TelegramClient
from telethon.tl.custom import Button
from dotenv import load_dotenv
import logging
from telethon.types import PeerUser

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

# % pytest test_menu_buttons.py::test_main_menu -v 
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
    expected_buttons = ["Analyze My Messages", "View My Data", "Delete My Data", "Edit My Messages"]  # Adjust these to match your actual button names
    for expected in expected_buttons:
        assert any(expected in btn for btn in button_texts), f"Expected button '{expected}' not found"
        
        
#########

@pytest.mark.asyncio
async def test_delete_my_data(telegram_client: TelegramClient):
    """Test the complete delete my data flow including confirmation."""
    # Get the main menu
    bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID

    # Ensure bot_target is an entity Telethon can work with
    if isinstance(bot_target, int):
        bot_target = PeerUser(bot_target)  # Create a PeerUser object

    try:
        await telegram_client.send_message(bot_target, "/start")
    except Exception as e:
        logger.error(f"Failed to send /start message: {e}")
        raise  # Re-raise the exception to fail the test

    await asyncio.sleep(2)

    # Get the main menu message
    messages = await telegram_client.get_messages(bot_target, limit=5)
    main_menu = next((msg for msg in messages if msg.buttons), None)
    assert main_menu is not None, "Main menu not received"

    # Find and click Delete My Data button
    delete_button = next(
        (btn for row in main_menu.buttons
         for btn in row if "Delete My Data" in btn.text),
        None
    )
    assert delete_button is not None, "Delete My Data button not found"
    await main_menu.click(text=delete_button.text)
    await asyncio.sleep(8)

    # Retry logic for getting the confirmation menu
    for attempt in range(3):
        try:
            # Get the confirmation menu message (newest message with buttons)
            messages = await telegram_client.get_messages(bot_target, limit=5)
            confirm_menu = next(
                (msg for msg in reversed(messages)
                 if msg.buttons and any("yes" in btn.text.lower() or "no" in btn.text.lower()
                                         for row in msg.buttons for btn in row)),
                None
            )
            if confirm_menu is None:
                raise AssertionError("Confirmation menu not received")
            break  # Exit the loop if successful
        except AssertionError as e:
            logger.warning(f"Attempt {attempt + 1}: Confirmation menu not received: {e}")
            if attempt == 2:
                raise  # Re-raise the exception after the last attempt
            await asyncio.sleep(5)  # Wait before retrying

    # Find and click Yes button
    yes_button = next(
        (btn for row in confirm_menu.buttons
         for btn in row if "yes" in btn.text.lower() or "confirm" in btn.text.lower()),
        None
    )

    if yes_button is None:
        buttons_text = []
        if confirm_menu and confirm_menu.buttons:
            for row in confirm_menu.buttons:
                for btn in row:
                    buttons_text.append(btn.text)
        assert False, f"Confirmation button not found. Available buttons: {buttons_text}. Confirm Menu text: {confirm_menu.text if confirm_menu else 'No Confirm Menu'}"

    if yes_button:
        await confirm_menu.click(text=yes_button.text)
        await asyncio.sleep(4)
    else:
        assert False, "No 'yes' or 'confirm' button found in confirmation menu"

    # Retry logic for getting the deletion confirmation message
    for attempt in range(3):
        try:
            # Verify deletion confirmation message
            messages = await telegram_client.get_messages(bot_target, limit=5)
            deletion_msg = next(
                (msg for msg in messages
                 if msg.text and ("deleted" in msg.text.lower() or "removed" in msg.text.lower())),
                None
            )
            if deletion_msg is None:
                raise AssertionError("Deletion confirmation not received")
            logger.info(f"Received deletion confirmation: {deletion_msg.text[:100]}...")
            break  # Exit the loop if successful
        except AssertionError as e:
            logger.warning(f"Attempt {attempt + 1}: Deletion confirmation not received: {e}")
            if attempt == 2:
                raise  # Re-raise the exception after the last attempt
            await asyncio.sleep(5)  # Wait before retrying
    
#########


@pytest.mark.asyncio
async def test_send_image_and_get_response(telegram_client):
    """Test sending an image to the bot and verifying analysis."""
    test_image = "images/cadorna.jpeg"
    
    # Verify image exists
    if not os.path.exists(test_image):
        pytest.skip(f"Test image not found at {test_image}")

    # Send the image
    bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
    await telegram_client.send_file(bot_target, test_image, caption="Test image")

    # Wait longer for processing (since we're skipping the intermediate check)
    await asyncio.sleep(15)  # Increased wait time

    # Get all recent messages
    messages = await telegram_client.get_messages(bot_target, limit=10)
    
    # Verify final analysis contains expected content
    analysis_msg = next(
        (msg for msg in messages 
         if msg.text and ("cadorna" in msg.text.lower() or 
                         "luigi" in msg.text.lower() or
                         "general" in msg.text.lower())),
        None
    )
    
    assert analysis_msg, (
        "Bot did not provide analysis containing expected content. "
        f"Messages received: {[msg.text[:50] + '...' if msg.text else 'None' for msg in messages]}"
    )
    
    logger.info(f"Received analysis: {analysis_msg.text[:200]}...")
    
@pytest.mark.asyncio
async def test_view_my_data_button(telegram_client):
    """Test clicking the View My Data button in the main menu."""
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
    
    # Find and click the View My Data button
    view_my_data_button = None
    for row in menu_message.buttons:
        for button in row:
            if "View My Data" in button.text:  # Adjust this to match your actual button name
                view_my_data_button = button
                break
        if view_my_data_button:
            break
    
    assert view_my_data_button is not None, "View My Data button not found"
    
    # Click the button
    await menu_message.click(text=view_my_data_button.text)
    
    # Wait for response
    await asyncio.sleep(2)
    
    # Check for help text in recent messages
    bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
    recent_messages = await telegram_client.get_messages(bot_target, limit=5)
    help_received = False
    
    for msg in recent_messages:
        if "cadorna" in msg.text.lower() or "luigi" in msg.text.lower():
            help_received = True
            logger.info(f"Cadorna message received: {msg.text[:100]}...")
            break
    
    assert help_received, "No Luigi Cadorna message was received after clicking Help button"

    print (recent_messages)
    
    back_button_message = None
    for msg in recent_messages:
        if msg.buttons:
            back_button_message = msg
            break
        
   # Click the "Back to Main Menu" button
    await back_button_message.click(text="Back to Main Menu")
    
    # Wait for response
    await asyncio.sleep(2)

@pytest.mark.asyncio
async def test_send_text_and_get_response(telegram_client):
    """Test sending a text message and getting a specific response."""
    # Send a text message to the bot
    bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
    await telegram_client.send_message(bot_target, "Cómo se llama el paciente?")

    # Wait briefly for the response
    await asyncio.sleep(4)

    # Get the most recent message from the bot
    messages = await telegram_client.get_messages(bot_target, limit=5)
    response_received = False

    # Check if the bot responded with the expected text
    for msg in messages:
        print(msg.text)
        if msg.text and "cadorna" in msg.text.lower():
            response_received = True
            logger.info(f"Received expected response: {msg.text[:100]}...")
            break
    # print(response_received)
    assert response_received, "Bot did not respond with the expected text"


# @pytest.mark.asyncio
# async def test_settings_submenu(telegram_client):
#     """Test that the settings submenu appears when clicking Settings."""
#     # First get the main menu
#     # Use the bot entity if available, otherwise use the ID
#     bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
#     await telegram_client.send_message(bot_target, "/start")
#     await asyncio.sleep(2)
    
#     # Get the most recent message with buttons
#     bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
#     messages = await telegram_client.get_messages(bot_target, limit=5)
#     menu_message = None
#     for msg in messages:
#         if msg.buttons:
#             menu_message = msg
#             break
    
#     assert menu_message is not None, "No menu with buttons was received"
    
#     # Find and click the Settings button
#     settings_button = None
#     for row in menu_message.buttons:
#         for button in row:
#             if "Settings" in button.text or "Config" in button.text:  # Adjust this to match your actual button name
#                 settings_button = button
#                 break
#         if settings_button:
#             break
    
#     assert settings_button is not None, "Settings button not found"
    
#     # Click the button
#     await menu_message.click(text=settings_button.text)
    
#     # Wait for response
#     await asyncio.sleep(2)
    
#     # Check for settings submenu in recent messages
#     bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
#     recent_messages = await telegram_client.get_messages(bot_target, limit=5)
#     submenu_received = False
    
#     for msg in recent_messages:
#         # Check if this message has buttons (submenu)
#         if msg.buttons and msg.id != menu_message.id:
#             submenu_received = True
            
#             # Log the submenu buttons
#             submenu_buttons = []
#             for row in msg.buttons:
#                 for button in row:
#                     submenu_buttons.append(button.text)
#             logger.info(f"Settings submenu buttons: {submenu_buttons}")
            
#             # Verify expected submenu buttons (adjust based on your actual submenu)
#             expected_submenu = ["Preferences", "Back"]  # Adjust these to match your actual button names
#             for expected in expected_submenu:
#                 assert any(expected in btn for btn in submenu_buttons), f"Expected submenu button '{expected}' not found"
#             break
    
#     assert submenu_received, "No settings submenu was received after clicking Settings button"

# @pytest.mark.asyncio
# async def test_back_button(telegram_client):
    # """Test that the Back button returns to the main menu."""
    # # First navigate to a submenu
    # # Use the bot entity if available, otherwise use the ID
    # bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
    # await telegram_client.send_message(bot_target, "/start")
    # await asyncio.sleep(2)
    
    # # Get the main menu message
    # bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
    # messages = await telegram_client.get_messages(bot_target, limit=5)
    # menu_message = None
    # for msg in messages:
    #     if msg.buttons:
    #         menu_message = msg
    #         break
    
    # assert menu_message is not None, "No menu with buttons was received"
    
    # # Find and click a submenu button (e.g., Settings)
    # submenu_button = None
    # for row in menu_message.buttons:
    #     for button in row:
    #         if "Settings" in button.text or "Config" in button.text:  # Adjust this to match your actual button name
    #             submenu_button = button
    #             break
    #     if submenu_button:
    #         break
    
    # assert submenu_button is not None, "Submenu button not found"
    
    # # Click to enter submenu
    # await menu_message.click(text=submenu_button.text)
    # await asyncio.sleep(2)
    
    # # Find the submenu message with Back button
    # bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
    # messages = await telegram_client.get_messages(bot_target, limit=5)
    # submenu_message = None
    # for msg in messages:
    #     if msg.buttons and msg.id != menu_message.id:
    #         submenu_message = msg
    #         break
    
    # assert submenu_message is not None, "No submenu message was received"
    
    # # Find and click the Back button
    # back_button = None
    # for row in submenu_message.buttons:
    #     for button in row:
    #         if "Back" in button.text or "Return" in button.text:  # Adjust this to match your actual button name
    #             back_button = button
    #             break
    #     if back_button:
    #         break
    
    # assert back_button is not None, "Back button not found in submenu"
    
    # # Click the Back button
    # await submenu_message.click(text=back_button.text)
    # await asyncio.sleep(2)
    
    # # Verify we're back at the main menu
    # bot_target = BOT_ENTITY if BOT_ENTITY else BOT_ID
    # messages = await telegram_client.get_messages(bot_target, limit=5)
    # back_to_main = False
    
    # for msg in messages:
    #     # Check if this is a main menu message
    #     if msg.buttons:
    #         # Check for main menu buttons
    #         main_menu_buttons = []
    #         for row in msg.buttons:
    #             for button in row:
    #                 main_menu_buttons.append(button.text)
            
    #         # If we find expected main menu buttons, we're back
    #         if any("Help" in btn for btn in main_menu_buttons) and any(("Settings" in btn or "Config" in btn) for btn in main_menu_buttons):
    #             back_to_main = True
    #             break
    
    # assert back_to_main, "Did not return to main menu after clicking Back button"
