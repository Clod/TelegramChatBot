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
from . import config, strings as s # Use relative import

logger = logging.getLogger(__name__)

# --- Credential Management ---
def get_credentials_for_gemini():
    """Get authenticated credentials specifically for Gemini API"""
    logger.info(s.LOG_GETTING_GEMINI_CREDS)
    try:
        if not config.SERVICE_ACCOUNT_FILE or not os.path.exists(config.SERVICE_ACCOUNT_FILE):
            logger.error(s.ERROR_SERVICE_ACCOUNT_NOT_FOUND.format(path=config.SERVICE_ACCOUNT_FILE))
            return None
        scopes_to_try = [
            [s.API_SCOPE_CLOUD_PLATFORM],
            [s.API_SCOPE_AI_PLATFORM],
            [s.API_SCOPE_GENERATIVE_AI]
        ]
        for scope in scopes_to_try:
            logger.info(s.LOG_TRYING_GEMINI_SCOPE.format(scope=scope))
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    config.SERVICE_ACCOUNT_FILE, scopes=scope)
                auth_req = GoogleAuthRequest()
                logger.info(s.LOG_REFRESHING_GEMINI_CREDS.format(scope=scope))
                credentials.refresh(auth_req)
                if credentials.token:
                    token_preview = credentials.token[:10] + "..."
                    logger.info(s.LOG_GEMINI_TOKEN_SUCCESS.format(token_preview=token_preview))
                    return credentials
                else:
                    logger.warning(s.WARN_GEMINI_NO_TOKEN.format(scope=scope))
            except Exception as e:
                logger.warning(s.WARN_GEMINI_FAILED_TOKEN_SCOPE.format(scope=scope, error=str(e)))
                continue
        logger.error(s.ERROR_GEMINI_ALL_AUTH_FAILED)
        return None
    except Exception as e:
        logger.error(s.ERROR_GETTING_GEMINI_CREDS.format(error=str(e)))
        logger.error(traceback.format_exc()) # Log traceback
        return None

