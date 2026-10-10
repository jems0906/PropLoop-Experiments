from unittest.mock import patch

import pytest
from fastapi import HTTPException
from app.spec_generator import generate_spec
from app.spec_generator import _mock_spec
import httpx
import json


EXPERIMENT = {"name": "Triage test", "hypothesis": "Triage saves staff time", "target_metric": "Time saved", "problem_statement": "Manual triage is slow"}


def test_mock_contract_is_complete():
    with patch("app.spec_generator.settings.ai_provider", "mock"):
        result = generate_spec(EXPERIMENT)
    assert result["implementation_checklist"]
    assert result["success_metric"]["guardrails"]


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini"])
def test_explicit_provider_with_missing_key_fails(provider):
    with patch("app.spec_generator.settings.ai_provider", provider), patch(f"app.spec_generator.settings.{provider}_api_key", None):
        with pytest.raises(HTTPException) as error:
            generate_spec(EXPERIMENT)
    assert error.value.status_code == 503


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini"])
def test_malformed_hosted_spec_is_rejected(provider):
    with patch("app.spec_generator.settings.ai_provider", provider), patch(f"app.spec_generator.settings.{provider}_api_key", "test-only-key"), patch(f"app.spec_generator._{provider}_spec", return_value={"user_story": "incomplete"}):
        with pytest.raises(HTTPException) as error:
            generate_spec(EXPERIMENT)
    assert error.value.status_code == 502


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini"])
def test_hosted_adapter_parses_complete_response(provider):
    draft = _mock_spec(EXPERIMENT)
    draft.pop("provider")
    text = json.dumps(draft)
    body = {
        "openai": {"choices": [{"message": {"content": text}}]},
        "anthropic": {"content": [{"text": text}]},
        "gemini": {"candidates": [{"content": {"parts": [{"text": text}]}}]},
    }[provider]
    response = httpx.Response(200, json=body, request=httpx.Request("POST", "https://provider.invalid"))
    with patch("app.spec_generator.settings.ai_provider", provider), patch(f"app.spec_generator.settings.{provider}_api_key", "test-only-key"), patch("app.spec_generator.httpx.post", return_value=response):
        result = generate_spec(EXPERIMENT)
    assert result["provider"] == provider
    assert result["implementation_checklist"] == draft["implementation_checklist"]


def test_network_failure_is_explicit():
    with patch("app.spec_generator.settings.ai_provider", "openai"), patch("app.spec_generator.settings.openai_api_key", "test-only-key"), patch("app.spec_generator.httpx.post", side_effect=httpx.ConnectError("provider offline")):
        with pytest.raises(HTTPException) as error:
            generate_spec(EXPERIMENT)
    assert error.value.status_code == 502
