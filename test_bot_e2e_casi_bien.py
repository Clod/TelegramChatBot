"""
Telegram Bot Menu Button Tests (Improved)

This module contains automated tests for Telegram bot menu button interactions using Telethon.
It tests the functionality of various menu buttons and navigation flows in a Telegram bot.

Improvements:
- Uses string constants for UI text and expected responses (language-agnostic).
- Employs helper functions to reduce code duplication.
- Uses a polling wait mechanism (_wait_for_bot_response) instead of fixed sleeps for robustness.
- Includes type hinting and clearer assertions.

Requirements:
- Python 3.7+
- pytest
- pytest-asyncio
- telethon
- python-dotenv
- Your bot_modules (strings_en, strings_es)

Environment variables (in .env file):
- TELEGRAM_API_ID: Your Telegram API ID (integer)
- TELEGRAM_API_HASH: Your Telegram API hash (string)
- TELEGRAM_PHONE: Your phone number in international format
- TELEGRAM_BOT_USERNAME: Username of the bot to test
- BOT_LANGUAGE: 'english' or 'spanish' (optional, defaults to english)

Before running:
1. Create a .env file with the required environment variables.
2. Run auth_telethon.py or ensure a valid Telethon session file exists.
3. Ensure the bot is running and accessible.
4. Verify constants in strings_en.py/strings_es.py match your bot's actual text.

Usage:
    PYTHONPATH=$PYTHONPATH:. pytest test_bot_e2e.py -v
    pytest test_menu_buttons.py -v --asyncio-mode=auto
"""
import asyncio
import os
import pytest
import pytest_asyncio
import logging
import sys
from typing import List, Optional, Tuple, Callable, Any

from telethon import TelegramClient
from telethon.tl.custom import Button, Message
from telethon.tl.types import PeerUser, TypeMessageMedia, TypeInputPeer
from telethon.errors import UserNotParticipantError, ChatWriteForbiddenError, PeerIdInvalidError
from dotenv import load_dotenv

# Ensure bot_modules is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- String Constants Setup ---
try:
    from bot_modules import strings_en, strings_es
except ImportError as e:
    print(f"Import error: {e}")
    print("Ensure 'bot_modules' directory with strings_en.py and strings_es.py exists.")
    print(f"Current sys.path: {sys.path}")
    # Provide dummy strings if import fails to allow script parsing,
    # but tests relying on 's' will fail.
    class DummyStrings:
        def __getattr__(self, name):
            print(f"Warning: Accessing undefined string constant '{name}'")
            return f"MISSING_STRING_{name}"
    strings_en = DummyStrings()
    strings_es = DummyStrings()
    # raise # Optional: re-raise if you want to halt execution

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
telethon_logger = logging.getLogger('telethon')
telethon_logger.setLevel(logging.WARNING) # Keep Telethon logs less verbose unless debugging

# --- Environment and Config ---
load_dotenv()

BOT_LANGUAGE = os.getenv('BOT_LANGUAGE', 'english').lower()
s = strings_es if BOT_LANGUAGE == 'spanish' else strings_en
logger.info(f"Using language strings: {'Spanish' if BOT_LANGUAGE == 'spanish' else 'English'}")

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
PHONE = os.getenv("TELEGRAM_PHONE", "")
BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "")
if BOT_USERNAME and not BOT_USERNAME.startswith('@'):
    BOT_USERNAME = '@' + BOT_USERNAME
SESSION_NAME = "menu_test_session"

# Fallback Bot ID (replace with your actual ID if needed)
BOT_ID = 8166772639 # Example ID, replace if necessary

# Global variable for resolved bot entity (optimization)
BOT_ENTITY: Optional[TypeInputPeer] = None

# Default wait time for responses
DEFAULT_WAIT_TIME = 5 # seconds
LONG_WAIT_TIME = 15 # seconds for potentially slow operations like AI processing

REQUIRED_CONSTANTS = [
    "BUTTON_VIEW_DATA",
    "CALLBACK_DATA_SUMMARY_HEADER", # Use this header as a reliable indicator
    "BUTTON_BACK_MAIN_MENU",
]

# Skip tests if essential credentials are missing
pytestmark = pytest.mark.skipif(
    not all([API_ID, API_HASH, PHONE, BOT_USERNAME]),
    reason="Telegram credentials (API_ID, API_HASH, PHONE, BOT_USERNAME) not found in environment variables"
)

