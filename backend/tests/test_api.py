import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine)

    def override_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
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


def test_lifecycle_approval_gates_and_decision(client):
    experiment = create_experiment(client)
    experiment_id = experiment["id"]
    assert client.post(f"/api/experiments/{experiment_id}/plan/approve").status_code == 409
    assert client.post(f"/api/experiments/{experiment_id}/spec/generate").status_code == 200
    assert client.post(f"/api/experiments/{experiment_id}/spec/approve").status_code == 200
    planned = client.post(f"/api/experiments/{experiment_id}/plan/approve")
    assert planned.status_code == 200
    assert len(planned.json()["tasks"]) == 4
    assert client.post(f"/api/experiments/{experiment_id}/decisions", json={"outcome": "ship", "rationale": "Ready to release to all properties."}).status_code == 409
    for task in planned.json()["tasks"]:
        assert client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}).status_code == 200
    assert client.post(f"/api/experiments/{experiment_id}/metrics", json={"name": "On-time recovery rate", "baseline": 61, "observed": 72, "unit": "%", "sample_size": 180}).status_code == 201
    assert client.get(f"/api/experiments/{experiment_id}").json()["stage"] == "decision"
    decision = client.post(f"/api/experiments/{experiment_id}/decisions", json={"outcome": "ship", "rationale": "The measured improvement clears our rollout threshold."})
    assert decision.status_code == 201
    assert client.get(f"/api/experiments/{experiment_id}").json()["stage"] == "complete"


def test_quality_artifact_and_template_endpoints(client):
    experiment = create_experiment(client)
    templates = client.get("/api/templates").json()
    assert len(templates) == 5
    assert any(template["id"] == "rent-delinquency" for template in templates)
    artifact = client.post(f"/api/experiments/{experiment['id']}/quality/pr-checklist")
    assert artifact.status_code == 201
    assert len(artifact.json()["content"]["items"]) >= 5


def test_percentage_confidence_is_reported(client):
    experiment = create_experiment(client)
    client.post(f"/api/experiments/{experiment['id']}/spec/generate")
    client.post(f"/api/experiments/{experiment['id']}/spec/approve")
    client.post(f"/api/experiments/{experiment['id']}/plan/approve")
    response = client.post(f"/api/experiments/{experiment['id']}/metrics", json={"name": "Activation", "baseline": 30, "observed": 48, "sample_size": 200})
    assert response.status_code == 201
    assert response.json()["confidence"]["confidence"] is not None


def test_lower_is_better_metric_is_reported_as_improved(client):
    experiment = create_experiment(client)
    client.post(f"/api/experiments/{experiment['id']}/spec/generate")
    client.post(f"/api/experiments/{experiment['id']}/spec/approve")
    client.post(f"/api/experiments/{experiment['id']}/plan/approve")
    response = client.post(f"/api/experiments/{experiment['id']}/metrics", json={"name": "Time to assignment", "baseline": 42, "observed": 29, "unit": "min", "direction": "lower", "sample_size": 48})
    assert response.status_code == 201
    assert response.json()["improved"] is True


def test_generated_spec_can_be_edited_before_approval(client):
    experiment = create_experiment(client)
    generated = client.post(f"/api/experiments/{experiment['id']}/spec/generate").json()
    generated["spec"]["user_story"] = "Edited by the experiment owner before approval."
    updated = client.put(f"/api/experiments/{experiment['id']}/spec", json={"spec": generated["spec"]})
    assert updated.status_code == 200
    assert updated.json()["spec"]["user_story"].startswith("Edited by")


def test_controlled_assignments_are_sticky_and_metrics_use_arm_sizes(client):
    experiment = create_experiment(client)
    experiment_id = experiment["id"]
    client.post(f"/api/experiments/{experiment_id}/spec/generate")
    client.post(f"/api/experiments/{experiment_id}/spec/approve")
    client.post(f"/api/experiments/{experiment_id}/plan/approve")

    first = client.post(f"/api/experiments/{experiment_id}/assignments", json={"subject_key": "participant-000"}).json()
    duplicate = client.post(f"/api/experiments/{experiment_id}/assignments", json={"subject_key": "participant-000"}).json()
    assert first["variant"] == duplicate["variant"]
    assert first["assignment_summary"] == duplicate["assignment_summary"]

    summary = first["assignment_summary"]
    for index in range(1, 100):
        if summary["control"] >= 2 and summary["treatment"] >= 2:
            break
        summary = client.post(f"/api/experiments/{experiment_id}/assignments", json={"subject_key": f"participant-{index:03}"}).json()["assignment_summary"]
    assert summary["control"] >= 2 and summary["treatment"] >= 2

    metric = client.post(f"/api/experiments/{experiment_id}/metrics", json={
        "name": "Activation rate", "baseline": 30, "observed": 45, "unit": "%",
        "comparison_mode": "controlled", "sample_size": 1,
    })
    assert metric.status_code == 201
    assert metric.json()["control_sample_size"] == summary["control"]
    assert metric.json()["treatment_sample_size"] == summary["treatment"]
    assert metric.json()["sample_size"] == summary["control"] + summary["treatment"]
    assert metric.json()["confidence"]["confidence"] is not None
    current = client.get(f"/api/experiments/{experiment_id}").json()
    assert current["assignment_summary"] == summary


