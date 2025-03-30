import asyncio
import os
import pytest
import pytest_asyncio
from telethon import TelegramClient
from telethon.tl.custom import Button
from telethon.errors import SessionPasswordNeededError, FloodWaitError # Import FloodWaitError
from dotenv import load_dotenv
from telethon import utils
# Assuming strings module is accessible relative to tests or installed
# If tests are run from root, this might work:
try:
    from bot_modules import strings as s
except ImportError:
    # Fallback if running tests differently, define minimal strings here or adjust path
    class s: # Minimal fallback
        TEST_SESSION_NAME = "telegram_test_session"
        TEST_DEFAULT_IMAGE_PATH = "/Users/claudiograsso/Documents/code/telegram_bot_webhook/images/cadorna.jpeg"
        TEST_MISSING_ENV_VARS = "Missing one or more Telegram environment variables (TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE, TELEGRAM_BOT_USERNAME)"
        TEST_INVALID_API_ID = "TELEGRAM_API_ID must be an integer."
        TEST_INIT_CLIENT = "\nInitializing Telegram client..."
        TEST_CONNECTING = "Connecting to Telegram..."
        TEST_CONNECTION_FINISHED = "Connection attempt finished."
        TEST_USER_NOT_AUTHORIZED = "User not authorized. Sending code request..."
        TEST_ENTER_CODE = "Enter the code you received: "
        TEST_SIGNED_IN_SUCCESS = "Signed in successfully."
        TEST_PASSWORD_PROMPT = "Two-step verification enabled. Please enter your password: "
        TEST_SIGNED_IN_PASSWORD_SUCCESS = "Signed in successfully with password."
        TEST_FLOOD_WAIT_ERROR = "FloodWaitError during login: Telegram requires waiting {seconds} seconds. Delete '{session_name}.session' and wait before retrying. Error: {error}"
        TEST_SIGN_IN_FAILED = "Failed to sign in: {error}"
        TEST_USER_AUTHORIZED = "User already authorized."
        TEST_INIT_CONNECT_FAILED = "Failed to initialize or connect Telegram client: {error}"
        TEST_DISCONNECTING = "\nDisconnecting Telegram client..."
        TEST_DISCONNECTED = "Client disconnected."
        TEST_START_COMMAND_LOG = "\nTesting /start command with bot: {bot_username}"
        TEST_SENT_START = "Sent /start command."
        TEST_RECEIVED_RESPONSE_LOG = "Received response: {text_preview}..."
        TEST_ASSERT_WELCOME_RECEIVED = "Assertion passed: Welcome message received."
        TEST_TIMEOUT_START = "Timeout: Did not receive a response from the bot for /start."
        TEST_ERROR_START = "An error occurred during /start test: {error}"
        TEST_HELP_COMMAND_LOG = "\nTesting /help command with bot: {bot_username}"
        TEST_SENT_HELP = "Sent /help command."
        TEST_ASSERT_HELP_RECEIVED = "Assertion passed: Help message received."
        TEST_TIMEOUT_HELP = "Timeout: Did not receive a response from the bot for /help."
        TEST_ERROR_HELP = "An error occurred during /help test: {error}"
        TEST_INLINE_BUTTON_LOG = "\nTesting inline button interaction with bot: {bot_username}"
        TEST_SENT_INLINE_TRIGGER = "Sent command to trigger inline keyboard."
        TEST_RECEIVED_BUTTON_MSG_LOG = "Received message with buttons: {text_preview}..."
        TEST_SKIP_NO_BUTTONS = "Bot did not reply with inline buttons on /start. Skipping button test."
        TEST_FOUND_BUTTONS = "Found buttons in the response."
        TEST_SKIP_NO_CALLBACK_BUTTON = "Could not find a suitable callback button to click. Found: {button}"
        TEST_CLICKING_BUTTON_LOG = "Clicking button with text: '{text}' and data: '{data}'"
        TEST_MESSAGE_EDITED_LOG = "Message edited after button click. New text: {text_preview}..."
        TEST_ASSERT_MESSAGE_EDITED = "Assertion passed: Message edited as expected."
        TEST_NEW_MESSAGE_LOG = "Received new message after button click: {text_preview}..."
        TEST_ASSERT_NEW_MESSAGE = "Assertion passed: New message received as expected."
        TEST_NO_NEW_MESSAGE = "No new message received after button click (within 5s)."
        TEST_FAIL_NO_EXPECTED_ACTION = "Button click did not result in an expected message edit or a new message."
        TEST_TIMEOUT_BUTTON = "Timeout: Did not receive a response or button interaction timed out."
        TEST_ATTRIBUTE_ERROR_CLICK = "The received message object doesn't support the '.click()' method. Ensure the button is a Callback Button and Telethon version is compatible."
        TEST_ATTRIBUTE_ERROR_GENERIC = "An AttributeError occurred: {error}"
        TEST_ERROR_INLINE_BUTTON = "An error occurred during inline button test: {error}"
        TEST_IMAGE_UPLOAD_LOG = "\nTesting image upload and processing with bot: {bot_username}"
        TEST_IMAGE_NOT_FOUND = "Test image not found at: {path}. Please set TEST_IMAGE_PATH environment variable."
        TEST_UPLOADING_IMAGE_LOG = "Uploading image: {path}..."
        TEST_IMAGE_SENT = "Image sent."
        TEST_LOOKING_FOR_BUTTON_LOG = "Looking for message with button text: '{text}'..."
        TEST_CHECKING_MESSAGE_LOG = "Checking message ID {message_id} from bot for buttons..."
        TEST_FOUND_BUTTON_LOG = "Found button '{text}' in message {message_id}."
        TEST_FAIL_BUTTON_NOT_FOUND = "Could not find message with button '{text}' after sending image."
        TEST_BUTTON_CLICKED = "Button clicked."
        TEST_ERROR_CLICKING_BUTTON = "Error clicking button: {error}"
        TEST_WAITING_FOR_CONFIRMATION = "Waiting for bot's processing confirmation message..."
        TEST_CHECKING_BOT_MESSAGE_LOG = "Checking bot message ID {message_id}: '{text_preview}...'";
        TEST_FOUND_EXPECTED_RESPONSE = "Found expected response text!"
        TEST_FAIL_EXPECTED_RESPONSE_NOT_FOUND = "Did not find expected text '{text}' in bot's recent responses after clicking process button."
        TEST_ASSERT_CONFIRMATION_RECEIVED = "Assertion passed: Bot confirmation received."
        TEST_TIMEOUT_IMAGE_PROCESSING = "Timeout: Interaction sequence for image processing timed out."
        TEST_ERROR_IMAGE_UPLOAD = "An error occurred during image upload/process test: {error}"


