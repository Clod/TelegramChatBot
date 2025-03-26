Excellent!  Yes, the 401 error is a classic authentication issue. The error message itself is very helpful and points directly to the problem:  "API keys are not supported by this API. Expected OAuth2 access token...".

Let's break down what's happening and how to fix it.

**Understanding the 401 Error and Gemini API Authentication**

The Gemini API you are trying to use (likely through Vertex AI on Google Cloud Platform, based on the error details: `google.cloud.aiplatform.v1.PredictionService.StreamGenerateContent`) requires a more secure authentication method than a simple API key. It expects you to authenticate using OAuth 2.0.

**Here's why API Keys are not enough and why OAuth 2.0 is needed:**

*   **Security:**  API keys are simpler but less secure for production services, especially when dealing with powerful APIs like those in Vertex AI. OAuth 2.0 provides a more robust and secure way to manage access and permissions.
*   **Granular Permissions:** OAuth 2.0 allows for more fine-grained control over what your application can access and do.  You can grant specific permissions (scopes) to your application, rather than just giving it blanket access with an API key.
*   **Service Accounts (for Server-Side Apps):** For server-side applications like your Flask/Telegram bot, the recommended way to use OAuth 2.0 with Google Cloud APIs is through **Service Accounts**.

**What is a Service Account?**

A Service Account is a special type of Google account intended for programmatic use by applications and services, rather than by individual users.  It acts as the identity of your application when it interacts with Google Cloud services.

**Steps to Resolve the 401 Error and Authenticate with a Service Account**

Here's a step-by-step guide to set up Service Account authentication for your Gemini API calls:

**1. Google Cloud Project Setup (If you don't have one already):**

*   Go to the [Google Cloud Console](https://console.cloud.google.com/).
*   If you don't have a project, create a new project.  Give it a name and select a billing account.

**2. Enable the Vertex AI API:**

*   In the Cloud Console, navigate to "APIs & Services" -> "Enabled APIs & services".
*   Click "+ ENABLE APIS AND SERVICES".
*   Search for "Vertex AI API" and enable it.

**3. Create a Service Account:**

*   Navigate to "IAM & Admin" -> "Service Accounts".
*   Click "+ CREATE SERVICE ACCOUNT".
*   Give your service account a descriptive name (e.g., `gemini-api-bot-sa`).
*   Service account ID will be generated automatically. You can customize it if you wish.
*   Click "Create and Continue".

**4. Grant the Service Account Necessary Roles:**

*   On the "Grant this service account access to project" page, you need to grant the service account the roles it needs to use the Gemini API.  The necessary role might depend on the specific Gemini API endpoint you are using.  A common role for using Vertex AI prediction services is:
    *   **`Vertex AI User`**  (This is a good starting point and often sufficient)
    *   You might need to consult the Gemini API documentation for the *exact* minimum required roles.  More specific roles might exist for finer-grained control.
*   Search for and select the appropriate role (e.g., "Vertex AI User").
*   Click "Continue".
*   The "Grant users access to this service account" page is optional for now (you don't need to grant user access in most cases for application authentication). Click "Done".

**5. Generate a Service Account Key (JSON File):**

*   Find your newly created service account in the Service Accounts list.
*   Click on the service account's email address to go to its details page.
*   Go to the "Keys" tab.
*   Click "ADD KEY" -> "Create new key".
*   Choose "JSON" as the key type.
*   Click "CREATE".
*   A JSON key file will be downloaded to your computer. **This file contains your service account's private key.  Treat it securely! Do not commit it to your code repository directly.**

**6. Install the `google-auth` Library in your Python Environment:**

```bash
pip install google-auth
```

**7. Update Your Python Code to Use Service Account Authentication:**

Here's how you'll need to modify your Python code to use the service account key for authentication.  **Important:**  Adapt this to how you are *actually* making the request to the Gemini API (using `requests`, a specific Gemini/Vertex AI Python client library, etc.). This is a conceptual example using `requests` and assuming you're still using `requests` for the API call.

```python
import os
import google.auth.transport.requests
import google.oauth2.credentials
import requests
import json
import logging

logger = logging.getLogger(__name__)

# ---  Authentication Setup ---
SERVICE_ACCOUNT_KEY_PATH = "path/to/your/downloaded/service_account_key.json"  # **REPLACE WITH YOUR ACTUAL PATH**
GEMINI_API_ENDPOINT = "YOUR_GEMINI_API_ENDPOINT_HERE" # **REPLACE WITH YOUR ACTUAL GEMINI API ENDPOINT**

def get_gemini_access_token():
    """Authenticates with Google Cloud using a service account key and returns an access token."""
    try:
        credentials = google.oauth2.service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_KEY_PATH)
        request = google.auth.transport.requests.Request()
        credentials.refresh(request) # Refresh access token if needed
        return credentials.token
    except Exception as e:
        logger.error(f"Error getting Gemini access token: {e}")
        return None


def process_image_from_document(update, context):
    # ... (rest of your process_image_from_document code - image download, etc.) ...

    access_token = get_gemini_access_token()
    if not access_token:
        context.bot.send_message(chat_id=user_id, text="Sorry, I couldn't authenticate with the image processing service.")
        return

    try:
        logger.info("Initiating Gemini 2.0 Lite API request (with OAuth 2.0).")
        with open(temp_image_path, 'rb') as image_file:
            image_data = image_file.read()
            headers = {
                "Content-Type": "image/jpeg", # Or appropriate content type
                "Authorization": f"Bearer {access_token}" # Use access token in Authorization header
            }
            # ... (Rest of your API request logic - payload, files, etc. - as before) ...
            response = requests.post(GEMINI_API_ENDPOINT, files={'image': ('image.jpg', image_data, 'image/jpeg')}, headers=headers)
            response.raise_for_status()
            logger.info("Gemini 2.0 Lite API request successful (with OAuth 2.0).")
            logger.debug(f"Raw Gemini API response: {response.text}")
            # ... (Rest of your JSON parsing, DB storage, user feedback logic) ...

    except requests.exceptions.RequestException as api_error:
        logger.error(f"Gemini API request failed with status code: {api_error.response.status_code if api_error.response else 'N/A'}") # Log status code if available
        if api_error.response:
            logger.error(f"Error response: {api_error.response.text}") # Log full error response for debugging
        logger.error(f"Error during Gemini 2.0 Lite API request: {api_error}")
        context.bot.send_message(chat_id=user_id, text="Sorry, there was an issue with the image processing service.")

    # ... (rest of your function - cleanup, etc.) ...

# ... (rest of your bot code - handlers, etc.) ...
```

**Key Changes in the Code:**

*   **Import `google.auth` libraries:**  `google.auth.transport.requests`, `google.oauth2.credentials`, `google.oauth2.service_account`.
*   **`SERVICE_ACCOUNT_KEY_PATH`:**  Set this variable to the path of your downloaded JSON key file. **Remember to replace the placeholder!**
*   **`get_gemini_access_token()` function:**
    *   Loads the service account credentials from the JSON key file using `google.oauth2.service_account.Credentials.from_service_account_file()`.
    *   Refreshes the access token (important for long-running applications) using `credentials.refresh(request)`.
    *   Returns the access token (`credentials.token`).
*   **`Authorization` Header:** In your `requests.post()` call, the `headers` dictionary now includes: `"Authorization": f"Bearer {access_token}"`.  This is where you pass the OAuth 2.0 access token to the Gemini API.
*   **Error Handling:**  Improved error logging to include the HTTP status code and error response text from the Gemini API, which is helpful for debugging.

**Important Security Reminders:**

*   **Securely Store Your Service Account Key:**  **Never hardcode the contents of the JSON key file directly into your code.**  Store the `SERVICE_ACCOUNT_KEY_PATH` in an environment variable or a secure configuration management system.  Do not commit the key file to your code repository.
*   **Least Privilege:**  Grant your service account only the minimum necessary roles required to access the Gemini API.  Start with `Vertex AI User` and refine if needed based on the specific API documentation.
*   **API Endpoint:** Double-check that `GEMINI_API_ENDPOINT` is the correct endpoint for the Gemini API you are using. Refer to the official Gemini API documentation.

**Next Steps:**

1.  **Implement the Service Account Authentication:** Follow the steps above to create a service account, generate a key, and update your Python code.
2.  **Test Again:** Send an image to your bot again.
3.  **Check Logs:** Examine your logs. You should now see successful Gemini API requests (status code 200) if the authentication is set up correctly. If you still get 401 errors, double-check your service account setup, key file path, and code implementation.
4.  **Consult Gemini API Documentation:**  Refer to the official Gemini API documentation for the precise API endpoint, request format, required roles, and any other authentication-specific details.

By implementing Service Account authentication, you should resolve the 401 error and be able to successfully communicate with the Gemini API! Let me know if you encounter any issues or have further questions as you go through these steps.