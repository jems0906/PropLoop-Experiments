from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import current_user, reviewer
from app.api.routes.core import protect_requests
from app.auth_models import AuthState
from app.database import Base, get_db
from app.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
ACTOR = SimpleNamespace(id=1, name="Test reviewer", role="reviewer", active=True)


@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine)
    with TestingSession() as db:
        db.add(AuthState(id=1, setup_complete=False, generation=0))
        db.commit()

    def override_db():
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[current_user] = lambda: ACTOR
    app.dependency_overrides[reviewer] = lambda: ACTOR
    app.dependency_overrides[protect_requests] = lambda: None
    with patch("app.main.init_db"):
        with TestClient(app) as test_client:
            yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def create_experiment(client):
    response = client.post("/api/experiments", json={
        "name": "Rent reminder pilot", "hypothesis": "Personal reminders improve on-time rent recovery.",
        "problem_statement": "Overdue rent outreach is inconsistent and slow.", "target_metric": "On-time recovery rate", "template_id": "rent-delinquency",
    })
    assert response.status_code == 201
    return response.json()


def build_experiment(client):
    item = create_experiment(client)
    path = f"/api/experiments/{item['id']}"
    assert client.post(path + "/hypothesis/approve").status_code == 200
    assert client.post(path + "/spec/generate").status_code == 200
    assert client.post(path + "/spec/approve").status_code == 200
    response = client.post(path + "/plan/approve")
    assert response.status_code == 200
    return response.json()


def measure_experiment(client):
    item = build_experiment(client)
    for task in item["tasks"]:
        assert client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}).status_code == 200
    assert client.post(f"/api/experiments/{item['id']}/build/approve").status_code == 200
    return item


def test_all_stage_gates_and_repeat_approvals(client):
    item = create_experiment(client)
    path = f"/api/experiments/{item['id']}"
    assert client.post(path + "/spec/generate").status_code == 409
    assert client.post(path + "/plan/approve").status_code == 409
    assert client.post(path + "/hypothesis/approve").status_code == 200
    assert client.post(path + "/hypothesis/approve").status_code == 409
    assert client.post(path + "/spec/generate").status_code == 200
    assert client.post(path + "/spec/approve").status_code == 200
    built = client.post(path + "/plan/approve").json()
    assert client.post(path + "/spec/approve").status_code == 409
    assert client.post(path + "/plan/approve").status_code == 409
    assert client.get(path).json()["tasks"] == built["tasks"]
    assert client.post(path + "/build/approve").status_code == 409
    for task in built["tasks"]:
        client.patch(f"/api/tasks/{task['id']}", json={"status": "done"})
    assert client.get(path).json()["stage"] == "build"
    assert client.post(path + "/build/approve").status_code == 200
    assert client.patch(f"/api/tasks/{built['tasks'][0]['id']}", json={"status": "todo"}).status_code == 409
    assert client.post(path + "/measure/approve").status_code == 409
    assert client.post(path + "/metrics", json={"name": "Recovery rate", "baseline": 60, "observed": 75, "sample_size": 100}).status_code == 201
    assert client.post(path + "/measure/approve").status_code == 200
    response = client.post(path + "/decisions", json={"outcome": "ship", "rationale": "Reviewed outcomes meet the acceptance criteria."})
    assert response.status_code == 201
    assert response.json()["reviewer_name"] == ACTOR.name
    assert client.post(path + "/decisions", json={"outcome": "ship", "rationale": "Repeat approval should not be accepted."}).status_code == 409
    assert [row["stage"] for row in client.get(path).json()["approvals"]] == ["hypothesis", "design", "plan", "build", "measure", "decision"]


def test_blocker_prevents_progression(client):
    item = create_experiment(client)
    path = f"/api/experiments/{item['id']}"
    client.patch(path + "/blocker", json={"blocker": "Missing verified baseline"})
    assert client.post(path + "/hypothesis/approve").status_code == 409
    client.patch(path + "/blocker", json={"blocker": None})
    assert client.post(path + "/hypothesis/approve").status_code == 200


