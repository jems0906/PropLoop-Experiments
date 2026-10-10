import importlib.util
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth
from app.auth_models import AuthInvite, AuthLoginBucket, AuthSession, AuthState, AuthUser
from app.database import Base, get_db

ADMIN = {"email": "admin@example.com", "name": "Team Admin", "password": "correct horse battery staple"}
BOOTSTRAP = {"X-Bootstrap-Token": "test-bootstrap-secret", "Origin": "http://localhost:5173"}
TABLES = [AuthState.__table__, AuthUser.__table__, AuthSession.__table__,
          AuthInvite.__table__, AuthLoginBucket.__table__]


def make_app(factory):
    app = FastAPI()
    app.include_router(auth.router, prefix="/api")

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db

    @app.get("/review")
    def review(user=Depends(auth.reviewer)):
        return {"id": user.id}

    @app.post("/mutation", dependencies=[Depends(auth.require_same_origin)])
    def mutation():
        return {"ok": True}

    return app


@pytest.fixture
def environment():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=TABLES)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        db.add(AuthState(id=1, setup_complete=False, generation=0))
        db.commit()
    settings = SimpleNamespace(frontend_url="http://localhost:5173",
                               bootstrap_token="test-bootstrap-secret", cookie_secure=False,
                               session_ttl_seconds=3600, invite_ttl_seconds=3600)
    with patch.object(auth, "settings", settings):
        with TestClient(make_app(factory)) as client:
            yield client, factory, settings
    engine.dispose()


def bootstrap(client):
    response = client.post("/api/auth/bootstrap", json=ADMIN, headers=BOOTSTRAP)
    assert response.status_code == 201, response.text
    return response


def csrf(client, **extra):
    return {"X-CSRF-Token": client.cookies.get(auth.CSRF_COOKIE), **extra}


def invite(client, email="member@example.com", role="member"):
    result = client.post("/api/auth/invites", json={"email": email, "role": role}, headers=csrf(client))
    assert result.status_code == 201, result.text
    return result.json()


def accept(client, invitation):
    return client.post("/api/auth/accept-invite", json={
        "email": invitation["email"], "token": invitation["token"],
        "name": "Named teammate", "password": "another strong password",
    })


def test_bootstrap_is_operator_authorized_and_one_time(environment):
    client, factory, settings = environment
    assert client.get("/api/auth/status").json() == {"setup_required": True}
    settings.bootstrap_token = None
    assert client.post("/api/auth/bootstrap", json=ADMIN, headers=BOOTSTRAP).status_code == 503
    settings.bootstrap_token = "test-bootstrap-secret"
    assert client.post("/api/auth/bootstrap", json=ADMIN).status_code == 403
    assert client.post("/api/auth/bootstrap", json=ADMIN,
                       headers={**BOOTSTRAP, "X-Bootstrap-Token": "wrong"}).status_code == 403
    response = bootstrap(client)
    assert response.json()["user"]["role"] == "admin"
    assert client.get("/api/auth/status").json() == {"setup_required": False}
    assert client.post("/api/auth/bootstrap", json=ADMIN, headers=BOOTSTRAP).status_code == 409
    with factory() as db:
        assert len(list(db.scalars(select(AuthUser)))) == 1
        assert db.get(AuthState, 1).setup_complete