# --- Fixtures ---
@pytest_asyncio.fixture(scope="function")
async def telegram_client():
    """Creates and connects a Telethon client for each test function."""
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH, request_retries=3)
    logger.info("Connecting Telethon client...")
    try:
        await client.connect()
    except Exception as e:
        logger.error(f"Failed to connect client: {e}")
        pytest.fail(f"Client connection failed: {e}")

    if not await client.is_user_authorized():
        logger.error("User is not authorized. Run authentication script first.")
        await client.disconnect()
        pytest.skip("Telethon authentication required")

    # Resolve bot entity once per session if not already done
    global BOT_ENTITY
    if BOT_ENTITY is None:
        logger.info(f"Attempting to resolve bot entity for {BOT_USERNAME}...")
        try:
            BOT_ENTITY = await client.get_entity(BOT_USERNAME)
            logger.info(f"Successfully resolved bot entity: ID={BOT_ENTITY.id}")
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not resolve bot username '{BOT_USERNAME}': {e}. Falling back to BOT_ID: {BOT_ID}")
            # Keep BOT_ENTITY as None, will use BOT_ID later
        except Exception as e:
            logger.error(f"Unexpected error resolving bot entity: {e}")
            # Fallback strategy might still work
            pass # Continue and try with BOT_ID

    yield client

    logger.info("Disconnecting Telethon client...")
    await client.disconnect()

# --- Helper Functions ---

async def _get_bot_target(client: TelegramClient) -> TypeInputPeer:
    """Gets the bot entity or constructs a PeerUser from BOT_ID."""
    if BOT_ENTITY:
        return BOT_ENTITY
    elif BOT_ID:
        logger.debug(f"Using fallback BOT_ID: {BOT_ID}")
        try:
            # Try resolving ID just in case it works now
            return await client.get_entity(PeerUser(BOT_ID))
        except Exception:
            logger.warning(f"Could not resolve PeerUser for BOT_ID {BOT_ID}, using raw ID.")
            return PeerUser(BOT_ID) # Return PeerUser object directly
    else:
        pytest.fail("Bot target could not be determined (no BOT_ENTITY or BOT_ID).")


def _find_message_with_buttons(messages: List[Message]) -> Optional[Message]:
    """Finds the most recent message with buttons in a list."""
    for msg in reversed(messages): # Check newest first
        if msg.buttons:
            return msg
    return None

def _find_button_by_text(message: Message, text: str) -> Optional[Button]:
    """Finds a button by its exact text within a message."""
    if not message or not message.buttons:
        return None
    for row in message.buttons:
        for button in row:
            if button.text == text:
                return button
    return None

def _find_message_containing(messages: List[Message], text_fragments: List[str], case_sensitive=False) -> Optional[Message]:
    """Finds the most recent message containing ALL text fragments."""
    for msg in reversed(messages): # Check newest first
        if msg.text:
            text_to_check = msg.text if case_sensitive else msg.text.lower()
            fragments_to_check = text_fragments if case_sensitive else [f.lower() for f in text_fragments]
            if all(fragment in text_to_check for fragment in fragments_to_check):
                return msg
    return None

async def _wait_for_bot_response(
    client: TelegramClient,
    bot_target: TypeInputPeer,
    condition_func: Callable[[List[Message]], Optional[Any]],
    timeout: int = 15,
    poll_interval: float = 1.0,
    limit: int = 5
) -> Optional[Any]:
    """
    Waits for a bot response that satisfies the condition function.

    Args:
        client: The connected TelegramClient.
        bot_target: The bot entity or peer.
        condition_func: A function that takes a list of recent messages
                        and returns a non-None value if the condition is met,
                        or None otherwise. The returned value is the result.
        timeout: Maximum time to wait in seconds.
        poll_interval: How often to check for new messages in seconds.
        limit: How many recent messages to fetch in each poll.

    Returns:
        The value returned by condition_func when the condition is met, or None if timed out.
    """
    # await asyncio.sleep(2)
    start_time = asyncio.get_event_loop().time()
    logger.debug(f"Waiting (up to {timeout}s) for condition...")
    while asyncio.get_event_loop().time() - start_time < timeout:
        try:
            messages = await client.get_messages(bot_target, limit=limit)
            if messages:
                result = condition_func(messages)
                if result is not None:
                    logger.debug(f"Condition met. Result: {str(result)[:100]}...")
                    return result
            else:
                logger.debug("No messages received yet...")
        except (UserNotParticipantError, ChatWriteForbiddenError, PeerIdInvalidError) as e:
             logger.error(f"Cannot get messages from bot: {e}")
             pytest.fail(f"Failed to get messages from bot: {e}")
        except Exception as e:
            logger.warning(f"Error fetching messages during wait: {e}")
            # Decide if this should be fatal or just logged

        await asyncio.sleep(poll_interval)

    logger.warning(f"Timed out after {timeout}s waiting for condition.")
    return None