# Load environment variables from .env file
load_dotenv()

# Read credentials from environment variables
api_id = os.getenv("TELEGRAM_API_ID")
api_hash = os.getenv("TELEGRAM_API_HASH")
phone = os.getenv("TELEGRAM_PHONE")
bot_username = os.getenv("TELEGRAM_BOT_USERNAME")
TEST_IMAGE_PATH = os.getenv("TEST_IMAGE_PATH", s.TEST_DEFAULT_IMAGE_PATH) # Default path if not set
TEST_TIMEOUT = int(os.getenv("TEST_TIMEOUT", "30")) # Default timeout in seconds

# Basic validation
if not all([api_id, api_hash, phone, bot_username]):
    raise ValueError(s.TEST_MISSING_ENV_VARS)

# Convert api_id to integer
try:
    api_id = int(api_id)
except ValueError:
    raise ValueError(s.TEST_INVALID_API_ID)


# Use a unique session name for testing to avoid conflicts
session_name = s.TEST_SESSION_NAME

# Configure pytest-asyncio to use session scope for the loop
pytestmark = pytest.mark.asyncio(scope="session")

# Configure pytest-asyncio to use session scope for the loop
@pytest.fixture(scope="session")
def asyncio_default_fixture_loop_scope():
    return "session"

@pytest_asyncio.fixture(scope="session")
async def telegram_client():
    """Fixture to create and manage the Telegram client connection."""
    print(s.TEST_INIT_CLIENT)
    client = TelegramClient(session_name, api_id, api_hash)

    try:
        print(s.TEST_CONNECTING)
        await client.connect()
        print(s.TEST_CONNECTION_FINISHED)

        if not await client.is_user_authorized():
            print(s.TEST_USER_NOT_AUTHORIZED)
            try:
                await client.send_code_request(phone)
                code = input(s.TEST_ENTER_CODE)
                await client.sign_in(phone, code)
                print(s.TEST_SIGNED_IN_SUCCESS)
            except SessionPasswordNeededError:
                password = input(s.TEST_PASSWORD_PROMPT)
                await client.sign_in(password=password)
                print(s.TEST_SIGNED_IN_PASSWORD_SUCCESS)
            except FloodWaitError as e:
                pytest.fail(s.TEST_FLOOD_WAIT_ERROR.format(seconds=e.seconds, session_name=session_name, error=e))
            except Exception as e:
                pytest.fail(s.TEST_SIGN_IN_FAILED.format(error=e))
        else:
            print(s.TEST_USER_AUTHORIZED)

        yield client

    except Exception as e:
        pytest.fail(s.TEST_INIT_CONNECT_FAILED.format(error=e))
    finally:
        print(s.TEST_DISCONNECTING)
        await client.disconnect()
        print(s.TEST_DISCONNECTED)
        # --- DO NOT DELETE SESSION FILES ---
        # Let the session persist to avoid re-login and FloodWaitErrors
        # if os.path.exists(f"{session_name}.session"):
        #     os.remove(f"{session_name}.session")
        #     print(f"Removed {session_name}.session")
        # if os.path.exists(f"{session_name}.session-journal"):
        #     os.remove(f"{session_name}.session-journal")
        #     print(f"Removed {session_name}.session-journal")