def test_passwords_sessions_and_cookie_flags(environment):
    client, factory, settings = environment
    response = bootstrap(client)
    cookie_headers = response.headers.get_list("set-cookie")
    assert any("proploop_session=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
               for cookie in cookie_headers)
    assert any("proploop_csrf=" in cookie and "HttpOnly" not in cookie for cookie in cookie_headers)
    assert all("Secure" not in cookie for cookie in cookie_headers)
    raw_session = client.cookies.get(auth.SESSION_COOKIE)
    with factory() as db:
        user = db.scalar(select(AuthUser))
        session = db.scalar(select(AuthSession))
        assert user.password_hash.startswith("scrypt$16384$8$1$")
        assert ADMIN["password"] not in user.password_hash
        assert session.token_hash == auth.token_hash(raw_session)
        assert session.token_hash != raw_session
    assert client.get("/api/auth/me").json() == response.json()
    assert "password" not in response.text
    assert response.headers["cache-control"] == "no-store"
    settings.cookie_secure = True
    login = client.post("/api/auth/login", json={"email": ADMIN["email"], "password": ADMIN["password"]})
    assert login.status_code == 200
    assert all("Secure" in cookie for cookie in login.headers.get_list("set-cookie"))


def test_login_generic_errors_rate_limit_and_expiry(environment):
    client, factory, _ = environment
    bootstrap(client)
    for email in ("admin@example.com", "missing@example.com"):
        result = client.post("/api/auth/login", json={"email": email, "password": "incorrect"})
        assert result.status_code == 401
        assert result.json() == {"detail": "Invalid email or password"}
    for _ in range(9):
        assert client.post("/api/auth/login", json={"email": "missing@example.com", "password": "wrong"}).status_code == 401
    limited = client.post("/api/auth/login", json={"email": "missing@example.com", "password": "wrong"})
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "900"
    with factory() as db:
        for bucket in db.scalars(select(AuthLoginBucket)):
            bucket.expires_at = auth.now() - timedelta(seconds=1)
        db.commit()
    assert client.post("/api/auth/login", json={
        "email": "ADMIN@example.com", "password": ADMIN["password"],
    }).status_code == 200
    with factory() as db:
        session = db.scalar(select(AuthSession))
        session.expires_at = auth.now() - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/auth/me").status_code == 401


def test_peer_and_global_login_limits_bound_rotating_emails(environment):
    client, factory, _ = environment
    with factory() as db:
        db.add(AuthLoginBucket(key=auth.token_hash("peer:testclient"), attempts=30,
                               expires_at=auth.now() + timedelta(minutes=15)))
        db.commit()
    assert client.post("/api/auth/login", json={"email": "new@example.com", "password": "wrong"}).status_code == 429
    with factory() as db:
        db.delete(db.get(AuthLoginBucket, auth.token_hash("peer:testclient")))
        db.add(AuthLoginBucket(key=auth.token_hash("global"), attempts=100,
                               expires_at=auth.now() + timedelta(minutes=15)))
        db.commit()
    assert client.post("/api/auth/login", json={"email": "different@example.com", "password": "wrong"}).status_code == 429