def test_quality_metrics_require_and_store_measured_evidence(client):
    experiment = create_experiment(client)
    experiment_id = experiment["id"]
    assert client.post(f"/api/experiments/{experiment_id}/quality/coverage", json={}).status_code == 422

    coverage = client.post(f"/api/experiments/{experiment_id}/quality/coverage", json={"coverage_before": 71, "coverage_after": 83})
    assert coverage.status_code == 201
    assert coverage.json()["content"]["delta"] == 12

    evidence = {"files_changed": 8, "lines_changed": 320, "dependency_changes": 1, "coverage_before": 83, "coverage_after": 78, "tests_passed": 18, "tests_total": 20}
    risk = client.post(f"/api/experiments/{experiment_id}/quality/refactor-risk", json=evidence)
    assert risk.status_code == 201
    assert risk.json()["content"]["factors"]["dependency_changes"] == 1
    assert risk.json()["content"]["factors"]["test_pass_rate"] == 90


def test_code_quality_trend_uses_recorded_evidence(client):
    experiment = create_experiment(client)
    experiment_id = experiment["id"]
    first = client.post(f"/api/experiments/{experiment_id}/quality/code-quality", json={"lint_issues": 7, "tests_passed": 18, "tests_total": 20, "coverage_after": 70})
    second = client.post(f"/api/experiments/{experiment_id}/quality/code-quality", json={"lint_issues": 2, "tests_passed": 20, "tests_total": 20, "coverage_after": 79})
    assert first.status_code == 201
    assert first.json()["content"]["trend"] == "baseline"
    assert second.status_code == 201
    assert second.json()["content"]["trend"] == "improving"
    history = client.get("/api/quality/trends").json()
    assert len(history) == 2
    assert history[-1]["experiment_id"] == experiment_id


def test_ci_quality_ingestion_requires_token_and_records_snapshot(client, monkeypatch):
    from app.config import settings

    experiment = create_experiment(client)
    monkeypatch.setattr(settings, "quality_ingest_token", "test-quality-token")
    payload = {"experiment_id": experiment["id"], "lint_issues": 0, "tests_passed": 20, "tests_total": 20, "coverage_after": 81.5}
    assert client.post("/api/quality/ingest", json=payload).status_code == 401
    response = client.post("/api/quality/ingest", json=payload, headers={"Authorization": "Bearer test-quality-token"})
    assert response.status_code == 201
    assert response.json()["content"]["coverage"] == 81.5
    assert response.json()["content"]["test_pass_rate"] == 100


@pytest.mark.parametrize(("outcome", "expected_stage"), [("iterate", "hypothesis"), ("stop", "stopped")])
def test_iterate_and_stop_decisions_are_recorded(client, outcome, expected_stage):
    experiment = create_experiment(client)
    experiment_id = experiment["id"]
    client.post(f"/api/experiments/{experiment_id}/spec/generate")
    client.post(f"/api/experiments/{experiment_id}/spec/approve")
    planned = client.post(f"/api/experiments/{experiment_id}/plan/approve").json()
    for task in planned["tasks"]:
        client.patch(f"/api/tasks/{task['id']}", json={"status": "done"})
    client.post(f"/api/experiments/{experiment_id}/metrics", json={"name": "Recovery rate", "baseline": 61, "observed": 58, "sample_size": 120})
    response = client.post(f"/api/experiments/{experiment_id}/decisions", json={"outcome": outcome, "rationale": "The team reviewed outcomes and the guardrail metrics."})
    assert response.status_code == 201
    assert response.json()["outcome"] == outcome
    current = client.get(f"/api/experiments/{experiment_id}").json()
    assert current["stage"] == expected_stage
    if outcome == "iterate":
        assert current["spec_approved"] is False
        assert current["plan_approved"] is False