def get_credentials_for_google_apis(scopes):
    """Get authenticated credentials for Google APIs (Forms, Apps Script, etc.)"""
    logger.info(s.LOG_GETTING_GOOGLE_API_CREDS)
    try:
        if not config.SERVICE_ACCOUNT_FILE or not os.path.exists(config.SERVICE_ACCOUNT_FILE):
            logger.error(s.ERROR_SERVICE_ACCOUNT_NOT_FOUND.format(path=config.SERVICE_ACCOUNT_FILE))
            return None
        logger.info(s.LOG_REQUESTING_GOOGLE_API_CREDS.format(scopes=scopes))
        credentials = service_account.Credentials.from_service_account_file(
            config.SERVICE_ACCOUNT_FILE, scopes=scopes)
        logger.info(s.LOG_GOOGLE_API_CREDS_CREATED.format(path=config.SERVICE_ACCOUNT_FILE))
        try:
            auth_req = GoogleAuthRequest()
            logger.info(s.LOG_REFRESHING_GOOGLE_API_CREDS)
            credentials.refresh(auth_req)
            logger.info(s.LOG_GOOGLE_API_CREDS_REFRESHED)
            if credentials.token:
                token_preview = credentials.token[:10] + "..."
                logger.info(s.LOG_GOOGLE_API_TOKEN_SUCCESS.format(token_preview=token_preview))
                expiry_time = getattr(credentials, 'expiry', None)
                if expiry_time: logger.info(s.LOG_GOOGLE_API_TOKEN_EXPIRY.format(expiry_time=expiry_time))
                else: logger.info(s.LOG_GOOGLE_API_TOKEN_NO_EXPIRY)
            else:
                logger.warning(s.WARN_GOOGLE_API_NO_TOKEN)
        except Exception as refresh_error:
            logger.warning(s.WARN_GOOGLE_API_REFRESH_FAILED.format(error=str(refresh_error)))
        logger.info(s.LOG_GOOGLE_API_CREDS_SUCCESS)
        return credentials
    except Exception as e:
        logger.error(s.ERROR_GETTING_GOOGLE_API_CREDS.format(error=str(e)))
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
    logger.info(s.LOG_GEMINI_REQUEST_INITIATED.format(user_id=user_id))

    try:
        # Use the dedicated Gemini credentials function
        credentials = get_credentials_for_gemini()

        if not credentials:
            logger.error(s.ERROR_GEMINI_AUTH_FAILED)
            return None, s.ERROR_GEMINI_AUTH_FAILED_MSG # Return error message

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
                    "parts": [{"text": s.GEMINI_PROMPT_IMAGE_ANALYSIS},
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

        logger.info(s.LOG_GEMINI_SENDING_IMAGE.format(endpoint=config.GEMINI_API_ENDPOINT))

        # Get an access token from the credentials
        auth_req = GoogleAuthRequest()
        credentials.refresh(auth_req) # Refresh just before use
        access_token = credentials.token

        if not access_token:
             logger.error(s.ERROR_GEMINI_TOKEN_REFRESH_FAILED)
             return None, s.ERROR_GEMINI_TOKEN_REFRESH_FAILED_MSG

        # Log token information (without revealing the full token)
        token_preview = access_token[:10] + "..." if access_token else "None"
        logger.info(s.LOG_GEMINI_USING_TOKEN.format(token_preview=token_preview))

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
        logger.info(s.LOG_GEMINI_RAW_RESPONSE.format(status_code=response.status_code, text_preview=response.text[:500]))

        # Check if the request was successful
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        logger.info(s.LOG_GEMINI_RESPONSE_SUCCESS)

        # Parse the JSON response
        logger.info(s.LOG_GEMINI_PARSED_SUCCESS)
        parsed_response = response.json()
        logger.info(s.LOG_GEMINI_PARSED_SUCCESS)

        return parsed_response, None # Return data and no error

    except requests.exceptions.RequestException as req_err:
         logger.error(s.ERROR_GEMINI_REQUEST_FAILED.format(error=req_err), exc_info=True)
         status_code = getattr(req_err.response, 'status_code', None)
         error_text = getattr(req_err.response, 'text', str(req_err))
         user_error = s.ERROR_GEMINI_REQUEST_FAILED_USER_MSG.format(status_code=status_code, error_text_preview=error_text[:200])
         return None, user_error
    except json.JSONDecodeError as json_err:
        logger.error(s.ERROR_GEMINI_JSON_DECODE.format(error=json_err), exc_info=True)
        return None, s.ERROR_GEMINI_JSON_DECODE_USER_MSG
    except Exception as e:
        logger.error(s.ERROR_GEMINI_PROCESSING_IMAGE.format(error=str(e)), exc_info=True)
        return None, s.ERROR_GEMINI_PROCESSING_IMAGE_USER_MSG

def extract_text_from_gemini_response(gemini_response):
    """
    Extract the text content from Gemini API response and format it as pipe-separated key-value pairs
    """
    try:
        # Log the received response for debugging before checking its type
        logger.debug(s.DEBUG_GEMINI_EXTRACT_ATTEMPT.format(type=type(gemini_response), content_preview=str(gemini_response)[:500])) # Log type and preview

        # Allow either a dictionary or a list as the top-level response structure
        if not isinstance(gemini_response, (dict, list)):
             logger.error(s.ERROR_GEMINI_EXTRACT_UNEXPECTED_TYPE.format(type=type(gemini_response)))
             logger.error(s.DEBUG_GEMINI_EXTRACT_FAIL_CONTENT.format(content=gemini_response)) # Log the full problematic response
             return s.ERROR_GEMINI_EXTRACT_INVALID_FORMAT

        # Initialize all_text to collect the text from all parts
        all_text = ""

        # If it's a list of responses (like in gemini_response.json)
        if isinstance(gemini_response, list):
            # Extract text from all parts in all responses
            for response_segment in gemini_response:
                if "candidates" in response_segment and response_segment["candidates"]:
                    candidate = response_segment["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        for part in candidate["content"]["parts"]:
                            if "text" in part:
                                all_text += part["text"]

        # Handle single response format
        elif "candidates" in gemini_response and gemini_response["candidates"]:
            candidate = gemini_response["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                for part in candidate["content"]["parts"]:
                    if "text" in part:
                        all_text += part["text"]
        else:
            # Check for promptFeedback if no candidates
            feedback = gemini_response.get("promptFeedback", {})
            block_reason = feedback.get("blockReason")
            if block_reason:
                 logger.warning(s.WARN_GEMINI_RESPONSE_BLOCKED.format(reason=block_reason))
                 safety_ratings = feedback.get("safetyRatings", [])
                 return s.GEMINI_RESPONSE_BLOCKED_USER_MSG.format(reason=block_reason, safety_ratings=safety_ratings)
            else:
                 logger.warning(s.WARN_GEMINI_NO_CANDIDATES.format(response=gemini_response))
                 return s.GEMINI_NO_TEXT_USER_MSG

        # If we didn't extract any text, return a message
        if not all_text:
            logger.warning(s.WARN_GEMINI_NO_TEXT_EXTRACTED)
            return s.GEMINI_NO_TEXT_USER_MSG

        # Clean up the text - remove code blocks, markdown formatting, etc.
        all_text = re.sub(r"```(json)?", "", all_text).strip()
        all_text = all_text.replace("`", "").replace("**", "") # Remove backticks and bold markdown

        # Basic check if it looks like the expected pipe format
        if "|" in all_text and "=" in all_text:
            logger.info(s.LOG_GEMINI_EXTRACTED_PIPE_FORMAT)
            return all_text
        else:
            logger.warning(s.WARN_GEMINI_EXTRACTED_UNEXPECTED_FORMAT.format(text_preview=all_text[:100]))
            # Return the cleaned text anyway
            return all_text

    except Exception as e:
        logger.error(s.ERROR_GEMINI_EXTRACTING_TEXT.format(error=str(e)), exc_info=True)
        logger.error(s.DEBUG_GEMINI_EXTRACT_FAIL_SNIPPET.format(snippet=str(gemini_response)[:500]))
        return s.ERROR_GEMINI_EXTRACTING_TEXT_USER_MSG

def analyze_text_with_gemini(prompt_text, user_id):
    """Sends text prompt to Gemini for analysis (used in Menu 1)."""
    logger.info(s.LOG_GEMINI_TEXT_ANALYSIS_INITIATED.format(user_id=user_id))
    try:
        credentials = get_credentials_for_gemini()
        if not credentials:
            logger.error(s.ERROR_GEMINI_TEXT_AUTH_FAILED)
            return None, s.ERROR_GEMINI_AUTH_FAILED_MSG

        if not credentials.token:
             logger.error(s.ERROR_GEMINI_TEXT_TOKEN_MISSING)
             return None, s.ERROR_GEMINI_TEXT_TOKEN_MISSING_MSG

        headers = {
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json"
        }
        token_preview = credentials.token[:10] + "..."
        logger.info(s.LOG_GEMINI_TEXT_USING_TOKEN.format(token_preview=token_preview))

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt_text}]}],
            "generationConfig": {"temperature": 0.4, "topK": 32, "topP": 0.95, "maxOutputTokens": 1024}
        }

        logger.info(s.LOG_GEMINI_TEXT_SENDING_REQUEST.format(endpoint=config.GEMINI_API_ENDPOINT))
        response = requests.post(config.GEMINI_API_ENDPOINT, headers=headers, json=payload, timeout=60)

        logger.info(s.LOG_GEMINI_RAW_RESPONSE.format(status_code=response.status_code, text_preview=response.text[:500]))
        response.raise_for_status()

        response_json = response.json()
        analysis_result = extract_text_from_gemini_response(response_json) # Reuse extraction logic
        logger.info(s.LOG_GEMINI_TEXT_ANALYSIS_SUCCESS.format(user_id=user_id))
        return analysis_result, None

    except requests.exceptions.RequestException as req_err:
         logger.error(s.ERROR_GEMINI_TEXT_REQUEST_FAILED.format(error=req_err), exc_info=True)
         status_code = getattr(req_err.response, 'status_code', None)
         error_text = getattr(req_err.response, 'text', str(req_err))
         user_error = s.ERROR_GEMINI_REQUEST_FAILED_USER_MSG.format(status_code=status_code, error_text_preview=error_text[:200])
         return None, user_error
    except json.JSONDecodeError as json_err:
        logger.error(s.ERROR_GEMINI_TEXT_JSON_DECODE.format(error=json_err), exc_info=True)
        return None, s.ERROR_GEMINI_JSON_DECODE_USER_MSG
    except Exception as e:
        logger.error(s.ERROR_GEMINI_TEXT_PROCESSING.format(user_id=user_id, error=str(e)), exc_info=True)
        return None, s.ERROR_GEMINI_TEXT_PROCESSING_USER_MSG