def test_csrf_rejects_cross_site_and_requires_cookie_header_pair(environment):
    client, _, _ = environment
    assert client.post("/api/auth/login", json={"email": ADMIN["email"], "password": ADMIN["password"]},
                       headers={"Origin": "https://attacker.example"}).status_code == 403
    assert client.post("/api/auth/bootstrap", json=ADMIN,
                       headers={**BOOTSTRAP, "Origin": "null"}).status_code == 403
    bootstrap(client)
    assert client.post("/mutation").status_code == 403
    assert client.post("/mutation", headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert client.post("/mutation", headers=csrf(client, Origin="https://attacker.example")).status_code == 403
    assert client.post("/mutation", headers=csrf(client, Origin="http://localhost:5173")).status_code == 200
    assert client.post("/mutation", headers=csrf(client, Origin="https://testserver")).status_code == 200
    assert client.post("/mutation", headers=csrf(client)).status_code == 200  # CLI double submit
    assert client.post("/mutation", headers=csrf(client, **{"Sec-Fetch-Site": "cross-site"})).status_code == 403
    client.cookies.delete(auth.CSRF_COOKIE)
    assert client.post("/mutation", headers={"X-CSRF-Token": client.get("/api/auth/me").json()["csrf_token"]}).status_code == 403


def test_logout_revokes_server_session(environment):
    client, factory, _ = environment
    bootstrap(client)
    raw = client.cookies.get(auth.SESSION_COOKIE)
    assert client.post("/api/auth/logout").status_code == 403
    result = client.post("/api/auth/logout", headers=csrf(client))
    assert result.status_code == 204
    assert auth.SESSION_COOKIE not in client.cookies
    assert auth.CSRF_COOKIE not in client.cookies
    client.cookies.set(auth.SESSION_COOKIE, raw)
    assert client.get("/api/auth/me").status_code == 401
    with factory() as db:
        assert db.get(AuthSession, auth.token_hash(raw)) is None


@pytest.mark.parametrize("role", ["member", "reviewer", "admin"])
def test_invite_is_email_bound_one_time_and_role_is_enforced(environment, role):
    client, factory, _ = environment
    bootstrap(client)
    invitation = invite(client, role=role)
    listed = client.get("/api/auth/invites").json()
    assert "token" not in listed[0] and "token_hash" not in listed[0]
    with factory() as db:
        stored = db.get(AuthInvite, invitation["id"])
        assert stored.token_hash == auth.token_hash(invitation["token"])
    mismatch = client.post("/api/auth/accept-invite", json={
        "email": "different@example.com", "token": invitation["token"],
        "name": "Someone", "password": "another strong password",
    })
    assert mismatch.status_code == 400
    accepted = accept(client, invitation)
    assert accepted.status_code == 201
    assert accepted.json()["user"]["role"] == role
    assert accept(client, invitation).status_code == 400
    assert client.get("/review").status_code == (403 if role == "member" else 200)
    assert client.get("/api/auth/users").status_code == (200 if role == "admin" else 403)
    assert client.post("/api/auth/invites", json={"email": "new@example.com"},
                       headers=csrf(client)).status_code == (201 if role == "admin" else 403)


def test_invite_expiry_reissue_and_duplicate_account(environment):
    client, factory, _ = environment
    bootstrap(client)
    first = invite(client)
    second = invite(client)
    assert accept(client, first).status_code == 400
    with factory() as db:
        db.get(AuthInvite, second["id"]).expires_at = auth.now() - timedelta(seconds=1)
        db.commit()
    assert accept(client, second).status_code == 400
    third = invite(client)
    assert accept(client, third).status_code == 201
    assert client.post("/api/auth/login", json={"email": ADMIN["email"], "password": ADMIN["password"]}).status_code == 200
    assert client.post("/api/auth/invites", json={"email": third["email"]}, headers=csrf(client)).status_code == 409


def test_final_admin_guard_and_deactivation_revocation(environment):
    client, factory, _ = environment
    first = bootstrap(client).json()["user"]
    for payload in ({"active": False}, {"role": "member"}, {"role": "reviewer", "active": False}):
        assert client.patch(f"/api/auth/users/{first['id']}", json=payload, headers=csrf(client)).status_code == 409
    second = accept(client, invite(client, email="second@example.com", role="admin")).json()["user"]
    assert client.patch(f"/api/auth/users/{first['id']}", json={"active": False}, headers=csrf(client)).status_code == 200
    assert client.patch(f"/api/auth/users/{second['id']}", json={"role": "member"}, headers=csrf(client)).status_code == 409
    assert client.post("/api/auth/login", json={"email": ADMIN["email"], "password": ADMIN["password"]}).status_code == 401
    with factory() as db:
        assert list(db.scalars(select(AuthSession).where(AuthSession.user_id == first["id"]))) == []
    assert client.patch(f"/api/auth/users/{second['id']}", json={"active": True}, headers=csrf(client)).status_code == 200
    assert client.patch("/api/auth/users/999", json={"active": False}, headers=csrf(client)).status_code == 404


def test_role_change_revokes_existing_sessions(environment):
    client, _, _ = environment
    bootstrap(client)
    invitation = invite(client, role="reviewer")
    with TestClient(client.app) as teammate:
        accepted = accept(teammate, invitation)
        target = accepted.json()["user"]["id"]
        assert teammate.get("/review").status_code == 200
        assert client.patch(f"/api/auth/users/{target}", json={"role": "member"},
                            headers=csrf(client)).status_code == 200
        assert teammate.get("/api/auth/me").status_code == 401
        assert teammate.post("/api/auth/login", json={
            "email": invitation["email"], "password": "another strong password",
        }).status_code == 200
        assert teammate.get("/review").status_code == 403


@pytest.mark.parametrize("payload", [
    {**ADMIN, "email": "not an email"},
    {**ADMIN, "email": "a..b@example.com"},
    {**ADMIN, "email": "a@example..com"},
    {**ADMIN, "email": "a@example.com\n"},
    {**ADMIN, "name": "   "},
    {**ADMIN, "name": 123},
    {**ADMIN, "password": "short"},
    {**ADMIN, "password": 123456789012},
    {**ADMIN, "role": "admin"},
])
def test_strict_account_validation(environment, payload):
    client, _, _ = environment
    assert client.post("/api/auth/bootstrap", json=payload, headers=BOOTSTRAP).status_code == 422


def test_strict_patch_and_no_public_user_enumeration(environment):
    client, _, _ = environment
    assert client.get("/api/auth/users").status_code == 401
    assert client.get("/api/auth/invites").status_code == 401
    user = bootstrap(client).json()["user"]
    for payload in ({"active": "false"}, {"active": None}, {"role": None}, {"role": "owner"}, {"name": "rename"}):
        assert client.patch(f"/api/auth/users/{user['id']}", json=payload, headers=csrf(client)).status_code == 422


def test_missing_singleton_fails_closed(environment):
    client, factory, _ = environment
    with factory() as db:
        db.delete(db.get(AuthState, 1))
        db.commit()
    assert client.post("/api/auth/bootstrap", json=ADMIN, headers=BOOTSTRAP).status_code == 503
    assert client.post("/api/auth/login", json={"email": ADMIN["email"], "password": ADMIN["password"]}).status_code == 503


def test_concurrent_bootstrap_allows_exactly_one_admin():
    # File SQLite is needed for independent concurrent connections, not StaticPool.
    path = Path(__file__).parent / ".auth-concurrency.sqlite"
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False, "timeout": 20})
    try:
        Base.metadata.create_all(engine, tables=TABLES)
        factory = sessionmaker(engine, expire_on_commit=False)
        with factory() as db:
            db.add(AuthState(id=1, setup_complete=False, generation=0))
            db.commit()
        app = make_app(factory)
        settings = SimpleNamespace(frontend_url="http://localhost:5173", bootstrap_token="test-bootstrap-secret")

        def attempt(number):
            with TestClient(app) as client:
                return client.post("/api/auth/bootstrap", headers=BOOTSTRAP,
                                   json={**ADMIN, "email": f"admin{number}@example.com"}).status_code

        with patch.object(auth, "settings", settings), ThreadPoolExecutor(max_workers=2) as executor:
            assert sorted(executor.map(attempt, (1, 2))) == [201, 409]
        with factory() as db:
            assert len(list(db.scalars(select(AuthUser)))) == 1
    finally:
        engine.dispose()
        path.unlink(missing_ok=True)


def test_auth_migration_seeds_singleton_and_roundtrips():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "0004_team_auth.py"
    spec = importlib.util.spec_from_file_location("team_auth_revision", path)
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)
    assert revision.down_revision == "0003_controlled_tests"
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        with patch.object(revision, "op", operations):
            revision.upgrade()
            assert set(inspect(connection).get_table_names()) == {table.name for table in TABLES}
            assert connection.execute(select(AuthState.__table__)).one() == (1, False, 0)
            revision.downgrade()
            assert inspect(connection).get_table_names() == []
    engine.dispose()