# --- Test Cases ---

@pytest.mark.asyncio
async def test_main_menu(telegram_client: TelegramClient):
    """Test that the main menu appears with expected buttons after /start."""
    bot_target = await _get_bot_target(telegram_client)
    await telegram_client.send_message(bot_target, "/start")

    # Wait for a message with buttons
    menu_message = await _wait_for_bot_response(
        telegram_client,
        bot_target,
        lambda msgs: _find_message_with_buttons(msgs),
        timeout=DEFAULT_WAIT_TIME
    )

    assert menu_message is not None, "No menu with buttons received after /start"
    logger.info(f"Received main menu message ID: {menu_message.id}")

    # Verify expected buttons exist
    button_texts = [btn.text for row in menu_message.buttons for btn in row]
    logger.info(f"Found buttons: {button_texts}")

    expected_buttons = [s.BUTTON_VIEW_DATA, s.BUTTON_DELETE_DATA, s.BUTTON_EDIT_MESSAGES]
    for expected in expected_buttons:
        assert expected in button_texts, f"Expected main menu button '{expected}' not found"

@pytest.mark.asyncio
async def test_delete_my_data(telegram_client: TelegramClient):
    """Test the complete 'Delete My Data' flow including confirmation."""
    bot_target = await _get_bot_target(telegram_client)

    # 1. Get Main Menu
    await telegram_client.send_message(bot_target, "/start")
    main_menu = await _wait_for_bot_response(
        telegram_client, bot_target, _find_message_with_buttons, timeout=DEFAULT_WAIT_TIME
    )
    assert main_menu is not None, "Main menu not received"

    # 2. Click 'Delete My Data'
    delete_button = _find_button_by_text(main_menu, s.BUTTON_DELETE_DATA)
    assert delete_button is not None, f"Button '{s.BUTTON_DELETE_DATA}' not found in main menu"
    logger.info("Clicking Delete My Data button...")
    await delete_button.click()

    # 3. Wait for Confirmation Menu
    confirm_menu = await _wait_for_bot_response(
        telegram_client,
        bot_target,
        lambda msgs: _find_message_with_buttons(msgs) if _find_button_by_text(_find_message_with_buttons(msgs), s.BUTTON_CONFIRM_DELETE) else None,
        timeout=LONG_WAIT_TIME # Allow more time if DB operations are involved
    )
    assert confirm_menu is not None, "Confirmation menu with 'Yes' button not received"
    logger.info(f"Received confirmation menu message ID: {confirm_menu.id}")

    # 4. Click Confirmation ('Yes') Button
    yes_button = _find_button_by_text(confirm_menu, s.BUTTON_CONFIRM_DELETE)
    assert yes_button is not None, f"Button '{s.BUTTON_CONFIRM_DELETE}' not found in confirmation menu"
    logger.info("Clicking confirmation (Yes) button...")
    await yes_button.click()

    # 5. Wait for Deletion Confirmation Message
    # Extract the core part of the success message for checking
    # Example: "✅ Data deleted ({msg_del} msgs, {int_del} interactions)." -> "Data deleted"
    # Adjust this based on your actual s.CALLBACK_DELETE_SUCCESS_USER_MSG format
    try:
        # Basic extraction assuming format like "✅ Text..." or "Text..."
        success_msg_core = s.CALLBACK_DELETE_SUCCESS_USER_MSG.split('(')[0].strip().lstrip('✅').strip()
        if not success_msg_core: # Handle cases where extraction fails
             success_msg_core = "Data deleted" # Fallback check
             logger.warning("Could not reliably extract core part of delete success message, using fallback check.")
    except Exception:
        success_msg_core = "Data deleted" # Fallback on any error
        logger.warning("Error processing delete success message constant, using fallback check.")

    logger.info(f"Waiting for deletion confirmation message containing: '{success_msg_core}'")
    deletion_msg = await _wait_for_bot_response(
        telegram_client,
        bot_target,
        lambda msgs: _find_message_containing(msgs, [success_msg_core]),
        timeout=LONG_WAIT_TIME # Deletion might take time
    )

    assert deletion_msg is not None, f"Deletion confirmation message containing '{success_msg_core}' not received"
    logger.info(f"Received deletion confirmation: {deletion_msg.text[:100]}...")

