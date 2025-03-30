import logging
import traceback
import json
import base64
import requests
import os
import re # Import re
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleAuthRequest
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from . import config # Use relative import

logger = logging.getLogger(__name__)

# --- Credential Management ---
def get_credentials_for_gemini():
    """Get authenticated credentials specifically for Gemini API"""
    logger.info("Attempting to get credentials for Gemini API...")
    try:
        if not config.SERVICE_ACCOUNT_FILE or not os.path.exists(config.SERVICE_ACCOUNT_FILE):
            logger.error(f"Service account file not found at path: {config.SERVICE_ACCOUNT_FILE}")
            return None
        scopes_to_try = [
            ["https://www.googleapis.com/auth/cloud-platform"],
            ["https://www.googleapis.com/auth/aiplatform"],
            ["https://www.googleapis.com/auth/generative-ai"]
        ]
        for scope in scopes_to_try:
            logger.info(f"Trying Gemini credentials with scope: {scope}")
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    config.SERVICE_ACCOUNT_FILE, scopes=scope)
                auth_req = GoogleAuthRequest()
                logger.info(f"Refreshing Gemini credentials with scope: {scope}")
                credentials.refresh(auth_req)
                if credentials.token:
                    token_preview = credentials.token[:10] + "..."
                    logger.info(f"Successfully obtained Gemini access token starting with: {token_preview}")
                    return credentials
                else:
                    logger.warning(f"No token obtained with scope: {scope}")
            except Exception as e:
                logger.warning(f"Failed to get token with scope {scope}: {str(e)}")
                continue
        logger.error("All Gemini API authentication attempts failed")
        return None
    except Exception as e:
        logger.error(f"Error getting Gemini credentials: {str(e)}")
        logger.error(traceback.format_exc()) # Log traceback
        return None

def get_credentials_for_google_apis(scopes):
    """Get authenticated credentials for Google APIs (Forms, Apps Script, etc.)"""
    logger.info("Attempting to get credentials for Google APIs...")
    try:
        if not config.SERVICE_ACCOUNT_FILE or not os.path.exists(config.SERVICE_ACCOUNT_FILE):
            logger.error(f"Service account file not found at path: {config.SERVICE_ACCOUNT_FILE}")
            return None
        logger.info(f"Requesting Google API credentials with scopes: {scopes}")
        credentials = service_account.Credentials.from_service_account_file(
            config.SERVICE_ACCOUNT_FILE, scopes=scopes)
        logger.info(f"Google API credentials object created from file: {config.SERVICE_ACCOUNT_FILE}")
        try:
            auth_req = GoogleAuthRequest()
            logger.info("Attempting to refresh Google API credentials...")
            credentials.refresh(auth_req)
            logger.info("Google API credentials refreshed successfully.")
            if credentials.token:
                token_preview = credentials.token[:10] + "..."
                logger.info(f"Obtained Google API access token starting with: {token_preview}")
                expiry_time = getattr(credentials, 'expiry', None)
                if expiry_time: logger.info(f"Token expiry time: {expiry_time}")
                else: logger.info("Token expiry time not available.")
            else:
                logger.warning("Google API credentials refreshed but no token was obtained.")
        except Exception as refresh_error:
            logger.warning(f"Token refresh failed, but continuing: {str(refresh_error)}")
        logger.info(f"Successfully obtained credentials for Google APIs.")
        return credentials
    except Exception as e:
        logger.error(f"Error getting Google API credentials: {str(e)}")
        logger.error(traceback.format_exc()) # Log traceback
        return None

# Keep the original function for backward compatibility, but make it call the appropriate new function
def get_credentials(scopes):
    """Legacy function that routes to the appropriate credential getter based on scope"""
    if any(platform in str(scopes) for platform in ["aiplatform", "cloud-platform", "generative-ai"]):
        return get_credentials_for_gemini()
    else:
        return get_credentials_for_google_apis(scopes)