# --- Google Forms API ---
def get_google_form_response(form_id, response_id):
    """Retrieves a specific response from a Google Form."""
    logger.info(s.LOG_FORM_RETRIEVAL_INITIATED.format(response_id=response_id, form_id=form_id))

    # Get credentials for Google Forms API
    forms_scope = [s.API_SCOPE_FORMS_READONLY]
    credentials = get_credentials_for_google_apis(scopes=forms_scope)

    if not credentials:
        logger.error(s.ERROR_FORM_AUTH_FAILED)
        return None, s.ERROR_FORM_AUTH_FAILED_MSG

    try:
        # Build the service object
        service = build('forms', 'v1', credentials=credentials)

        # Retrieve the response
        result = service.forms().responses().get(
            formId=form_id,
            responseId=response_id
        ).execute()

        logger.info(s.LOG_FORM_RETRIEVAL_SUCCESS.format(response_id=response_id))
        return result, None # Return data and no error

    except HttpError as error:
        error_details = error.content.decode('utf-8') # Use content instead of resp.get
        try:
             error_json = json.loads(error_details)
             error_message = error_json.get('error', {}).get('message', s.ERROR_FORM_API_UNKNOWN)
             status_code = error_json.get('error', {}).get('code', error.resp.status)
        except json.JSONDecodeError:
             error_message = s.ERROR_FORM_API_STATUS_FALLBACK.format(status_code=error.resp.status)
             status_code = error.resp.status

        logger.error(s.ERROR_FORM_API.format(status_code=status_code, error_message=error_message))
        user_error = s.ERROR_FORM_API_USER_MSG.format(status_code=status_code, error_message=error_message)
        if status_code == 404: user_error = s.ERROR_FORM_NOT_FOUND_USER_MSG.format(response_id=response_id, form_id=form_id)
        elif status_code == 403: user_error = s.ERROR_FORM_PERMISSION_DENIED_USER_MSG
        return None, user_error
    except Exception as e:
        logger.error(s.ERROR_FORM_UNEXPECTED.format(error=e), exc_info=True)
        return None, s.ERROR_GENERIC