@pytest.mark.asyncio
async def test_send_image_and_get_response(telegram_client: TelegramClient):
    """Test sending an image and verifying the processing and result messages."""
    bot_target = await _get_bot_target(telegram_client)

    # Verify test image exists
    if not hasattr(s, 'TEST_IMAGE_PATH') or not s.TEST_IMAGE_PATH:
         pytest.skip("s.TEST_IMAGE_PATH constant is not defined in strings file.")
    if not os.path.exists(s.TEST_IMAGE_PATH):
        pytest.skip(f"Test image not found at path defined in s.TEST_IMAGE_PATH: {s.TEST_IMAGE_PATH}")

    logger.info(f"Sending image: {s.TEST_IMAGE_PATH}")
    await telegram_client.send_file(bot_target, s.TEST_IMAGE_PATH, caption=s.TEST_IMAGE_CAPTION)

    # Wait for initial "Processing..." message
    processing_msg = await _wait_for_bot_response(
        telegram_client,
        bot_target,
        lambda msgs: _find_message_containing(msgs, [s.PHOTO_PROCESSING_USER_MSG]),
        timeout=DEFAULT_WAIT_TIME
    )
    assert processing_msg, f"Did not receive image processing message: '{s.PHOTO_PROCESSING_USER_MSG}'"
    logger.info("Received 'Processing...' message.")

    # Wait longer for the final analysis result header
    # Example: "Extracted Information:\n\n{result_text}" -> Check for "Extracted Information"
    try:
        # Basic extraction assuming format like "Header:\n\n..."
        result_header = s.PHOTO_EXTRACTED_INFO_USER_MSG.split('\n')[0].strip()
        if not result_header:
            result_header = "Extracted Information" # Fallback
            logger.warning("Could not reliably extract header from image result message, using fallback check.")
    except Exception:
        result_header = "Extracted Information" # Fallback
        logger.warning("Error processing image result message constant, using fallback check.")

    logger.info(f"Waiting for image analysis results header: '{result_header}'")
    analysis_header_msg = await _wait_for_bot_response(
        telegram_client,
        bot_target,
        lambda msgs: _find_message_containing(msgs, [result_header]),
        timeout=LONG_WAIT_TIME * 2 # AI processing can be slow
    )
    assert analysis_header_msg, f"Did not receive image analysis results header: '{result_header}'"
    logger.info("Received analysis result header.")

    # Verify analysis contains *some* expected content (check across recent messages)
    messages = await telegram_client.get_messages(bot_target, limit=5) # Fetch again to be sure
    found_expected_content = False
    expected_data_fragments = [
        s.TEST_EXPECTED_NAME.lower(),
        s.TEST_EXPECTED_FIRST_NAME.lower(),
        # s.TEST_EXPECTED_TITLE.lower() # Add more specific checks if needed
    ]
    for msg in messages:
        if msg.text:
            text_lower = msg.text.lower()
            if any(frag in text_lower for frag in expected_data_fragments):
                 found_expected_content = True
                 logger.info(f"Found expected content fragment in message: {msg.text[:100]}...")
                 break

    assert found_expected_content, (
        f"Bot did not provide analysis containing expected content fragments like '{s.TEST_EXPECTED_NAME}'. "
        f"Last messages: {[m.text[:50] + '...' if m.text else '[NoText/Media]' for m in messages]}"
    )
    logger.info("Image processing test completed successfully.")