# --- Gemini API ---
def process_image_with_gemini(image_path, user_id):
    """
    Process an image using Gemini 2.0 Lite API with service account authentication
    Returns: Tuple (Parsed JSON response or None, Error message string or None)
    """
    logger.info(f"Initiating Gemini API request for image from user_id: {user_id}")

    try:
        # Use the dedicated Gemini credentials function
        credentials = get_credentials_for_gemini()

        if not credentials:
            logger.error("Failed to get authenticated credentials for Gemini")
            return None, "Authentication failed." # Return error message

        # Read the image file as binary data
        with open(image_path, 'rb') as image_file:
            image_data = image_file.read()

        # Encode image to base64
        encoded_image = base64.b64encode(image_data).decode('utf-8')

        # Prepare the request payload
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": "Analyze the image and extract the following personal information: full name, date of birth, age, email, phone number, city, state, gender, and preferred contact method.  Return the extracted information as a **single string** with **key-value pairs separated by pipe symbols (|)**.  The format should be: `key=value|key=value|key=value|...`. Use the following keys: `full_name`, `date_of_birth`, `age`, `email`, `phone_number`, `city`, `state`, `gender`, and `preferred_contact_method`. For example: `full_name=LUIGI CADORNA|date_of_birth=8/2/1962|age=63|email=luigi.cadorna@ymail.com|phone_number=1234567890|city=Buenos Aires|state=JALISCO|gender=Male|preferred_contact_method=Mail` If any piece of information cannot be confidently extracted from the image, leave the corresponding value **empty** (for strings) or `null` (for numbers like age), but still include the key in the output string. For example, if the email is not found, it should be `email=|...` and if the age is not found, it should be `age=null|...`. Ensure the response is **only the single string** with pipe-separated key-value pairs, without any markdown formatting, code blocks, or extraneous text."},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": encoded_image
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.4,
                "topK": 32,
                "topP": 1,
                "maxOutputTokens": 4096
            }
        }

        logger.info(f"Sending image data to Gemini API endpoint: {config.GEMINI_API_ENDPOINT}")

        # Get an access token from the credentials
        auth_req = GoogleAuthRequest()
        credentials.refresh(auth_req) # Refresh just before use
        access_token = credentials.token

        if not access_token:
             logger.error("Failed to get access token after refresh for Gemini.")
             return None, "Authentication token refresh failed."

        # Log token information (without revealing the full token)
        token_preview = access_token[:10] + "..." if access_token else "None"
        logger.info(f"Using token starting with: {token_preview} for image processing")

        # Make the API request with the access token
        response = requests.post(
            config.GEMINI_API_ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            },
            data=json.dumps(payload),
            timeout=60 # Add a timeout
        )

        # Log the raw response
        logger.info(f"Received raw response from Gemini API (Status: {response.status_code}): {response.text[:500]}...")

        # Check if the request was successful
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        logger.info("Successfully received response from Gemini API")

        # Parse the JSON response
        logger.info("Starting JSON parsing of Gemini API response")
        parsed_response = response.json()
        logger.info("Successfully parsed JSON response")

        return parsed_response, None # Return data and no error

    except requests.exceptions.RequestException as req_err:
         logger.error(f"HTTP request error calling Gemini API: {req_err}", exc_info=True)
         status_code = getattr(req_err.response, 'status_code', None)
         error_text = getattr(req_err.response, 'text', str(req_err))
         user_error = f"Network error communicating with AI service ({status_code}): {error_text[:200]}"
         return None, user_error
    except json.JSONDecodeError as json_err:
        logger.error(f"Error parsing Gemini JSON response: {json_err}", exc_info=True)
        return None, "Received invalid data format from AI service."
    except Exception as e:
        logger.error(f"Error processing image with Gemini: {str(e)}", exc_info=True)
        return None, "An unexpected error occurred during AI processing."