# --- Google Apps Script ---
def call_apps_script(script_id, function_name, parameters):
    """Calls a Google Apps Script function with extensive logging."""
    logger.info(s.LOG_APPS_SCRIPT_CALL_INITIATED.format(script_id=script_id, function_name=function_name))
    logger.debug(s.LOG_APPS_SCRIPT_PARAMETERS.format(parameters=parameters)) # Log parameters at debug level

    # Get credentials for Apps Script API
    apps_script_scope = [s.API_SCOPE_SCRIPT_EXECUTE]
    credentials = get_credentials_for_google_apis(scopes=apps_script_scope)

    if not credentials:
        # get_credentials already logs the error extensively
        logger.error(s.ERROR_APPS_SCRIPT_AUTH_FAILED)
        return None, s.ERROR_APPS_SCRIPT_AUTH_FAILED_MSG

    # Log credential details (avoid logging full token)
    logger.info(s.LOG_APPS_SCRIPT_USING_CREDS.format(email=credentials.service_account_email))
    logger.debug(s.LOG_APPS_SCRIPT_CREDS_DETAILS.format(valid=credentials.valid, scopes=credentials.scopes))

    try:
        logger.info(s.LOG_APPS_SCRIPT_BUILDING_SERVICE)
        service = build('script', 'v1', credentials=credentials)
        logger.info(s.LOG_APPS_SCRIPT_SERVICE_BUILT)

        # Create the request body
        request = {
            'function': function_name,
            'parameters': parameters,
            'devMode': False  # Set to True only if debugging the Apps Script itself
        }
        logger.info(s.LOG_APPS_SCRIPT_EXECUTING.format(function_name=function_name))
        logger.debug(s.LOG_APPS_SCRIPT_REQUEST_BODY.format(request=request))

        # Make the API call to run the script
        response = service.scripts().run(scriptId=script_id, body=request).execute()
        logger.info(s.LOG_APPS_SCRIPT_RESPONSE_RECEIVED)
        logger.debug(s.LOG_APPS_SCRIPT_RAW_RESPONSE.format(response=response)) # Log raw response at debug level

        # Check for errors returned by the Apps Script execution itself
        if 'error' in response:
            error_details = response['error'].get('details', [{}])[0]
            error_message = error_details.get('errorMessage', 'Unknown script execution error')
            error_type = error_details.get('errorType', 'UnknownType')
            script_stack_trace = error_details.get('scriptStackTraceElements', [])

            logger.error(s.ERROR_APPS_SCRIPT_EXECUTION.format(error_type=error_type, error_message=error_message))
            if script_stack_trace:
                logger.error(s.LOG_APPS_SCRIPT_STACKTRACE.format(stacktrace=script_stack_trace))

            # Provide a more user-friendly message based on common issues
            user_error = s.ERROR_APPS_SCRIPT_EXECUTION_USER_MSG.format(error_message=error_message)
            if "Authorization is required" in error_message or "Script has attempted to perform an action" in error_message:
                 user_error = s.ERROR_APPS_SCRIPT_AUTH_REQUIRED_USER_MSG
            elif "not found" in error_message: # Function or variable not found
                 user_error = s.ERROR_APPS_SCRIPT_NOT_FOUND_USER_MSG.format(function_name=function_name)
            return None, user_error

        # Extract the result if execution was successful
        result = response.get('response', {}).get('result')
        logger.info(s.LOG_APPS_SCRIPT_EXECUTION_SUCCESS.format(type=type(result)))
        logger.debug(s.LOG_APPS_SCRIPT_RESULT.format(result=result)) # Log result at debug level
        return result, None # Return result and no error

    except HttpError as http_error:
        status_code = http_error.resp.status
        error_content = http_error.content.decode('utf-8')
        logger.error(s.ERROR_APPS_SCRIPT_HTTP.format(status_code=status_code, error_content=error_content), exc_info=True)

        # Provide specific user messages based on HTTP status code
        user_error = s.ERROR_APPS_SCRIPT_HTTP_USER_MSG.format(status_code=status_code)
        if status_code == 401: user_error = s.ERROR_APPS_SCRIPT_HTTP_401_USER_MSG
        elif status_code == 403: user_error = s.ERROR_APPS_SCRIPT_HTTP_403_USER_MSG
        elif status_code == 404: user_error = s.ERROR_APPS_SCRIPT_HTTP_404_USER_MSG.format(script_id=script_id)
        elif status_code == 429: user_error = s.ERROR_APPS_SCRIPT_HTTP_429_USER_MSG
        return None, user_error

    except Exception as e:
        logger.error(s.ERROR_APPS_SCRIPT_UNEXPECTED.format(error=e), exc_info=True)
        return None, s.ERROR_APPS_SCRIPT_UNEXPECTED_USER_MSG