@pytest.mark.asyncio
async def test_view_my_data_button_basic(telegram_client):
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
async def test_view_my_data_button_complex(telegram_client: TelegramClient):
    """Test clicking 'View My Data', verifying data display, and using the 'Back' button."""

    # Check if required string constants are defined
    missing_constants = [c for c in REQUIRED_CONSTANTS if not hasattr(s, c) or not getattr(s, c)]
    if missing_constants:
        pytest.skip(f"Missing required string constants in strings file: {', '.join(missing_constants)}")

    bot_target = await _get_bot_target(telegram_client)
    logger.info(f"--- Starting test_view_my_data_button for target: {bot_target} ---")

    # 1. Get Main Menu
    logger.info("Sending /start to get main menu...")
    await telegram_client.send_message(bot_target, "/start")

    # --- DIAGNOSTIC SLEEP ---
    logger.info("Pausing for 2 seconds after sending /start before waiting for menu...")
    # await asyncio.sleep(2)
    # return
    # --- END DIAGNOSTIC SLEEP ---

    logger.info("Now waiting for main menu response...")
    main_menu = await _wait_for_bot_response(
        telegram_client, bot_target, _find_message_with_buttons, timeout=DEFAULT_WAIT_TIME
    )
    assert main_menu is not None, "Main menu message with buttons not received after /start and sleep"
    logger.info(f"Received main menu message ID: {main_menu.id}")

    # --- Optional: Add another short pause BEFORE clicking ---
    # logger.info("Pausing briefly before clicking View My Data...")
    # await asyncio.sleep(0.5)
    # ---

    # 2. Find and Click 'View My Data' Button
    view_button = _find_button_by_text(main_menu, s.BUTTON_VIEW_DATA)
 
    assert view_button is not None, f"Button '{s.BUTTON_VIEW_DATA}' not found in main menu"
    logger.info(f"Clicking '{s.BUTTON_VIEW_DATA}' button (on msg ID: {main_menu.id})...")
    # Use the message object associated with the button to click
    await main_menu.click(text=view_button.text)
    # Alternative if clicking button directly fails sometimes:
    # await view_button.click() # Less reliable if button object gets detached

    # 3. Wait for Data Display (Handles both Edited Message and New Message)
    logger.info(f"Waiting for data display (expecting text containing '{s.CALLBACK_DATA_SUMMARY_HEADER}' and button '{s.BUTTON_BACK_MAIN_MENU}')...")

    def find_data_message_condition(msgs: List[Message]) -> Optional[Message]:
        logger.debug(f"Checking {len(msgs)} messages for data display...")
        for msg in reversed(msgs):
            is_edited_original = msg.id == main_menu.id and msg.edit_date is not None
            is_new_message = msg.id != main_menu.id
            logger.debug(f"  Checking msg ID {msg.id}: IsEditedOriginal={is_edited_original}, IsNew={is_new_message}")

            if (is_edited_original or is_new_message) and msg.text:
                logger.debug(f"    Msg ID {msg.id} has text. Checking content...")
                # Check for a reliable header/indicator for data display
                if s.CALLBACK_DATA_SUMMARY_HEADER in msg.text:
                    logger.debug(f"      Msg ID {msg.id} contains header '{s.CALLBACK_DATA_SUMMARY_HEADER}'. Checking for back button...")
                    # Check if the back button is present
                    if _find_button_by_text(msg, s.BUTTON_BACK_MAIN_MENU):
                        logger.debug(f"      Found data message (ID: {msg.id}, Edited: {is_edited_original})")
                        return msg
                    else:
                         logger.debug(f"      Msg ID {msg.id} has header but MISSING back button '{s.BUTTON_BACK_MAIN_MENU}'.")
                else:
                    logger.debug(f"      Msg ID {msg.id} does NOT contain header '{s.CALLBACK_DATA_SUMMARY_HEADER}'. Text preview: {msg.text[:50]}...")
            elif not msg.text:
                 logger.debug(f"    Msg ID {msg.id} has no text.")

        return None # Condition not met yet

    data_message = await _wait_for_bot_response(
        telegram_client,
        bot_target,
        find_data_message_condition,
        timeout=DEFAULT_WAIT_TIME + 5 # Slightly longer timeout for data retrieval
    )

    assert data_message is not None, (
        f"Did not receive data message containing header '{s.CALLBACK_DATA_SUMMARY_HEADER}' "
        f"and button '{s.BUTTON_BACK_MAIN_MENU}' after clicking '{s.BUTTON_VIEW_DATA}'. "
        f"Check bot logs and ensure it sends/edits the message correctly."
    )
    logger.info(f"Received data display message (ID: {data_message.id}, Original Menu Edited: {data_message.id == main_menu.id})")
    logger.info(f"Data message text (preview): {data_message.text[:100]}...")

    # 4. Find and Click 'Back to Main Menu' Button
    back_button = _find_button_by_text(data_message, s.BUTTON_BACK_MAIN_MENU)
    assert back_button is not None, f"'{s.BUTTON_BACK_MAIN_MENU}' button not found in the data message (ID: {data_message.id})"
    logger.info(f"Clicking '{s.BUTTON_BACK_MAIN_MENU}' button (on msg ID: {data_message.id})...")
    await data_message.click(text=back_button.text)

    # 5. Wait for Main Menu to Reappear (Handles both Edited Message and New Message)
    logger.info(f"Waiting for main menu to reappear (expecting button '{s.BUTTON_VIEW_DATA}')...")

    def find_returned_main_menu_condition(msgs: List[Message]) -> Optional[Message]:
        logger.debug(f"Checking {len(msgs)} messages for returned main menu...")
        for msg in reversed(msgs):
            # Check if it's the data message that got edited back
            is_edited_data_msg = msg.id == data_message.id and msg.edit_date is not None
            # Check if it's a completely new message (and not the data message itself before edit)
            is_new_menu_msg = msg.id != data_message.id
            logger.debug(f"  Checking msg ID {msg.id}: IsEditedDataMsg={is_edited_data_msg}, IsNewMenuMsg={is_new_menu_msg}")

            if (is_edited_data_msg or is_new_menu_msg) and msg.buttons:
                 logger.debug(f"    Msg ID {msg.id} has buttons. Checking for main menu button...")
                 # Check for a known main menu button
                 if _find_button_by_text(msg, s.BUTTON_VIEW_DATA): # Or another reliable main menu button
                    logger.debug(f"    Found returned main menu (ID: {msg.id}, Edited Data Msg: {is_edited_data_msg})")
                    return msg
                 else:
                    button_texts = [b.text for row in msg.buttons for b in row]
                    logger.debug(f"    Msg ID {msg.id} has buttons, but not '{s.BUTTON_VIEW_DATA}'. Buttons found: {button_texts}")
            elif not msg.buttons:
                 logger.debug(f"    Msg ID {msg.id} has no buttons.")

        return None # Condition not met yet

    returned_main_menu = await _wait_for_bot_response(
        telegram_client,
        bot_target,
        find_returned_main_menu_condition,
        timeout=DEFAULT_WAIT_TIME
    )

    assert returned_main_menu is not None, (
        f"Did not return to the main menu (containing button '{s.BUTTON_VIEW_DATA}') "
        f"after clicking '{s.BUTTON_BACK_MAIN_MENU}'. Check bot logs."
    )
    logger.info(f"Successfully returned to main menu (ID: {returned_main_menu.id}, Data Msg Edited: {returned_main_menu.id == data_message.id})")
    logger.info(f"--- Finished test_view_my_data_button ---")