def extract_text_from_gemini_response(gemini_response):
    """
    Extract the text content from Gemini API response and format it as pipe-separated key-value pairs
    """
    try:
        # Check if response is already a dictionary (parsed JSON)
        if isinstance(gemini_response, dict):
            response_dict = gemini_response
        else:
            # Try to parse the response as JSON if it's a string
            if isinstance(gemini_response, str):
                response_dict = json.loads(gemini_response)
            else:
                # If it's neither a dict nor a string, assume it's already the parsed object
                response_dict = gemini_response

        # Initialize all_text to collect the text from all parts
        all_text = ""

        # If it's a list of responses (like in gemini_response.json)
        if isinstance(response_dict, list):
            # Extract text from all parts in all responses
            for response_segment in response_dict:
                if "candidates" in response_segment and response_segment["candidates"]:
                    candidate = response_segment["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        for part in candidate["content"]["parts"]:
                            if "text" in part:
                                all_text += part["text"]

        # Handle single response format
        elif "candidates" in response_dict and response_dict["candidates"]:
            candidate = response_dict["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                for part in candidate["content"]["parts"]:
                    if "text" in part:
                        all_text += part["text"]
        else:
            # Check for promptFeedback if no candidates
            feedback = response_dict.get("promptFeedback", {})
            block_reason = feedback.get("blockReason")
            if block_reason:
                 logger.warning(f"Gemini response blocked. Reason: {block_reason}")
                 safety_ratings = feedback.get("safetyRatings", [])
                 return f"Content blocked by safety filters. Reason: {block_reason}. Details: {safety_ratings}"
            else:
                 logger.warning(f"No candidates or block reason found in Gemini response: {response_dict}")
                 return "No text content found in the AI response."

        # If we didn't extract any text, return a message
        if not all_text:
            logger.warning("No text was extracted from the response")
            return "No text content found in the AI response."

        # Clean up the text - remove code blocks, markdown formatting, etc.
        all_text = re.sub(r"```(json)?", "", all_text).strip()
        all_text = all_text.replace("`", "").replace("**", "") # Remove backticks and bold markdown

        # Basic check if it looks like the expected pipe format
        if "|" in all_text and "=" in all_text:
            logger.info("Extracted text appears to be in pipe-separated format.")
            return all_text
        else:
            logger.warning(f"Extracted text might not be in the expected pipe-separated format: {all_text[:100]}...")
            # Return the cleaned text anyway
            return all_text

    except Exception as e:
        logger.error(f"Error extracting text from Gemini response: {str(e)}", exc_info=True)
        logger.error(f"Problematic response snippet: {str(gemini_response)[:500]}")
        traceback.print_exc() # Print traceback for debugging
        return "Error processing AI response content."

def analyze_text_with_gemini(prompt_text, user_id):
    """Sends text prompt to Gemini for analysis (used in Menu 1)."""
    logger.info(f"Initiating Gemini text analysis for user {user_id}")
    try:
        credentials = get_credentials_for_gemini()
        if not credentials:
            logger.error("Failed to get authenticated credentials for Gemini text analysis")
            return None, "Authentication failed."

        if not credentials.token:
             logger.error("Credentials obtained but token is missing after refresh for Gemini text analysis.")
             return None, "Authentication token issue."

        headers = {
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json"
        }
        token_preview = credentials.token[:10] + "..."
        logger.info(f"Using token starting with: {token_preview} for text analysis")

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt_text}]}],
            "generationConfig": {"temperature": 0.4, "topK": 32, "topP": 0.95, "maxOutputTokens": 1024}
        }

        logger.info(f"Sending text analysis request to Gemini API endpoint: {config.GEMINI_API_ENDPOINT}")
        response = requests.post(config.GEMINI_API_ENDPOINT, headers=headers, json=payload, timeout=60)

        logger.info(f"Received raw response from Gemini API (Status: {response.status_code}): {response.text[:500]}...")
        response.raise_for_status()

        response_json = response.json()
        analysis_result = extract_text_from_gemini_response(response_json) # Reuse extraction logic
        logger.info(f"Successfully received and extracted Gemini analysis for user {user_id}")
        return analysis_result, None

    except requests.exceptions.RequestException as req_err:
         logger.error(f"HTTP request error calling Gemini API for text analysis: {req_err}", exc_info=True)
         status_code = getattr(req_err.response, 'status_code', None)
         error_text = getattr(req_err.response, 'text', str(req_err))
         user_error = f"Network error communicating with AI service ({status_code}): {error_text[:200]}"
         return None, user_error
    except json.JSONDecodeError as json_err:
        logger.error(f"Error parsing Gemini JSON response for text analysis: {json_err}", exc_info=True)
        return None, "Received invalid data format from AI service."
    except Exception as e:
        logger.error(f"Error processing text with Gemini for user {user_id}: {str(e)}", exc_info=True)
        return None, "An unexpected error occurred during AI text analysis."