def test_complete_draft_editing_and_validation(client):
    item = create_experiment(client)
    path = f"/api/experiments/{item['id']}"
    client.post(path + "/hypothesis/approve")
    generated = client.post(path + "/spec/generate").json()
    spec = generated["spec"]
    spec.update(user_story="Edited by the experiment owner before approval.", estimated_effort="2 days")
    assert client.put(path + "/spec", json={"spec": spec}).status_code == 200
    assert client.put(path + "/spec", json={"spec": {}}).status_code == 422
    client.post(path + "/spec/approve")
    spec["implementation_checklist"][0]["title"] = "Reviewed task title"
    assert client.put(path + "/spec", json={"spec": spec}).status_code == 200
    spec["design_brief"] = "An unapproved change to a previously approved design."
    assert client.put(path + "/spec", json={"spec": spec}).status_code == 409


def test_provider_failure_preserves_reviewed_draft(client):
    from fastapi import HTTPException
    item = create_experiment(client)
    path = f"/api/experiments/{item['id']}"
    client.post(path + "/hypothesis/approve")
    original = client.post(path + "/spec/generate").json()["spec"]
    with patch("app.api.routes.core.generate_spec", side_effect=HTTPException(502, "Invalid provider draft")):
        assert client.post(path + "/spec/generate").status_code == 502
    assert client.get(path).json()["spec"] == original


def test_before_after_is_descriptive_not_causal(client):
    item = measure_experiment(client)
    response = client.post(f"/api/experiments/{item['id']}/metrics", json={"name": "Time to assignment", "baseline": 42, "observed": 29, "unit": "min", "direction": "lower", "sample_size": 48})
    assert response.status_code == 201
    assert response.json()["improved"] is True
    assert response.json()["confidence"]["significant"] is False
    assert "Descriptive" in response.json()["confidence"]["label"]


def test_controlled_outcomes_use_observed_denominators(client):
    item = measure_experiment(client)
    path = f"/api/experiments/{item['id']}"
    arms = {"control": [], "treatment": []}
    for index in range(30):
        key = f"participant-{index:03}"
        response = client.post(path + "/assignments", json={"subject_key": key})
        assert response.status_code == 201
        arm = response.json()["variant"]
        duplicate = client.post(path + "/assignments", json={"subject_key": key}).json()
        assert duplicate["variant"] == arm
        arms[arm].append(key)
    for arm, keys in arms.items():
        for index, key in enumerate(keys[:5]):
            payload = {"exposed": True, "completed": arm == "treatment", "errored": arm == "control", "csat": 2 + index * .1 if arm == "control" else 4 + index * .1, "duration_minutes": 40 + index if arm == "control" else 20 + index}
            assert client.put(path + "/observations/" + key, json=payload).status_code == 200
    response = client.get(path).json()
    by_name = {metric["name"]: metric for metric in response["computed_metrics"]}
    assert by_name["Task completion rate"]["control_sample_size"] == 5
    assert by_name["Task completion rate"]["treatment_sample_size"] == 5
    assert by_name["Task completion rate"]["confidence"]["significant"] is True
    assert by_name["Task duration"]["time_saved_minutes"] == 20
    assert by_name["Simulated CSAT"]["confidence"]["method"].startswith("Welch")
    assert client.post(path + "/metrics", json={"name": "Manual control", "baseline": 30, "observed": 45, "comparison_mode": "controlled"}).status_code == 422
    assert client.put(path + "/observations/not-enrolled", json={"exposed": True}).status_code == 404
    assert client.put(path + "/observations/" + arms["control"][0], json={"exposed": False, "completed": True}).status_code == 422


@pytest.mark.parametrize("outcome,stage", [("iterate", "hypothesis"), ("stop", "stopped")])
def test_decision_and_iteration_snapshot(client, outcome, stage):
    item = measure_experiment(client)
    path = f"/api/experiments/{item['id']}"
    client.post(path + "/metrics", json={"name": "Recovery rate", "baseline": 60, "observed": 59})
    client.post(path + "/measure/approve")
    assert client.post(path + "/decisions", json={"outcome": outcome, "rationale": "Evidence requires reviewing the next direction."}).status_code == 201
    current = client.get(path).json()
    assert current["stage"] == stage
    if outcome == "iterate":
        assert current["cycle"] == 2
        assert current["history"][0]["snapshot"]["metrics"]
        assert current["history"][0]["snapshot"]["tasks"]
        assert not current["tasks"] and not current["metrics"] and current["spec"] is None
        assert client.post(path + "/spec/generate").status_code == 409
        assert current["history"][0]["snapshot"]["stage"] == "decision"
        assert current["history"][0]["snapshot"]["decisions"][-1]["outcome"] == "iterate"


