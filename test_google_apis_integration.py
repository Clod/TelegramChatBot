import os
import pytest
import bot_modules.google_apis as api
import logging


os.environ["GOOGLE_FORM_ID"] = "1DNf2FmTmF48Vj5F4MUR6IF6GE85WS4sEoZlN4laONtk"
os.environ["GOOGLE_PATIENT_ID"] = "123456"

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
    # Verify the returned response contains answers with a matching patient_id
    answers = result.get("answers", {})
    # There should be at least one answer segment
    assert answers, "No answers field in result"
    # Extract any answer value and assert it matches requested patient_id
    found = any(
        ans_data.get("textAnswers", {}).get("answers", [{}])[0].get("value") == patient_id
        for ans_data in answers.values()
    )
    assert found, f"No answer matching patient_id={patient_id} in response"

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
