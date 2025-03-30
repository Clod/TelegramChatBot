import asyncio
import os
import pytest
import pytest_asyncio
from telethon import TelegramClient
from telethon.tl.custom import Button
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv
from telethon import utils

# Load environment variables from .env file
load_dotenv()

# Read credentials from environment variables
api_id = os.getenv("TELEGRAM_API_ID")
api_hash = os.getenv("TELEGRAM_API_HASH")
phone = os.getenv("TELEGRAM_PHONE")
bot_username = os.getenv("TELEGRAM_BOT_USERNAME")
TEST_IMAGE_PATH = os.getenv("TEST_IMAGE_PATH", "/Users/claudiograsso/Documents/code/telegram_bot_webhook/images/cadorna.jpeg") # Default path if not set

# Basic validation
if not all([api_id, api_hash, phone, bot_username]):
    raise ValueError(
        "Missing one or more Telegram environment variables "
        "(TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE, TELEGRAM_BOT_USERNAME)"
    )

# Convert api_id to integer
try:
    api_id = int(api_id)
except ValueError:
    raise ValueError("TELEGRAM_API_ID must be an integer.")


# Use a unique session name for testing to avoid conflicts
session_name = "telegram_test_session"

# Configure pytest-asyncio to use session scope for the loop
pytestmark = pytest.mark.asyncio(scope="session")

# Configure pytest-asyncio to use session scope for the loop
@pytest.fixture(scope="session")
def asyncio_default_fixture_loop_scope():
    return "session"

@pytest_asyncio.fixture(scope="session")
async def telegram_client():
    """Fixture to create and manage the Telegram client connection."""
    print("\nInitializing Telegram client...")
    client = TelegramClient(session_name, api_id, api_hash)

    try:
        print("Connecting to Telegram...")
        await client.connect()
        print("Connection attempt finished.")

        if not await client.is_user_authorized():
            print("User not authorized. Sending code request...")
            await client.send_code_request(phone)
            try:
                code = input("Enter the code you received: ")
                await client.sign_in(phone, code)
                print("Signed in successfully.")
            except SessionPasswordNeededError:
                password = input("Two-step verification enabled. Please enter your password: ")
                await client.sign_in(password=password)
                print("Signed in successfully with password.")
            except Exception as e:
                pytest.fail(f"Failed to sign in: {e}")
        else:
            print("User already authorized.")

        yield client

    except Exception as e:
        pytest.fail(f"Failed to initialize or connect Telegram client: {e}")
    finally:
        print("\nDisconnecting Telegram client...")
        await client.disconnect()
        print("Client disconnected.")
        # Clean up session files after tests run
        if os.path.exists(f"{session_name}.session"):
            os.remove(f"{session_name}.session")
            print(f"Removed {session_name}.session")
        if os.path.exists(f"{session_name}.session-journal"):
            os.remove(f"{session_name}.session-journal")
            print(f"Removed {session_name}.session-journal")


@pytest.mark.asyncio
async def test_start_command(telegram_client):
    """Test the /start command and expect a welcome message."""
    print(f"\nTesting /start command with bot: {bot_username}")
    async with telegram_client.conversation(bot_username, timeout=10) as conv:
        try:
            # Send the /start command
            await conv.send_message("/start")
            print("Sent /start command.")

            # Wait for the response
            response = await conv.get_response()
            print(f"Received response: {response.text[:100]}...") # Log truncated response

            # Assert that the response contains expected text
            assert "Welcome" in response.text or "Choose an option" in response.text # Adjust based on your bot's actual welcome message
            print("Assertion passed: Welcome message received.")

        except asyncio.TimeoutError:
            pytest.fail("Timeout: Did not receive a response from the bot for /start.")
        except Exception as e:
            pytest.fail(f"An error occurred during /start test: {e}")