def test_quality_tools_and_real_trends(client):
    item = create_experiment(client)
    path = f"/api/experiments/{item['id']}"
    assert len(client.get("/api/templates").json()) == 5
    assert client.post(path + "/quality/coverage", json={}).status_code == 422
    assert client.post(path + "/quality/coverage", json={"coverage_before": 71, "coverage_after": 83}).json()["content"]["delta"] == 12
    for kind in ["pr-checklist", "adr", "release-notes"]:
        assert client.post(path + "/quality/" + kind).status_code == 201
    risk = client.post(path + "/quality/refactor-risk", json={"files_changed": 8, "lines_changed": 320, "dependency_changes": 1, "coverage_before": 83, "coverage_after": 78, "tests_passed": 18, "tests_total": 20})
    assert risk.json()["content"]["factors"]["test_pass_rate"] == 90
    baseline = {"lint_issues": 7, "tests_passed": 18, "tests_total": 20, "coverage_after": 70}
    assert client.post(path + "/quality/code-quality", json=baseline).json()["content"]["trend"] == "baseline"
    assert client.post(path + "/quality/code-quality", json=baseline).json()["content"]["trend"] == "unchanged"
    assert len(client.get("/api/quality/trends").json()) == 3
    trend = client.get("/api/dashboards/overview").json()["trend"]
    assert sum(row["active"] for row in trend) == 1
    assert sum(row["shipped"] for row in trend) == 0


def test_ci_ingestion_token(client, monkeypatch):
    from app.config import settings
    item = create_experiment(client)
    monkeypatch.setattr(settings, "quality_ingest_token", "test-quality-token")
    payload = {"experiment_id": item["id"], "lint_issues": 0, "tests_passed": 20, "tests_total": 20, "coverage_after": 81.5}
    assert client.post("/api/quality/ingest", json=payload).status_code == 401
    response = client.post("/api/quality/ingest", json=payload, headers={"Authorization": "Bearer test-quality-token"})
    assert response.status_code == 201
    assert response.json()["content"]["test_pass_rate"] == 100
    assert client.post("/api/quality/ingest", json={"experiment_id": item["id"]}, headers={"Authorization": "Bearer test-quality-token"}).status_code == 422


def test_real_account_roles_and_csrf_protect_core_routes(client, monkeypatch):
    from app.config import settings
    app.dependency_overrides.pop(current_user)
    app.dependency_overrides.pop(reviewer)
    app.dependency_overrides.pop(protect_requests)
    monkeypatch.setattr(settings, "bootstrap_token", "core-test-bootstrap-only")
    monkeypatch.setattr(settings, "cookie_secure", False)
    monkeypatch.setattr(settings, "frontend_url", "http://localhost:5173")
    assert client.get("/api/experiments").status_code == 401
    admin = client.post("/api/auth/bootstrap", headers={"Origin": settings.frontend_url, "X-Bootstrap-Token": settings.bootstrap_token}, json={
        "name": "Core Admin", "email": "core-admin@example.test", "password": "Core-Admin-Test-Only-12345",
    })
    assert admin.status_code in (200, 201)
    client.headers.update({"Origin": settings.frontend_url, "X-CSRF-Token": admin.json()["csrf_token"]})
    invite = client.post("/api/auth/invites", json={"email": "core-member@example.test", "role": "member"})
    assert invite.status_code == 201
    member = client.post("/api/auth/accept-invite", json={
        "token": invite.json()["token"], "name": "Core Member",
        "email": "core-member@example.test", "password": "Core-Member-Test-Only-12345",
    })
    assert member.status_code in (200, 201)
    client.headers.update({"X-CSRF-Token": member.json()["csrf_token"]})
    item = create_experiment(client)
    path = f"/api/experiments/{item['id']}"
    assert client.post(path + "/hypothesis/approve").status_code == 403
    client.headers.pop("X-CSRF-Token")
    assert client.patch(path + "/blocker", json={"blocker": "Should not be saved"}).status_code == 403
    assert client.get(path).json()["blocker"] is None
