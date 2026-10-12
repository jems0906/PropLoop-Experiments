import base64
import json

import httpx
import pytest
from fastapi import HTTPException

from app import coding_agent


EXPERIMENT = {
    "id": 12,
    "name": "Maintenance triage pilot",
    "hypothesis": "Automatic categories reduce assignment time without increasing misroutes.",
    "problem_statement": "Teams manually route maintenance tickets.",
    "target_metric": "Time to assignment",
    "approved_spec": {
        "design_brief": "Keep low-confidence ticket routing in a human review queue.",
        "user_story": "As an operator, I can review the suggested assignment.",
        "success_metric": {"name": "Time to assignment", "definition": "Minutes until owner assignment.", "guardrails": ["Misroute rate"]},
        "risks": [{"risk": "Wrong route", "mitigation": "Require review for uncertain cases."}],
        "acceptance_criteria": ["Operators can correct a suggested route."],
    },
}
TASKS = [{"title": "Add routing review", "description": "Keep low-confidence routes in a human queue."}]


def test_configuration_status_never_returns_secrets(monkeypatch):
    monkeypatch.setattr(coding_agent.settings, "openai_api_key", "not-returned")
    monkeypatch.setattr(coding_agent.settings, "github_token", "not-returned")
    monkeypatch.setattr(coding_agent.settings, "github_repository", "owner/repository")
    result = coding_agent.configuration_status()
    assert result == {
        "enabled": True,
        "missing": [],
        "model": coding_agent.settings.coding_agent_model,
        "repository": "owner/repository",
    }
    assert "not-returned" not in json.dumps(result)


def test_source_allowlist_excludes_credentials_auth_and_deployment_files():
    assert coding_agent._eligible_path("backend/app/measurement.py")
    assert coding_agent._eligible_path("frontend/src/components/ExperimentBoard.jsx")
    assert not coding_agent._eligible_path("backend/app/auth.py")
    assert not coding_agent._eligible_path("backend/app/config.py")
    assert not coding_agent._eligible_path("backend/.env")
    assert not coding_agent._eligible_path(".github/workflows/ci.yml")
    assert not coding_agent._eligible_path("frontend/package.json")


def test_openai_changes_cannot_escape_source_context_or_add_secrets(monkeypatch):
    class Response:
        content = b"{}"

        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class Client:
        def post(self, *args, **kwargs):
            content = json.dumps({
                "summary": "A clear enough implementation proposal.",
                "changes": [{
                    "path": "backend/app/auth.py",
                    "content": "safe = True",
                    "reason": "This must be rejected.",
                }],
            })
            return Response({"choices": [{"message": {"content": content}}]})

    with pytest.raises(coding_agent.AgentFailure, match="safety checks"):
        coding_agent._generate_changes(Client(), "fake-key", "test-model", EXPERIMENT, TASKS, {"backend/app/measurement.py": "source"})


def test_end_to_end_agent_integration_uses_allowlisted_context_and_creates_draft_pr(monkeypatch):
    requests = []
    generated = {
        "summary": "Adds a tested experiment-specific participant review.",
        "changes": [{
            "path": "backend/app/measurement.py",
            "content": "def new_measurement():\n    return True\n",
            "reason": "Implements the approved experiment task.",
        }],
    }

    def handler(request):
        requests.append(request)
        path = request.url.path
        if path.endswith("/branches/main"):
            payload = {"commit": {"sha": "base-sha"}}
        elif path.endswith("/git/trees/base-sha"):
            payload = {"tree": [
                {"path": "backend/app/measurement.py", "type": "blob"},
                {"path": "backend/app/secrets.py", "type": "blob"},
                {"path": "backend/app/auth.py", "type": "blob"},
                {"path": "backend/.env", "type": "blob"},
                {"path": ".github/workflows/ci.yml", "type": "blob"},
            ]}
        elif path.endswith("/contents/backend/app/measurement.py"):
            payload = {"encoding": "base64", "content": base64.b64encode(b"def old_measurement():\n    return False\n").decode()}
        elif path.endswith("/contents/backend/app/secrets.py"):
            payload = {"encoding": "base64", "content": base64.b64encode(b"api_key = 'sk-" + b"x" * 28 + b"'\n").decode()}
        elif path == "/v1/chat/completions":
            payload = {"choices": [{"message": {"content": json.dumps(generated)}}]}
        elif path.endswith("/git/trees"):
            payload = {"sha": "new-tree"}
        elif path.endswith("/git/commits"):
            payload = {"sha": "new-commit"}
        elif path.endswith("/git/refs"):
            payload = {}
        elif path.endswith("/pulls"):
            payload = {"html_url": "https://github.com/owner/repository/pull/14", "draft": True}
        else:
            return httpx.Response(404, json={"message": "unexpected request"})
        return httpx.Response(200, json=payload)

    real_client = httpx.Client

    class ClientFactory:
        def __new__(cls, *args, **kwargs):
            return real_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(coding_agent.httpx, "Client", ClientFactory)
    monkeypatch.setattr(coding_agent.settings, "openai_api_key", "test-openai")
    monkeypatch.setattr(coding_agent.settings, "github_token", "test-github")
    monkeypatch.setattr(coding_agent.settings, "github_repository", "owner/repository")
    monkeypatch.setattr(coding_agent.settings, "github_base_branch", "main")

    result = coding_agent.create_agent_pull_request(EXPERIMENT, TASKS, 9)

    assert result["pull_request_url"] == "https://github.com/owner/repository/pull/14"
    assert result["repository"] == "owner/repository"
    assert result["branch"].startswith("proploop/experiment-12-agent-")
    openai_request = next(request for request in requests if request.url.path == "/v1/chat/completions")
    assert openai_request.headers["Authorization"] == "Bearer test-openai"
    github_request = next(request for request in requests if request.url.host == "api.github.com")
    assert github_request.headers["Authorization"] == "Bearer test-github"
    prompt = json.loads(json.loads(openai_request.content)["messages"][0]["content"])
    assert set(prompt["repository_source"]) == {"backend/app/measurement.py"}
    assert prompt["approved_spec"]["design_brief"] == EXPERIMENT["approved_spec"]["design_brief"]
    pull_request_request = next(request for request in requests if request.url.path.endswith("/pulls"))
    assert json.loads(pull_request_request.content)["draft"] is True
    assert "No tests were executed" in json.loads(pull_request_request.content)["body"]


def test_missing_agent_settings_fail_closed(monkeypatch):
    monkeypatch.setattr(coding_agent.settings, "openai_api_key", None)
    monkeypatch.setattr(coding_agent.settings, "github_token", None)
    monkeypatch.setattr(coding_agent.settings, "github_repository", None)
    with pytest.raises(HTTPException) as error:
        coding_agent.create_agent_pull_request(EXPERIMENT, TASKS, 1)
    assert error.value.status_code == 503
    assert "OPENAI_API_KEY" in error.value.detail
    assert "GITHUB_TOKEN" in error.value.detail
