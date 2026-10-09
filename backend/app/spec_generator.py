import json

import httpx

from app.config import settings


def generate_spec(experiment: dict) -> dict:
    """Use an optional hosted model, falling back to a deterministic local spec."""
    provider = settings.ai_provider.lower()
    if provider == "openai" and settings.openai_api_key:
        return _openai_spec(experiment)
    if provider == "anthropic" and settings.anthropic_api_key:
        return _anthropic_spec(experiment)
    if provider == "gemini" and settings.gemini_api_key:
        return _gemini_spec(experiment)
    return _mock_spec(experiment)


def _mock_spec(experiment: dict) -> dict:
    name = experiment["name"]
    metric = experiment["target_metric"]
    problem = experiment["problem_statement"]
    return {
        "user_story": f"As a property-management team member, I want {name.lower()} so that residents and owners get a faster, more consistent experience.",
        "success_metric": {"name": metric, "definition": f"Compare the {metric.lower()} against the baseline for eligible users during the experiment window.", "guardrails": ["Error rate", "Support escalation rate"]},
        "risks": [
            {"risk": "Generated output may be incomplete or inaccurate.", "mitigation": "Keep a human approval step before any resident-facing action."},
            {"risk": f"{problem}", "mitigation": "Run with a limited cohort and monitor the guardrail metrics."},
        ],
        "acceptance_criteria": [
            "The primary user can complete the target workflow without staff re-entry.",
            "A human can review, correct, and audit generated recommendations.",
            "Failures are logged and can be safely retried without duplicate actions.",
        ],
        "implementation_checklist": [
            {"title": "Map the current workflow and baseline", "description": "Confirm user roles, edge cases, and baseline measurement."},
            {"title": "Build the smallest end-to-end experience", "description": "Implement the happy path with safe fallbacks and human review."},
            {"title": "Add instrumentation and guardrails", "description": "Capture the success metric, errors, and escalation events."},
            {"title": "Test with a limited cohort", "description": "Verify acceptance criteria and compare results with baseline."},
        ],
        "estimated_effort": "3-5 engineering days",
        "design_brief": f"{problem} Focus on a reversible, limited-cohort test with a clear human override.",
        "provider": "mock",
    }


def _openai_spec(experiment: dict) -> dict:
    prompt = _prompt(experiment)
    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        json={"model": "gpt-4o-mini", "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": prompt}]},
        timeout=45,
    )
    response.raise_for_status()
    result = json.loads(response.json()["choices"][0]["message"]["content"])
    result["provider"] = "openai"
    return result


def _anthropic_spec(experiment: dict) -> dict:
    response = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": settings.anthropic_api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": "claude-3-5-haiku-latest", "max_tokens": 1600, "messages": [{"role": "user", "content": _prompt(experiment)}]},
        timeout=45,
    )
    response.raise_for_status()
    text = response.json()["content"][0]["text"]
    result = json.loads(text[text.find("{"):text.rfind("}") + 1])
    result["provider"] = "anthropic"
    return result


def _gemini_spec(experiment: dict) -> dict:
    response = httpx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        params={"key": settings.gemini_api_key},
        json={"contents": [{"parts": [{"text": _prompt(experiment)}]}], "generationConfig": {"responseMimeType": "application/json"}},
        timeout=45,
    )
    response.raise_for_status()
    result = json.loads(response.json()["candidates"][0]["content"]["parts"][0]["text"])
    result["provider"] = "gemini"
    return result


def _prompt(experiment: dict) -> str:
    return (
        "Create a concise property-management product experiment spec. Return only JSON with keys: "
        "user_story (string), success_metric (object with name, definition, guardrails array), "
        "risks (array of objects with risk and mitigation), acceptance_criteria (string array), "
        "implementation_checklist (array of objects with title and description), estimated_effort (string), "
        "design_brief (string). Keep recommendations reversible and include human review.\n"
        f"Experiment: {json.dumps(experiment)}"
    )