@pytest.mark.asyncio
async def test_send_text_and_get_response(telegram_client: TelegramClient):
    """Test sending a specific text query and getting an expected response."""
    bot_target = await _get_bot_target(telegram_client)

    logger.info(f"Sending text query: '{s.TEST_TEXT_QUERY}'")
    await telegram_client.send_message(bot_target, s.TEST_TEXT_QUERY)

    # Wait for a response containing the expected name
    response_message = await _wait_for_bot_response(
        telegram_client,
        bot_target,
        lambda msgs: _find_message_containing(msgs, [s.TEST_EXPECTED_NAME]), # Check for name
        timeout=LONG_WAIT_TIME # Allow time for potential AI processing
    )

    assert response_message is not None, f"Bot did not respond with text containing '{s.TEST_EXPECTED_NAME}'"
    logger.info(f"Received expected response: {response_message.text[:100]}...")


# --- Commented Out Tests (Updated with String Constants) ---

# @pytest.mark.asyncio
# async def test_settings_submenu(telegram_client: TelegramClient):
#     """Test that the settings submenu appears when clicking Settings."""
#     # Assumption: You have constants like s.BUTTON_SETTINGS, s.BUTTON_PREFERENCES, s.BUTTON_BACK
#     if not all(hasattr(s, name) for name in ["BUTTON_SETTINGS", "BUTTON_PREFERENCES", "BUTTON_BACK"]):
#          pytest.skip("Required string constants (e.g., BUTTON_SETTINGS) not defined.")

#     bot_target = await _get_bot_target(telegram_client)

