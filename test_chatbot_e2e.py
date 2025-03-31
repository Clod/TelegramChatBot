import asyncio
import os
import pytest
import pytest_asyncio
from telethon import TelegramClient
from telethon.types import PeerUser
from dotenv import load_dotenv
import logging
import re

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

# Hardcoded bot ID from find_bot.py output as fallback
BOT_ID = 8166772639

# Skip all tests if credentials are missing
pytestmark = pytest.mark.skipif(
    not all([API_ID, API_HASH, PHONE, BOT_USERNAME]),
    reason="Telegram credentials not found in environment variables"
)


# Helper functions
async def get_bot_entity(client: TelegramClient, bot_username: str, bot_id: int, cache: pytest.Cache):
    """
    Retrieves the bot entity. Uses a cache to avoid repeated API calls.
    If not found in cache or dialogs, returns the bot ID as fallback
    """

    cached_entity = cache.get("bot_entity", None)
    if cached_entity:
        logger.info(f"Using cached bot entity: {cached_entity}")
        return cached_entity
    try:
        dialogs = await client.get_dialogs()
        bot_found = False
        bot_entity = None
        for dialog in dialogs:
            if dialog.name and bot_username.replace('@', '').lower() in dialog.name.lower():
                logger.info(f"Found bot in dialogs: {dialog.name}")
                logger.info(f"Bot entity ID: {dialog.entity.id}")
                bot_found = True
                bot_entity = dialog.entity
                break
        if not bot_found:
            logger.warning(f"Bot {bot_username} not found in recent dialogs.")
            return bot_id

        cache.set("bot_entity", bot_entity)
        return bot_entity

    except Exception as e:
        logger.warning(f"Error checking bot existence: {e}")
        return bot_id

async def send_message_with_retry(client: TelegramClient, bot_target, message: str, max_retries: int = 3, delay: int = 2):
    """Sends a message with retry logic."""
    for attempt in range(max_retries):
        try:
            await client.send_message(bot_target, message)
            return  # Success, exit the loop
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} to send message failed: {e}")
            if attempt == max_retries - 1:
                raise  # Re-raise the exception if all retries failed
            await asyncio.sleep(delay)  # Wait before retrying

async def get_latest_message_with_buttons(client: TelegramClient, bot_target, limit: int = 5):
    """Gets the most recent message with buttons from the bot."""
    messages = await client.get_messages(bot_target, limit=limit)
    for msg in messages:
        if msg.buttons:
            return msg
    return None


async def click_button(message, button_text):
    """
    Helper function to click a button, handling potential issues.
    """
    try:
        await message.click(text=button_text)
    except Exception as e:
        logger.error(f"Error clicking button {button_text}: {e}")
        raise


@pytest_asyncio.fixture(scope="function")
async def telegram_client(pytestconfig):
    """Create a new client for each test function to avoid event loop issues."""
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        logger.info("User not authorized. Please complete the login process manually first.")
        logger.info("Run a simple script with Telethon to log in before running tests.")
        pytest.skip("Authentication required")

    # Cache bot entity using pytest's cache
    bot_entity = await get_bot_entity(client, BOT_USERNAME, BOT_ID, pytestconfig.cache)

    # Store the bot entity for use in tests
    yield client, bot_entity  # Yield both client and bot_entity

    await client.disconnect()


@pytest.mark.asyncio
async def test_main_menu(telegram_client):
    """Test that the main menu appears and has expected buttons."""
    client, bot_entity = telegram_client
    await send_message_with_retry(client, bot_entity, "/start")
    await asyncio.sleep(2)

    menu_message = await get_latest_message_with_buttons(client, bot_entity)

    assert menu_message is not None, "No menu with buttons was received after sending /start"

    button_texts = [button.text for row in menu_message.buttons for button in row]
    logger.info(f"Found buttons: {button_texts}")

    expected_buttons = ["Analyze My Messages", "View My Data", "Delete My Data",
                        "Edit My Messages"]  # Adjust these to match your actual button names
    for expected in expected_buttons:
        assert any(expected in btn for btn in button_texts), f"Expected button '{expected}' not found"


# @pytest.mark.asyncio
# async def test_delete_my_data(telegram_client):
#     """Test the complete delete my data flow including confirmation."""
#     client, bot_entity = telegram_client