def get_sheet_data_via_webapp(id_to_find):
    """Retrieves data from the Google Sheet via the deployed Apps Script Web App."""
    logger.info(s.LOG_WEB_APP_CALL_INITIATED.format(id_to_find=id_to_find))

    # Check if configuration is available
    if not config.APPS_SCRIPT_WEB_APP_URL or not config.APPS_SCRIPT_API_KEY:
        logger.error(s.ERROR_WEB_APP_NOT_CONFIGURED)
        return None, s.ERROR_WEB_APP_NOT_CONFIGURED_USER_MSG

    try:
        # Construct the URL with query parameters
        params = {
            'id': id_to_find,
            'apiKey': config.APPS_SCRIPT_API_KEY
        }
        target_url = config.APPS_SCRIPT_WEB_APP_URL
        logger.info(s.LOG_WEB_APP_MAKING_REQUEST)
        # For debugging ONLY, uncomment the next line:
        # logger.debug(f"Request URL: {target_url}?id={id_to_find}&apiKey={config.APPS_SCRIPT_API_KEY[:4]}...")

        # --- START MODIFICATION ---
        logger.info(s.LOG_WEB_APP_ATTEMPTING_GET.format(target_url=target_url)) # Add log BEFORE request
        # Make the GET request
        response = requests.get(target_url, params=params, timeout=30) # Existing request
        logger.info(s.LOG_WEB_APP_GET_COMPLETED.format(status_code=response.status_code)) # Add log AFTER request
        # --- END MODIFICATION ---

        # Log basic response info (existing log)
        logger.info(s.LOG_WEB_APP_RESPONSE_RECEIVED.format(status_code=response.status_code, content_type=response.headers.get('Content-Type')))
        logger.debug(s.LOG_WEB_APP_RAW_RESPONSE.format(text_preview=response.text[:500]))

        # Check for HTTP errors (4xx or 5xx)
        response.raise_for_status()

        # Check for specific text responses indicating errors from the script itself
        if response.text == "Not Found":
            logger.warning(s.WARN_WEB_APP_NOT_FOUND.format(id_to_find=id_to_find))
            return None, s.WEB_APP_NOT_FOUND_USER_MSG.format(id_to_find=id_to_find)
        if response.text == "Unauthorized":
            logger.error(s.ERROR_WEB_APP_UNAUTHORIZED)
            return None, s.WEB_APP_UNAUTHORIZED_USER_MSG
        if response.text == "Bad Request":
             logger.error(s.ERROR_WEB_APP_BAD_REQUEST)
             return None, s.WEB_APP_BAD_REQUEST_USER_MSG

        # Attempt to parse the JSON response
        try:
            json_result = response.json()
            logger.info(s.LOG_WEB_APP_JSON_PARSED.format(id_to_find=id_to_find))
            return json_result, None # Return data and no error
        except json.JSONDecodeError as json_err:
            logger.error(s.ERROR_WEB_APP_JSON_DECODE.format(error=json_err))
            logger.error(s.ERROR_WEB_APP_JSON_DECODE_TEXT.format(text=response.text))
            return None, s.WEB_APP_INVALID_DATA_USER_MSG

    except requests.exceptions.Timeout:
         logger.error(s.ERROR_WEB_APP_TIMEOUT.format(id_to_find=id_to_find))
         return None, s.WEB_APP_TIMEOUT_USER_MSG
    except requests.exceptions.RequestException as req_err:
        logger.error(s.ERROR_WEB_APP_REQUEST_FAILED.format(error=req_err), exc_info=True)
        # Try to provide more specific feedback based on status code if available
        status_code = getattr(req_err.response, 'status_code', None)
        user_error = s.WEB_APP_REQUEST_FAILED_USER_MSG.format(error=req_err)
        if status_code == 401: user_error = s.WEB_APP_REQUEST_FAILED_401_USER_MSG
        elif status_code == 403: user_error = s.WEB_APP_REQUEST_FAILED_403_USER_MSG
        elif status_code == 404: user_error = s.WEB_APP_REQUEST_FAILED_404_USER_MSG
        elif status_code == 500: user_error = s.WEB_APP_REQUEST_FAILED_500_USER_MSG
        return None, user_error
    except Exception as e:
        logger.error(s.ERROR_WEB_APP_UNEXPECTED.format(error=e), exc_info=True)
        return None, s.WEB_APP_UNEXPECTED_USER_MSG
