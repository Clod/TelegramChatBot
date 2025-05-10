"""
test_google_apis_integration.py

Integration tests for Google APIs integration in the telegram_bot_webhook project.

This script contains two pytest integration tests:

1. test_real_form_response_by_patient_id:
   - Fetches a real Google Form response by patient ID.
   - Requires environment variables:
     - GOOGLE_FORM_ID: the ID of the Google Form to query.
     - GOOGLE_PATIENT_ID: the patient ID to filter responses.
     - SERVICE_ACCOUNT_FILE: the path to the JSON file for Google service account credentials.
   - Usage:
         export GOOGLE_FORM_ID=<your_form_id>
         export GOOGLE_PATIENT_ID=<your_patient_id>
         export SERVICE_ACCOUNT_FILE=<path_to_service_account_json>
         pytest test_google_apis_integration.py::test_real_form_response_by_patient_id -q

2. test_get_question_id_title_map:
   - Retrieves the mapping of question IDs to titles for a Google Form.
   - Requires environment variable:
     - GOOGLE_FORM_ID: the ID of the Google Form.
   - Usage:
         export GOOGLE_FORM_ID=<your_form_id>
         pytest test_google_apis_integration.py::test_get_question_id_title_map -q

To run all tests in this file:
    pytest test_google_apis_integration.py -q

"""

import os
import pytest
import bot_modules.google_apis as api
import logging

# pytest test_google_apis_integration.py -q

os.environ["GOOGLE_FORM_ID"] = "1DNf2FmTmF48Vj5F4MUR6IF6GE85WS4sEoZlN4laONtk"
os.environ["GOOGLE_PATIENT_ID"] = "1234"

@pytest.mark.skipif(
    not os.getenv("GOOGLE_FORM_ID") or not os.getenv("GOOGLE_PATIENT_ID"),
    reason="Integration test requires GOOGLE_FORM_ID and GOOGLE_PATIENT_ID environment variables"
)
def test_real_form_response_by_patient_id():
    """
    Integration test: fetch a real Google Form response by patient_id.
    Requires environment variables:
      - GOOGLE_FORM_ID: the Form ID to query
      - GOOGLE_PATIENT_ID: the patient_id value to match
      - SERVICE_ACCOUNT_FILE: path in config pointing to valid service account JSON
    """
    form_id = os.getenv("GOOGLE_FORM_ID")
    patient_id = os.getenv("GOOGLE_PATIENT_ID")

    # Verify service account configuration
    svc_file = getattr(api.config, "SERVICE_ACCOUNT_FILE", None)
    assert svc_file and os.path.exists(svc_file), "SERVICE_ACCOUNT_FILE is not configured or missing"

    # Call the function under test
    result, error = api.get_google_form_response_by_patient_id(form_id, patient_id)
    logging.info(f"Retrieved Google Form response for patient_id={patient_id}: {result}, error={error}")

    # Validate the call succeeded
    assert error is None, f"Expected no error, got: {error}"
    assert isinstance(result, dict), "Expected a dict result"
    # Verify that the returned mapping contains the patient_id value
    found = any(value == patient_id for value in result.values())
    assert found, f"No answer matching patient_id={patient_id} in result mapping"

@pytest.mark.skipif(
    not os.getenv("GOOGLE_FORM_ID"),
    reason="Integration test requires GOOGLE_FORM_ID environment variable"
)
def test_get_question_id_title_map():
    """
    Integration test: retrieve question id to title mapping for a Google Form.
    Requires environment variable:
      - GOOGLE_FORM_ID: the Form ID to query
    """
    form_id = os.getenv("GOOGLE_FORM_ID")
    mapping, error = api.get_question_id_title_map(form_id)
    logging.info(f"Retrieved question id title map for form_id={form_id}: {mapping}, error={error}")
    assert error is None, f"Expected no error, got: {error}"
    assert isinstance(mapping, dict), "Expected a dict mapping"
    assert mapping, "Expected at least one question in mapping"
    # Verify keys and values are strings
    for qid, title in mapping.items():
        assert isinstance(qid, str), f"Expected question id to be a string, got {type(qid)}"
        assert isinstance(title, str), f"Expected title to be a string, got {type(title)}"