#     # Convert to PeerUser if it's just the ID
#     if isinstance(bot_entity, int):
#         bot_target = PeerUser(bot_entity)
#     else:
#         bot_target = bot_entity


#     await send_message_with_retry(client, bot_target, "/start")
#     await asyncio.sleep(2)

#     main_menu = await get_latest_message_with_buttons(client, bot_target)
#     assert main_menu is not None, "Main menu not received after sending /start"

#     # More robust button search using regex
#     delete_button = next((
#         btn for row in main_menu.buttons
#         for btn in row if re.search(r"Delete My Data", btn.text, re.IGNORECASE)
#     ), None)
#     assert delete_button is not None, "Delete My Data button not found in main menu"

#     await click_button(main_menu, delete_button.text)
#     await asyncio.sleep(8)

#     # Get the confirmation menu message
#     messages = await client.get_messages(bot_target, limit=5)
#     confirm_menu = next((msg for msg in reversed(messages) if msg.buttons), None)
#     assert confirm_menu is not None, "Confirmation menu not received after clicking Delete My Data"

#     # Simplified logic for finding yes_button
#     yes_button = next(
#         (btn for row in confirm_menu.buttons for btn in row
#          if re.search(r"yes|confirm", btn.text.lower())),
#         None
#     )

#     if yes_button is None:
#         buttons_text = [btn.text for row in confirm_menu.buttons for btn in row] if confirm_menu and confirm_menu.buttons else []
#         assert False, f"Confirmation button not found. Available buttons: {buttons_text}. Confirm Menu text: {confirm_menu.text if confirm_menu else 'No Confirm Menu'}"

#     await click_button(confirm_menu, yes_button.text)
#     await asyncio.sleep(4)


#     # Verify deletion confirmation message
#     messages = await client.get_messages(bot_target, limit=5)
#     deletion_msg = next(
#         (msg for msg in messages
#          if msg.text and re.search(r"deleted|removed", msg.text.lower())),  # More robust regex
#         None
#     )
#     assert deletion_msg is not None, "Deletion confirmation message not received"
#     logger.info(f"Received deletion confirmation: {deletion_msg.text[:100]}...")


@pytest.mark.asyncio
async def test_send_image_and_get_response(telegram_client):
    """Test sending an image to the bot and verifying analysis."""
    client, bot_entity = telegram_client
    test_image = "images/cadorna.jpeg"

    if not os.path.exists(test_image):
        pytest.skip(f"Test image not found at {test_image}")

    await client.send_file(bot_entity, test_image, caption="Test image")
    await asyncio.sleep(15)  # Increased wait time

    messages = await client.get_messages(bot_entity, limit=10)

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
    client, bot_entity = telegram_client
    await send_message_with_retry(client, bot_entity, "/start")
    await asyncio.sleep(2)

    menu_message = await get_latest_message_with_buttons(client, bot_entity)
    assert menu_message is not None, "No menu with buttons was received"

    view_my_data_button = next(
        (button for row in menu_message.buttons for button in row if "View My Data" in button.text),
        None
    )

    assert view_my_data_button is not None, "View My Data button not found"

    await click_button(menu_message, view_my_data_button.text)
    await asyncio.sleep(2)

    recent_messages = await client.get_messages(bot_entity, limit=5)
    help_received = False

    for msg in recent_messages:
        if "cadorna" in msg.text.lower() or "luigi" in msg.text.lower():
            help_received = True
            logger.info(f"Cadorna message received: {msg.text[:100]}...")
            break

    assert help_received, "No Luigi Cadorna message was received after clicking Help button"

    back_button_message = next((msg for msg in recent_messages if msg.buttons), None)

    await click_button(back_button_message, "Back to Main Menu")

    await asyncio.sleep(2)


@pytest.mark.asyncio
async def test_send_text_and_get_response(telegram_client):
    """Test sending a text message and getting a specific response."""
    client, bot_entity = telegram_client
    await send_message_with_retry(client, bot_entity, "Cómo se llama el paciente?")
    await asyncio.sleep(4)

    messages = await client.get_messages(bot_entity, limit=5)
    response_received = False

    for msg in messages:
        if msg.text and "cadorna" in msg.text.lower():
            response_received = True
            logger.info(f"Received expected response: {msg.text[:100]}...")
            break

    assert response_received, "Bot did not respond with the expected text"