# --- Google Forms API ---
def get_google_form_response(form_id, response_id):
    """Retrieves a specific response from a Google Form."""
    logger.info(f"Attempting to retrieve response {response_id} from form {form_id}")

    # Get credentials for Google Forms API
    forms_scope = ["https://www.googleapis.com/auth/forms.responses.readonly"]
    credentials = get_credentials_for_google_apis(scopes=forms_scope)

    if not credentials:
        logger.error("Failed to get credentials for Google Forms API.")
        return None, "Authentication failed."

    try:
        # Build the service object
        service = build('forms', 'v1', credentials=credentials)

        # Retrieve the response
        result = service.forms().responses().get(
            formId=form_id,
            responseId=response_id
        ).execute()

        logger.info(f"Successfully retrieved form response {response_id}")
        return result, None # Return data and no error

    except HttpError as error:
        error_details = error.content.decode('utf-8') # Use content instead of resp.get
        try:
             error_json = json.loads(error_details)
             error_message = error_json.get('error', {}).get('message', 'Unknown API error')
             status_code = error_json.get('error', {}).get('code', error.resp.status)
        except json.JSONDecodeError:
             error_message = f"API Error (Status: {error.resp.status})"
             status_code = error.resp.status

        logger.error(f"Google Forms API error: {status_code} - {error_message}")
        if status_code == 404:
             return None, f"Response ID '{response_id}' not found in form '{form_id}'."
        elif status_code == 403:
             return None, "Permission denied. Ensure the service account has access to the form responses."
        else:
             return None, f"API Error: {error_message}"
    except Exception as e:
        logger.error(f"Unexpected error retrieving form response: {e}", exc_info=True)
        return None, "An unexpected error occurred."

# --- Google Apps Script ---
def call_apps_script(script_id, function_name, parameters):
    """Calls a Google Apps Script function with extensive logging."""
    logger.info(f"Initiating call to Apps Script ID: {script_id}, Function: {function_name}")
    logger.debug(f"Apps Script parameters: {parameters}") # Log parameters at debug level

    # Get credentials for Apps Script API
    apps_script_scope = ["https://www.googleapis.com/auth/script.execute"]
    credentials = get_credentials_for_google_apis(scopes=apps_script_scope)

    if not credentials:
        # get_credentials already logs the error extensively
        logger.error("Failed to obtain credentials for Apps Script call.")
        return None, "Authentication failed. Could not get credentials."

    # Log credential details (avoid logging full token)
    logger.info(f"Using credentials for service account: {credentials.service_account_email}")
    logger.debug(f"Credentials valid: {credentials.valid}, Scopes: {credentials.scopes}")

    try:
        logger.info("Building Apps Script API service (script, v1)...")
        service = build('script', 'v1', credentials=credentials)
        logger.info("Apps Script API service built successfully.")

        # Create the request body
        request = {
            'function': function_name,
            'parameters': parameters,
            'devMode': False  # Set to True only if debugging the Apps Script itself
        }
        logger.info(f"Executing Apps Script function '{function_name}'...")
        logger.debug(f"Apps Script request body: {request}")

        # Make the API call to run the script
        response = service.scripts().run(scriptId=script_id, body=request).execute()
        logger.info(f"Received response from Apps Script execution.")
        logger.debug(f"Raw Apps Script response: {response}") # Log raw response at debug level

        # Check for errors returned by the Apps Script execution itself
        if 'error' in response:
            error_details = response['error'].get('details', [{}])[0]
            error_message = error_details.get('errorMessage', 'Unknown script execution error')
            error_type = error_details.get('errorType', 'UnknownType')
            script_stack_trace = error_details.get('scriptStackTraceElements', [])

            logger.error(f"Apps Script execution error: Type={error_type}, Message={error_message}")
            if script_stack_trace:
                logger.error(f"Apps Script Stacktrace: {script_stack_trace}")

            # Provide a more user-friendly message based on common issues
            if "Authorization is required" in error_message or "Script has attempted to perform an action" in error_message:
                 user_error = "Authorization error within the Apps Script. Ensure the script has the necessary permissions."
            elif "not found" in error_message: # Function or variable not found
                 user_error = f"Error within the Apps Script: '{function_name}' or related code not found."
            else:
                 user_error = f"Error during script execution: {error_message}"
            return None, user_error

        # Extract the result if execution was successful
        result = response.get('response', {}).get('result')
        logger.info(f"Apps Script execution successful. Result type: {type(result)}")
        logger.debug(f"Apps Script result: {result}") # Log result at debug level
        return result, None # Return result and no error

    except HttpError as http_error:
        status_code = http_error.resp.status
        error_content = http_error.content.decode('utf-8')
        logger.error(f"HTTP error calling Apps Script API: Status={status_code}, Response={error_content}", exc_info=True)

        # Provide specific user messages based on HTTP status code
        if status_code == 401: # Unauthorized
            user_error = "Authentication failed (401). Check service account credentials and API access."
        elif status_code == 403: # Forbidden
            user_error = "Permission denied (403). Ensure the Apps Script API is enabled and the service account has permission to execute the script."
        elif status_code == 404: # Not Found
            user_error = f"Apps Script project (ID: {script_id}) not found (404)."
        elif status_code == 429: # Rate Limited
             user_error = "API rate limit exceeded (429). Please try again later."
        else:
            user_error = f"API error occurred ({status_code}). Check logs for details."
        return None, user_error

    except Exception as e:
        logger.error(f"Unexpected error calling Apps Script: {e}", exc_info=True)
        return None, "An unexpected error occurred while communicating with the Apps Script service."