#     # 1. Get Main Menu
#     await telegram_client.send_message(bot_target, "/start")
#     main_menu = await _wait_for_bot_response(
#         telegram_client, bot_target, _find_message_with_buttons, timeout=DEFAULT_WAIT_TIME
#     )
#     assert main_menu is not None, "Main menu not received"

#     # 2. Click 'Settings'
#     settings_button = _find_button_by_text(main_menu, s.BUTTON_SETTINGS) # Assumes s.BUTTON_SETTINGS exists
#     assert settings_button is not None, f"Button '{s.BUTTON_SETTINGS}' not found in main menu"
#     logger.info("Clicking Settings button...")
#     await settings_button.click()

#     # 3. Wait for Settings Submenu
#     settings_submenu = await _wait_for_bot_response(
#         telegram_client,
#         bot_target,
#         lambda msgs: next((msg for msg in reversed(msgs)
#                            if msg.buttons and msg.id != main_menu.id # New message with buttons
#                            and _find_button_by_text(msg, s.BUTTON_PREFERENCES) # Check for expected submenu button
#                            and _find_button_by_text(msg, s.BUTTON_BACK)), None), # Check for back button
#         timeout=DEFAULT_WAIT_TIME
#     )

#     assert settings_submenu is not None, "Settings submenu with expected buttons not received"
#     logger.info(f"Received settings submenu message ID: {settings_submenu.id}")

#     # Verify expected buttons
#     button_texts = [btn.text for row in settings_submenu.buttons for btn in row]
#     logger.info(f"Settings submenu buttons: {button_texts}")
#     expected_submenu_buttons = [s.BUTTON_PREFERENCES, s.BUTTON_BACK] # Assumes these constants exist
#     for expected in expected_submenu_buttons:
#         assert expected in button_texts, f"Expected submenu button '{expected}' not found"

# @pytest.mark.asyncio
# async def test_back_button(telegram_client: TelegramClient):
#     """Test that the Back button returns to the main menu from a submenu."""
#     # Assumption: Uses constants from test_settings_submenu and main menu
#     if not all(hasattr(s, name) for name in ["BUTTON_SETTINGS", "BUTTON_PREFERENCES", "BUTTON_BACK", "BUTTON_VIEW_DATA"]):
#          pytest.skip("Required string constants (e.g., BUTTON_SETTINGS, BUTTON_BACK) not defined.")

#     bot_target = await _get_bot_target(telegram_client)

#     # 1. Navigate to Settings Submenu (steps from previous test)
#     await telegram_client.send_message(bot_target, "/start")
#     main_menu = await _wait_for_bot_response(
#         telegram_client, bot_target, _find_message_with_buttons, timeout=DEFAULT_WAIT_TIME
#     )
#     assert main_menu is not None, "Main menu not received"
#     settings_button = _find_button_by_text(main_menu, s.BUTTON_SETTINGS)
#     assert settings_button is not None, f"Button '{s.BUTTON_SETTINGS}' not found"
#     await settings_button.click()
#     settings_submenu = await _wait_for_bot_response(
#         telegram_client, bot_target,
#         lambda msgs: next((msg for msg in reversed(msgs) if msg.buttons and msg.id != main_menu.id and _find_button_by_text(msg, s.BUTTON_BACK)), None),
#         timeout=DEFAULT_WAIT_TIME
#     )
#     assert settings_submenu is not None, "Settings submenu not received"

#     # 2. Click 'Back' button
#     back_button = _find_button_by_text(settings_submenu, s.BUTTON_BACK) # Assumes s.BUTTON_BACK exists
#     assert back_button is not None, f"Button '{s.BUTTON_BACK}' not found in submenu"
#     logger.info("Clicking Back button from submenu...")
#     await back_button.click()

#     # 3. Wait for Main Menu to reappear
#     returned_main_menu = await _wait_for_bot_response(
#         telegram_client,
#         bot_target,
#         lambda msgs: next((msg for msg in reversed(msgs)
#                            if msg.buttons and msg.id != settings_submenu.id # New message
#                            and _find_button_by_text(msg, s.BUTTON_VIEW_DATA)), None), # Check for main menu button
#         timeout=DEFAULT_WAIT_TIME
#     )

#     assert returned_main_menu is not None, "Did not return to the main menu after clicking 'Back'"
#     logger.info("Successfully returned to main menu from submenu.")