@pytest.mark.asyncio
async def test_help_command(telegram_client):
    """Test the /help command and expect a help message."""
    print(f"\nTesting /help command with bot: {bot_username}")
    async with telegram_client.conversation(bot_username, timeout=10) as conv:
        try:
            # Send the /help command
            await conv.send_message("/help")
            print("Sent /help command.")

            # Wait for the response
            response = await conv.get_response()
            print(f"Received response: {response.text[:100]}...") # Log truncated response

            # Assert that the response contains expected text (adjust as needed)
            assert "Here's how to use me" in response.text or "Available commands" in response.text
            print("Assertion passed: Help message received.")

        except asyncio.TimeoutError:
            pytest.fail("Timeout: Did not receive a response from the bot for /help.")
        except Exception as e:
            pytest.fail(f"An error occurred during /help test: {e}")


@pytest.mark.asyncio
async def test_inline_button_interaction(telegram_client):
    """Test interaction with an inline button, if the bot uses them."""
    print(f"\nTesting inline button interaction with bot: {bot_username}")
    async with telegram_client.conversation(bot_username, timeout=20) as conv: # Increased timeout
        try:
            # Send a command that triggers an inline keyboard (e.g., /start or a specific command)
            # Adjust this command based on your bot's functionality
            await conv.send_message("/start") # Assuming /start shows buttons
            print("Sent command to trigger inline keyboard.")

            # Get the message with the inline keyboard
            response_with_buttons = await conv.get_response()
            print(f"Received message with buttons: {response_with_buttons.text[:100]}...")

            # Check if there are buttons
            if not response_with_buttons.buttons:
                pytest.skip("Bot did not reply with inline buttons on /start. Skipping button test.")
                return # Exit the test function

            print("Found buttons in the response.")

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
                 pytest.skip(f"Could not find a suitable callback button to click. Found: {button_to_click}")
                 return

            print(f"Clicking button with text: '{button_to_click.text}' and data: '{button_to_click.data}'")

            # Click the button using its callback data
            # The result of clicking a callback button is often an edit to the original message
            # or a new message. We'll wait for an event.
            click_result = await response_with_buttons.click(data=button_to_click.data)

            # Option 1: Check if the original message was edited (common pattern)
            # We might need to wait a bit for the edit to propagate
            await asyncio.sleep(2) # Small delay
            edited_message = await telegram_client.get_messages(bot_username, ids=response_with_buttons.id)
            if edited_message and edited_message.text != response_with_buttons.text:
                 print(f"Message edited after button click. New text: {edited_message.text[:100]}...")
                 # Add assertions based on the expected edited content
                 assert "You clicked" in edited_message.text or "Option selected" in edited_message.text # Adjust assertion
                 print("Assertion passed: Message edited as expected.")
                 return # Test successful

            # Option 2: Check if a new message was sent in response to the click
            # This might require getting the next response in the conversation
            try:
                new_response = await conv.get_response(timeout=5) # Shorter timeout for follow-up
                print(f"Received new message after button click: {new_response.text[:100]}...")
                # Add assertions based on the expected new message content
                assert "Action confirmed" in new_response.text # Adjust assertion
                print("Assertion passed: New message received as expected.")
                return # Test successful
            except asyncio.TimeoutError:
                 print("No new message received after button click (within 5s).")


            # If neither an edit nor a new message was detected as expected
            pytest.fail("Button click did not result in an expected message edit or a new message.")


        except asyncio.TimeoutError:
            pytest.fail("Timeout: Did not receive a response or button interaction timed out.")
        except AttributeError as e:
             if "'Message' object has no attribute 'click'" in str(e):
                 pytest.fail("The received message object doesn't support the '.click()' method. "
                             "Ensure the button is a Callback Button and Telethon version is compatible.")
             else:
                 pytest.fail(f"An AttributeError occurred: {e}")
        except Exception as e:
            pytest.fail(f"An error occurred during inline button test: {e}")

# Add more test cases as needed for other commands or interactions