def get_sheet_data_via_webapp(id_to_find):
    """Retrieves data from the Google Sheet via the deployed Apps Script Web App."""
    logger.info(f"Initiating call to Apps Script Web App for ID: {id_to_find}")

    # Check if configuration is available
    if not config.APPS_SCRIPT_WEB_APP_URL or not config.APPS_SCRIPT_API_KEY:
        logger.error("Web App URL or API Key is not configured.")
        return None, "Web App retrieval is not configured on the server."

    try:
        # Construct the URL with query parameters
        params = {
            'id': id_to_find,
            'apiKey': config.APPS_SCRIPT_API_KEY
        }
        target_url = config.APPS_SCRIPT_WEB_APP_URL
        logger.info(f"Making GET request to Web App URL (parameters omitted for security)")
        # For debugging ONLY, uncomment the next line:
        # logger.debug(f"Request URL: {target_url}?id={id_to_find}&apiKey={config.APPS_SCRIPT_API_KEY[:4]}...")

        # --- START MODIFICATION ---
        logger.info(f"Attempting requests.get to {target_url} with timeout=30...") # Add log BEFORE request
        # Make the GET request
        response = requests.get(target_url, params=params, timeout=30) # Existing request
        logger.info(f"requests.get call completed. Status code received: {response.status_code}") # Add log AFTER request
        # --- END MODIFICATION ---

        # Log basic response info (existing log)
        logger.info(f"Received response from Web App. Status: {response.status_code}, Content-Type: {response.headers.get('Content-Type')}")
        logger.debug(f"Raw response text (first 500 chars): {response.text[:500]}")

        # Check for HTTP errors (4xx or 5xx)
        response.raise_for_status()

        # Check for specific text responses indicating errors from the script itself
        if response.text == "Not Found":
            logger.warning(f"Web App returned 'Not Found' for ID: {id_to_find}")
            return None, f"ID '{id_to_find}' not found in the Google Sheet."
        if response.text == "Unauthorized":
            logger.error("Web App returned 'Unauthorized'. Check the API Key.")
            return None, "Authorization failed. Invalid API Key provided to Web App."
        if response.text == "Bad Request":
             logger.error("Web App returned 'Bad Request'. Check if 'id' parameter is missing or invalid.")
             return None, "Bad request sent to the Web App (e.g., missing ID)."

        # Attempt to parse the JSON response
        try:
            json_result = response.json()
            logger.info(f"Successfully parsed JSON response from Web App for ID: {id_to_find}")
            return json_result, None # Return data and no error
        except json.JSONDecodeError as json_err:
            logger.error(f"Failed to decode JSON response from Web App: {json_err}")
            logger.error(f"Response text was: {response.text}")
            return None, "Received invalid data format from the Web App."

    except requests.exceptions.Timeout:
         logger.error(f"Request to Web App timed out for ID: {id_to_find}")
         return None, "The request to the Web App timed out."
    except requests.exceptions.RequestException as req_err:
        logger.error(f"HTTP request error calling Web App: {req_err}", exc_info=True)
        # Try to provide more specific feedback based on status code if available
        status_code = getattr(req_err.response, 'status_code', None)
        if status_code == 401: # Often means script requires login / incorrect sharing
             user_error = "Web App access denied (401). Check script permissions/deployment settings."
        elif status_code == 403: # Might mean API key mismatch or other permission issue
             user_error = "Web App forbidden (403). Check API key or script access settings."
        elif status_code == 404: # URL incorrect
             user_error = "Web App URL not found (404). Check the configured URL."
        elif status_code == 500: # Internal server error in the script
             user_error = "Error within the Web App script (500). Check script logs."
        else:
             user_error = f"Network error communicating with the Web App: {req_err}"
        return None, user_error
    except Exception as e:
        logger.error(f"Unexpected error retrieving data via Web App: {e}", exc_info=True)
        return None, "An unexpected error occurred while contacting the Web App."