@pytest.mark.asyncio
async def test_start_command(telegram_client):
    """Test the /start command and expect a welcome message."""
    print(s.TEST_START_COMMAND_LOG.format(bot_username=bot_username))
    async with telegram_client.conversation(bot_username, timeout=10) as conv:
        try:
            # Send the /start command
            await conv.send_message("/start")
            print(s.TEST_SENT_START)

            # Wait for the response
            response = await conv.get_response()
            print(s.TEST_RECEIVED_RESPONSE_LOG.format(text_preview=response.text[:100])) # Log truncated response

            # Assert that the response contains expected text
            assert "Welcome" in response.text or "Choose an option" in response.text # Adjust based on your bot's actual welcome message
            print(s.TEST_ASSERT_WELCOME_RECEIVED)

        except asyncio.TimeoutError:
            pytest.fail(s.TEST_TIMEOUT_START)
        except Exception as e:
            pytest.fail(s.TEST_ERROR_START.format(error=e))


@pytest.mark.asyncio
async def test_help_command(telegram_client):
    """Test the /help command and expect a help message."""
    print(s.TEST_HELP_COMMAND_LOG.format(bot_username=bot_username))
    async with telegram_client.conversation(bot_username, timeout=10) as conv:
        try:
            # Send the /help command
            await conv.send_message("/help")
            print(s.TEST_SENT_HELP)

            # Wait for the response
            response = await conv.get_response()
            print(s.TEST_RECEIVED_RESPONSE_LOG.format(text_preview=response.text[:100])) # Log truncated response

            # Assert that the response contains expected text (adjust as needed)
            assert "Here's how to use me" in response.text or "Available commands" in response.text
            print(s.TEST_ASSERT_HELP_RECEIVED)

        except asyncio.TimeoutError:
            pytest.fail(s.TEST_TIMEOUT_HELP)
        except Exception as e:
            pytest.fail(s.TEST_ERROR_HELP.format(error=e))


