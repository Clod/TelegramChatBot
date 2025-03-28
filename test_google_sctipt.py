import google.auth
from googleapiclient.discovery import build

# Path to the service account's JSON key file.  Replace with your actual path.
SERVICE_ACCOUNT_FILE = 'path/to/your/service_account_key.json'

# The ID of your Google Apps Script project.  Replace with your script ID.
SCRIPT_ID = 'your-script-id'  #found at Tools > Script editor > Project Settings

def call_script_function(script_id, function_name, parameters):
    """Calls a Google Apps Script function."""

    # Authenticate using the service account.
    credentials, project = google.auth.load_credentials_from_file(SERVICE_ACCOUNT_FILE,
        scopes=['https://www.googleapis.com/auth/script.execute',
                'https://www.googleapis.com/auth/spreadsheets.readonly',
                'https://www.googleapis.com/auth/script.projects',
                'https://www.googleapis.com/auth/documents.readonly'])

    try:
        # Build the Apps Script API service.
        service = build('script', 'v1', credentials=credentials)

        # Create the request.
        request = {
            'function': function_name,
            'parameters': parameters,
            'devMode': False  # Set to True if you're actively developing the script
        }

        # Make the API call.
        response = service.scripts().run(scriptId=script_id, body=request).execute()

        # Check for errors.
        if 'error' in response:
            error = response['error']
            print(f"Script error: {error}")
            return None

        # Return the result.
        return response.get('response', {}).get('result')

    except Exception as e:
        print(f"An error occurred: {e}")
        return None


if __name__ == '__main__':
    # Replace with the ID you want to search for.
    id_to_find = 123456

    # Call the script function.
    json_result = call_script_function(SCRIPT_ID, 'getRowByIdAsJson', [id_to_find])

    if json_result:
        print(f"JSON result: {json_result}")
    else:
        print("Failed to get JSON result.")