@pytest.mark.asyncio
async def test_image_upload_and_process(telegram_client):
    """Test uploading an image and clicking a button to process it."""
    print(f"\nTesting image upload and processing with bot: {bot_username}")

    # --- Configuration for this test ---
    # *** Adjust BUTTON_TEXT_TO_CLICK based on your bot's actual button ***
    BUTTON_TEXT_TO_CLICK = "Process Image" # <--- !!! IMPORTANT: CHANGE THIS !!!
    # *** Adjust EXPECTED_RESPONSE_TEXT based on your bot's success message ***
    EXPECTED_RESPONSE_TEXT = "Image processed successfully" # <--- !!! IMPORTANT: CHANGE THIS !!!
    # ---

    # 1. Check if the test image exists
    if not os.path.exists(TEST_IMAGE_PATH):
        pytest.fail(f"Test image not found at: {TEST_IMAGE_PATH}. Please set TEST_IMAGE_PATH environment variable.")

    # Use a conversation for potentially cleaner interaction, though not strictly necessary for just sending/clicking
    async with telegram_client.conversation(bot_username, timeout=30) as conv: # Increased timeout for processing
        try:
            # 2. Send the image file
            print(f"Uploading image: {TEST_IMAGE_PATH}...")
            await conv.send_file(
                TEST_IMAGE_PATH,
                caption="E2E Test: Please process this image."
            )
            print("Image sent.")

            # 3. Wait briefly and look for the message containing the button
            #    Assumption: The bot sends a *new* message with the button after receiving the image,
            #    or maybe edits a status message. We'll look for a new message first.
            await asyncio.sleep(3) # Give bot time to respond with button message

            print(f"Looking for message with button text: '{BUTTON_TEXT_TO_CLICK}'...")
            button_message = None
            button_to_click = None # Initialize button_to_click here
            clicked = False

            # Check recent messages for the button
            async for message in telegram_client.iter_messages(bot_username, limit=5):
                # Ensure message is from the bot and has buttons
                # Check sender_id against bot's ID if possible, or just ensure it's not 'me'
                me = await telegram_client.get_me()
                if message.sender_id != me.id and message.buttons: # Message from bot with buttons
                    print(f"Checking message ID {message.id} from bot for buttons...")
                    for row in message.buttons:
                        for button in row:
                            if isinstance(button, Button.Callback) and button.text == BUTTON_TEXT_TO_CLICK:
                                print(f"Found button '{BUTTON_TEXT_TO_CLICK}' in message {message.id}.")
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
                 pytest.fail(f"Could not find message with button '{BUTTON_TEXT_TO_CLICK}' after sending image.")


            # 4. Click the button
            print(f"Clicking button with text: '{button_to_click.text}' and data: '{button_to_click.data}'")
            try:
                # Use the client directly to click the button on the specific message
                click_result = await button_message.click(data=button_to_click.data)
                # Or click by text if data is unreliable/unknown:
                # click_result = await button_message.click(text=BUTTON_TEXT_TO_CLICK)
                print("Button clicked.")
                # Note: click_result might be None or a BotCallbackAnswer, not always useful for verification
            except Exception as e:
                pytest.fail(f"Error clicking button: {e}")


            # 5. Verify the bot's response after clicking
            print("Waiting for bot's processing confirmation message...")
            await asyncio.sleep(10) # Wait longer for potential image processing

            found_response = False
            # Check recent messages again for the confirmation text
            async for message in telegram_client.iter_messages(bot_username, limit=5):
                 # Check messages from the bot only
                 me = await telegram_client.get_me() # Get 'me' again just in case
                 if message.sender_id != me.id and message.text:
                     print(f"Checking bot message ID {message.id}: '{message.text[:100]}...'")
                     if EXPECTED_RESPONSE_TEXT in message.text:
                         print("Found expected response text!")
                         found_response = True
                         break # Stop checking once found

            assert found_response, f"Did not find expected text '{EXPECTED_RESPONSE_TEXT}' in bot's recent responses after clicking process button."
            print("Assertion passed: Bot confirmation received.")


        except asyncio.TimeoutError:
            pytest.fail("Timeout: Interaction sequence for image processing timed out.")
        except Exception as e:
            pytest.fail(f"An error occurred during image upload/process test: {e}")