@pytest.mark.asyncio
async def test_inline_button_interaction(telegram_client):
    """Test interaction with an inline button, if the bot uses them."""
    print(s.TEST_INLINE_BUTTON_LOG.format(bot_username=bot_username))
    async with telegram_client.conversation(bot_username, timeout=TEST_TIMEOUT) as conv: # Use configurable timeout
        try:
            # Send a command that triggers an inline keyboard (e.g., /start or a specific command)
            # Adjust this command based on your bot's functionality
            await conv.send_message("/start") # Assuming /start shows buttons
            print(s.TEST_SENT_INLINE_TRIGGER)

            # Get the message with the inline keyboard
            response_with_buttons = await conv.get_response()
            print(s.TEST_RECEIVED_BUTTON_MSG_LOG.format(text_preview=response_with_buttons.text[:100]))

            # Check if there are buttons
            if not response_with_buttons.buttons:
                pytest.skip(s.TEST_SKIP_NO_BUTTONS)
                return # Exit the test function

            print(s.TEST_FOUND_BUTTONS)

            # Find a specific button to click (e.g., the first one)
            # This assumes a simple layout. Adjust if needed.
            button_to_click = None
            if response_with_buttons.buttons:
                # Buttons can be nested in rows (list of lists)
                for row in response_with_buttons.buttons:
                    if row: # Check if row is not empty
                        button_to_click = row[0] # Click the first button in the first non-empty row
                        break

            if not button_to_click or not isinstance(button_to_click, Button.Callback):
                 pytest.skip(s.TEST_SKIP_NO_CALLBACK_BUTTON.format(button=button_to_click))
                 return

            print(s.TEST_CLICKING_BUTTON_LOG.format(text=button_to_click.text, data=button_to_click.data))

            # Click the button using its callback data
            # The result of clicking a callback button is often an edit to the original message
            # or a new message. We'll wait for an event.
            click_result = await response_with_buttons.click(data=button_to_click.data)

            # Option 1: Check if the original message was edited (common pattern)
            # We might need to wait a bit for the edit to propagate
            await asyncio.sleep(2) # Small delay
            edited_message = await telegram_client.get_messages(bot_username, ids=response_with_buttons.id)
            if edited_message and edited_message.text != response_with_buttons.text:
                 print(s.TEST_MESSAGE_EDITED_LOG.format(text_preview=edited_message.text[:100]))
                 # Add assertions based on the expected edited content
                 assert any(text in edited_message.text for text in ["You clicked", "Option selected", "Selected", "Chosen"]) # More flexible assertion
                 print(s.TEST_ASSERT_MESSAGE_EDITED)
                 return # Test successful

            # Option 2: Check if a new message was sent in response to the click
            # This might require getting the next response in the conversation
            try:
                new_response = await conv.get_response(timeout=5) # Shorter timeout for follow-up
                print(s.TEST_NEW_MESSAGE_LOG.format(text_preview=new_response.text[:100]))
                # Add assertions based on the expected new message content
                assert any(text in new_response.text for text in ["Action confirmed", "Confirmed", "Selected", "Processed"]) # More flexible assertion
                print(s.TEST_ASSERT_NEW_MESSAGE)
                return # Test successful
            except asyncio.TimeoutError:
                 print(s.TEST_NO_NEW_MESSAGE)


            # If neither an edit nor a new message was detected as expected
            pytest.fail(s.TEST_FAIL_NO_EXPECTED_ACTION)


        except asyncio.TimeoutError:
            pytest.fail(s.TEST_TIMEOUT_BUTTON)
        except AttributeError as e:
             if "'Message' object has no attribute 'click'" in str(e):
                 pytest.fail(s.TEST_ATTRIBUTE_ERROR_CLICK)
             else:
                 pytest.fail(s.TEST_ATTRIBUTE_ERROR_GENERIC.format(error=e))
        except Exception as e:
            pytest.fail(s.TEST_ERROR_INLINE_BUTTON.format(error=e))

# Add more test cases as needed for other commands or interactions


