import pytest
from unittest.mock import Mock
import bot_modules.google_apis as api

@pytest.fixture(autouse=True)
def fake_credentials(monkeypatch):
    # Always return a truthy credentials object for API calls
    monkeypatch.setattr(api, 'get_credentials_for_google_apis', lambda scopes: True)
    yield

def make_fake_service(form_struct, responses_struct):
    """
    Create a fake service mimicking Google Forms API:
    - service.forms().get(...).execute() -> form_struct
    - service.forms().responses().list(...).execute() -> responses_struct
    """
    fake_service = Mock()
    fake_forms = Mock()

    # service.forms() returns forms interface
    fake_service.forms.return_value = fake_forms

    # .get().execute() returns form structure
    fake_forms.get.return_value.execute.return_value = form_struct

    # .responses().list().execute() returns responses
    fake_forms.responses.return_value.list.return_value.execute.return_value = responses_struct

    return fake_service

def test_matching_response_found(monkeypatch):
    form_id = "form123"
    patient_id = "patient_42"

    # Fake form with a patient_id question
    fake_form = {
        "items": [
            {
                "questionItem": {
                    "question": {
                        "title": "patient_id",
                        "questionId": "qid1"
                    }
                }
            }
        ]
    }
    # Fake responses including one matching patient_id
    fake_responses = {
        "responses": [
            {
                "responseId": "r1",
                "answers": {
                    "qid1": {
                        "textAnswers": {
                            "answers": [{"value": patient_id}]
                        }
                    }
                }
            },
            {
                "responseId": "r2",
                "answers": {
                    "qid1": {
                        "textAnswers": {
                            "answers": [{"value": "other"}]
                        }
                    }
                }
            }
        ]
    }

    fake_service = make_fake_service(fake_form, fake_responses)
    # Patch the build function in the module
    monkeypatch.setattr(api, 'build', lambda *args, **kwargs: fake_service)

    result, error = api.get_google_form_response_by_patient_id(form_id, patient_id)
    assert error is None
    # Should return the first matching response
    assert result["responseId"] == "r1"

def test_no_matching_response(monkeypatch):
    form_id = "form456"
    patient_id = "not_present"

    fake_form = {
        "items": [
            {
                "questionItem": {
                    "question": {
                        "title": "patient_id",
                        "questionId": "qid2"
                    }
                }
            }
        ]
    }
    # Responses without the matching patient_id
    fake_responses = {
        "responses": [
            {
                "responseId": "rA",
                "answers": {
                    "qid2": {
                        "textAnswers": {
                            "answers": [{"value": "someone_else"}]
                        }
                    }
                }
            }
        ]
    }

    fake_service = make_fake_service(fake_form, fake_responses)
    monkeypatch.setattr(api, 'build', lambda *args, **kwargs: fake_service)

    result, error = api.get_google_form_response_by_patient_id(form_id, patient_id)
    assert result is None
    assert "No response found for patient_id" in error

def test_question_id_not_found(monkeypatch):
    form_id = "form789"
    patient_id = "any"

    # Fake form missing patient_id question
    fake_form = {
        "items": [
            {
                "questionItem": {
                    "question": {
                        "title": "other_question",
                        "questionId": "qidX"
                    }
                }
            }
        ]
    }
    fake_responses = {"responses": []}

    fake_service = make_fake_service(fake_form, fake_responses)
    monkeypatch.setattr(api, 'build', lambda *args, **kwargs: fake_service)

    result, error = api.get_google_form_response_by_patient_id(form_id, patient_id)
    assert result is None
    assert "patient_id question not found in form" in error
