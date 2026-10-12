from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import current_user, require_same_origin
from app.auth_models import AuthUser
from app.coding_agent import configuration_status
from app.database import Base, get_db
from app.main import app
from app.models import AgentRun, Experiment, ImplementationTask

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
ACTOR = SimpleNamespace(id=1, name="Test admin", role="admin", active=True)


@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine)
    with TestingSession() as db:
        db.add(AuthUser(
            id=1, email="agent-test@example.test", name="Test admin",
            password_hash="test-hash", role="admin", active=True,
        ))
        db.commit()

    def override_db():
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[current_user] = lambda: ACTOR
    app.dependency_overrides[require_same_origin] = lambda: None
    with patch("app.main.init_db"):
        with TestClient(app) as test_client:
            yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def create_plan(client):
    with TestingSession() as db:
        experiment = Experiment(
            name="Agent test pilot",
            hypothesis="Routing assistant reduces first response time.",
            problem_statement="Routing is currently manual and slow.",
            target_metric="First response time",
            stage="build",
            spec_approved=True,
            plan_approved=True,
        )
        db.add(experiment)
        db.flush()
        db.add(ImplementationTask(
            experiment_id=experiment.id,
            title="Implement safe routing",
            description="Keep low confidence results in human review.",
        ))
        db.commit()
        return experiment.id


def test_agent_endpoint_requires_authentication():
    response = TestClient(app).get("/api/agent/status")
    assert response.status_code == 401


def test_agent_endpoint_rejects_non_admin_users(client):
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id=2, name="Member", role="member", active=True)
    response = client.get("/api/agent/status")
    assert response.status_code == 403


def test_agent_only_runs_from_approved_unblocked_plan(client, monkeypatch):
    with TestingSession() as db:
        experiment = Experiment(
            name="Unapproved pilot", hypothesis="A longer hypothesis for validation.",
            problem_statement="A sufficiently detailed problem statement.",
            target_metric="Activation", stage="hypothesis",
        )
        db.add(experiment)
        db.commit()
        experiment_id = experiment.id
    monkeypatch.setattr("app.api.routes.agent.configuration_status", lambda: {"enabled": True, "missing": [], "repository": "owner/repo"})
    assert client.post(f"/api/experiments/{experiment_id}/agent-runs").status_code == 409
    with TestingSession() as db:
        experiment = db.get(Experiment, experiment_id)
        experiment.stage = "build"
        experiment.spec_approved = True
        experiment.plan_approved = True
        experiment.blocker = "Resolve first"
        db.commit()
        db.add(ImplementationTask(experiment_id=experiment_id, title="Complete the reviewed task"))
        db.commit()
    assert client.post(f"/api/experiments/{experiment_id}/agent-runs").status_code == 409
    assert client.get(f"/api/experiments/{experiment_id}/agent-runs").json() == []


def test_agent_endpoint_reports_missing_credentials_without_starting_run(client, monkeypatch):
    experiment_id = create_plan(client)
    monkeypatch.setattr("app.api.routes.agent.configuration_status", lambda: {
        "enabled": False, "missing": ["OPENAI_API_KEY"], "repository": "owner/repo",
    })
    response = client.post(f"/api/experiments/{experiment_id}/agent-runs")
    assert response.status_code == 503
    assert response.json()["detail"] == "GitHub coding agent is not configured: OPENAI_API_KEY"
    with TestingSession() as db:
        assert db.query(AgentRun).count() == 0


def test_agent_endpoint_persists_pr_and_lists_it(client, monkeypatch):
    experiment_id = create_plan(client)
    monkeypatch.setattr("app.api.routes.agent.configuration_status", lambda: {
        "enabled": True, "missing": [], "repository": "owner/repo",
    })
    with patch("app.api.routes.agent.create_agent_pull_request", return_value={
        "repository": "owner/repo", "branch": "proploop/experiment-1-agent-deadbeef",
        "pull_request_url": "https://github.com/owner/repo/pull/1",
        "summary": "AI-generated proposal awaiting human review.",
    }):
        response = client.post(f"/api/experiments/{experiment_id}/agent-runs")
    assert response.status_code == 201
    result = response.json()
    assert result["status"] == "pull_request"
    assert result["pull_request_url"] == "https://github.com/owner/repo/pull/1"
    assert "github_token" not in result
    assert client.get(f"/api/experiments/{experiment_id}/agent-runs").json() == [result]


def test_failed_provider_run_is_persisted_without_provider_response_details(client, monkeypatch):
    experiment_id = create_plan(client)
    monkeypatch.setattr("app.api.routes.agent.configuration_status", lambda: {
        "enabled": True, "missing": [], "repository": "owner/repo",
    })
    with patch(
        "app.api.routes.agent.create_agent_pull_request",
        side_effect=HTTPException(502, "OpenAI could not generate a valid implementation proposal."),
    ):
        response = client.post(f"/api/experiments/{experiment_id}/agent-runs")
    assert response.status_code == 502
    with TestingSession() as db:
        run = db.query(AgentRun).one()
        assert run.status == "failed"
        assert run.error == "OpenAI could not generate a valid implementation proposal."