@pytest.mark.asyncio
async def test_image_upload_and_process(telegram_client):
    """Test uploading an image and clicking a button to process it."""
    print(s.TEST_IMAGE_UPLOAD_LOG.format(bot_username=bot_username))

    # --- Configuration for this test ---
    # Get button text and expected response from environment variables with fallbacks
    BUTTON_TEXT_TO_CLICK = os.getenv("TEST_BUTTON_TEXT", "Process Image")
    EXPECTED_RESPONSE_TEXT = os.getenv("TEST_EXPECTED_RESPONSE", "Extracted Information")
    # ---

    # 1. Check if the test image exists
    if not os.path.exists(TEST_IMAGE_PATH):
        pytest.fail(s.TEST_IMAGE_NOT_FOUND.format(path=TEST_IMAGE_PATH))

    # Use a conversation for potentially cleaner interaction, though not strictly necessary for just sending/clicking
    async with telegram_client.conversation(bot_username, timeout=TEST_TIMEOUT) as conv: # Use configurable timeout
        try:
            # 2. Send the image file
            print(s.TEST_UPLOADING_IMAGE_LOG.format(path=TEST_IMAGE_PATH))
            await conv.send_file(
                TEST_IMAGE_PATH,
                caption="E2E Test: Please process this image." # Keep caption simple
            )
            print(s.TEST_IMAGE_SENT)

            # 3. Wait briefly and look for the message containing the button
            #    Assumption: The bot sends a *new* message with the button after receiving the image,
            #    or maybe edits a status message. We'll look for a new message first.
            await asyncio.sleep(3) # Give bot time to respond with button message

            print(s.TEST_LOOKING_FOR_BUTTON_LOG.format(text=BUTTON_TEXT_TO_CLICK))
            button_message = None
            button_to_click = None # Initialize button_to_click here
            clicked = False

            # Check recent messages for the button
            async for message in telegram_client.iter_messages(bot_username, limit=5):
                # Ensure message is from the bot and has buttons
                # Check sender_id against bot's ID if possible, or just ensure it's not 'me'
                me = await telegram_client.get_me()
                if message.sender_id != me.id and message.buttons: # Message from bot with buttons
                    print(s.TEST_CHECKING_MESSAGE_LOG.format(message_id=message.id))
                    for row in message.buttons:
                        for button in row:
                            if isinstance(button, Button.Callback) and button.text == BUTTON_TEXT_TO_CLICK:
                                print(s.TEST_FOUND_BUTTON_LOG.format(text=BUTTON_TEXT_TO_CLICK, message_id=message.id))
                                button_message = message
                                button_to_click = button # Assign the found button
                                break
                        if button_message: break
                    if button_message: break

            if not button_message or not button_to_click:
                 # Fallback: Maybe the button is triggered by a command after upload?
                 # If your bot requires sending a command like /processlast after upload, add that here.
                 # Example:
                 # print("Button not found immediately after upload. Sending /process command...")
                 # await conv.send_message("/processlastimage") # Adjust command if needed
                 # response_with_buttons = await conv.get_response()
                 # ... find button in response_with_buttons ...

                 # If still no button found after potential command:
                 pytest.fail(s.TEST_FAIL_BUTTON_NOT_FOUND.format(text=BUTTON_TEXT_TO_CLICK))


            # 4. Click the button
            print(s.TEST_CLICKING_BUTTON_LOG.format(text=button_to_click.text, data=button_to_click.data))
            try:
                # Use the client directly to click the button on the specific message
                click_result = await button_message.click(data=button_to_click.data)
                # Or click by text if data is unreliable/unknown:
                # click_result = await button_message.click(text=BUTTON_TEXT_TO_CLICK)
                print(s.TEST_BUTTON_CLICKED)
                # Note: click_result might be None or a BotCallbackAnswer, not always useful for verification
            except Exception as e:
                pytest.fail(s.TEST_ERROR_CLICKING_BUTTON.format(error=e))


            # 5. Verify the bot's response after clicking
            print(s.TEST_WAITING_FOR_CONFIRMATION)
            await asyncio.sleep(min(TEST_TIMEOUT // 3, 10)) # Wait longer for potential image processing, but not too long

            found_response = False
            # Check recent messages again for the confirmation text
            async for message in telegram_client.iter_messages(bot_username, limit=10):
                 # Check messages from the bot only
                 me = await telegram_client.get_me() # Get 'me' again just in case
                 if message.sender_id != me.id and message.text:
                     print(s.TEST_CHECKING_BOT_MESSAGE_LOG.format(message_id=message.id, text_preview=message.text[:100]))
                     if EXPECTED_RESPONSE_TEXT in message.text:
                         print(s.TEST_FOUND_EXPECTED_RESPONSE)
                         found_response = True
                         break # Stop checking once found

            assert found_response, s.TEST_FAIL_EXPECTED_RESPONSE_NOT_FOUND.format(text=EXPECTED_RESPONSE_TEXT)
            print(s.TEST_ASSERT_CONFIRMATION_RECEIVED)


        except asyncio.TimeoutError:
            pytest.fail(s.TEST_TIMEOUT_IMAGE_PROCESSING)
        except Exception as e:
            pytest.fail(s.TEST_ERROR_IMAGE_UPLOAD.format(error=e))
