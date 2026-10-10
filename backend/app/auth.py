import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, field_validator
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.auth_models import AuthInvite, AuthLoginBucket, AuthSession, AuthState, AuthUser

router = APIRouter(prefix="/auth", tags=["auth"])
SESSION_COOKIE = "proploop_session"
CSRF_COOKIE = "proploop_csrf"
Role = Literal["admin", "reviewer", "member"]
_EMAIL = re.compile(
    r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
    r"@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+"
)
_DUMMY_SALT = b"proploop-login-dummy-salt"
_DUMMY_HASH = hashlib.scrypt(b"not-a-real-password", salt=_DUMMY_SALT, n=16384, r=8, p=1).hex()


def now() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str | None) -> bool:
    if encoded is None:
        digest = hashlib.scrypt(password.encode(), salt=_DUMMY_SALT, n=16384, r=8, p=1)
        hmac.compare_digest(digest.hex(), _DUMMY_HASH)
        return False
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$")
        if (algorithm, n, r, p) != ("scrypt", "16384", "8", "1"):
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmailInput(Input):
    email: StrictStr = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def email_address(cls, value: str) -> str:
        if not _EMAIL.fullmatch(value) or len(value.split("@")[0]) > 64:
            raise ValueError("A valid email address is required")
        return value.lower()


class LoginInput(EmailInput):
    password: StrictStr = Field(min_length=1, max_length=128)


class AccountInput(EmailInput):
    name: StrictStr = Field(min_length=1, max_length=120)
    password: StrictStr = Field(min_length=12, max_length=128)

    @field_validator("name")
    @classmethod
    def named_account(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError("A nonempty account name is required")
        return value


class AcceptInviteInput(AccountInput):
    token: StrictStr = Field(min_length=20, max_length=128)


class InviteInput(EmailInput):
    role: Role = "member"


class UserPatch(Input):
    role: Role | None = None
    active: StrictBool | None = None

    @field_validator("role", "active")
    @classmethod
    def not_null(cls, value):
        if value is None:
            raise ValueError("Explicit null is not allowed")
        return value


def user_info(user: AuthUser) -> dict:
    return {
        "id": user.id, "email": user.email, "name": user.name,
        "role": user.role, "active": user.active, "created_at": aware(user.created_at),
    }


def invite_info(invite: AuthInvite) -> dict:
    return {
        "id": invite.id, "email": invite.email, "role": invite.role,
        "created_by": invite.created_by, "created_at": invite.created_at,
        "expires_at": invite.expires_at, "accepted_at": invite.accepted_at,
    }


def check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        if request.headers.get("sec-fetch-site") == "cross-site":
            raise HTTPException(403, "Cross-site request rejected")
        return
    try:
        parsed = urlsplit(origin)
        configured = urlsplit(settings.frontend_url)
        if (
            parsed.scheme not in ("http", "https") or not parsed.netloc
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment
        ):
            raise ValueError("Invalid origin")
        configured_match = (
            parsed.scheme.lower() == configured.scheme.lower()
            and parsed.netloc.lower() == configured.netloc.lower()
        )
        # The externally visible Host survives trusted reverse-proxy routing.
        same_host = parsed.netloc.lower() == request.url.netloc.lower()
        if not (configured_match or same_host):
            raise ValueError("Cross-site origin")
    except ValueError:
        raise HTTPException(403, "Cross-site request rejected") from None


def session_for(request: Request, db: Session) -> AuthSession:
    token = request.cookies.get(SESSION_COOKIE, "")
    session = db.get(AuthSession, token_hash(token)) if 20 <= len(token) <= 128 else None
    if session is None or aware(session.expires_at) <= now():
        raise HTTPException(401, "Authentication required")
    return session


def current_user(request: Request, db: Session = Depends(get_db)) -> AuthUser:
    session = session_for(request, db)
    user = db.get(AuthUser, session.user_id)
    if user is None or not user.active:
        raise HTTPException(401, "Authentication required")
    request.state.auth_session = session
    return user


def require_same_origin(request: Request, user: AuthUser = Depends(current_user)) -> None:
    check_origin(request)
    session = request.state.auth_session
    header = request.headers.get("x-csrf-token", "")
    cookie = request.cookies.get(CSRF_COOKIE, "")
    if not (
        header and cookie
        and hmac.compare_digest(header.encode(), session.csrf_token.encode())
        and hmac.compare_digest(cookie.encode(), session.csrf_token.encode())
    ):
        raise HTTPException(403, "CSRF token required")


def reviewer(user: AuthUser = Depends(current_user)) -> AuthUser:
    if user.role not in ("admin", "reviewer"):
        raise HTTPException(403, "Reviewer access required")
    return user


def admin(user: AuthUser = Depends(current_user)) -> AuthUser:
    if user.role != "admin":
        raise HTTPException(403, "Administrator access required")
    return user


def lock_state(db: Session) -> AuthState:
    result = db.execute(update(AuthState).where(AuthState.id == 1).values(generation=AuthState.generation + 1))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(503, "Authentication storage requires migration")
    return db.get(AuthState, 1, populate_existing=True)


def locked_admin(db: Session, user: AuthUser) -> None:
    lock_state(db)
    fresh = db.get(AuthUser, user.id, populate_existing=True)
    if fresh is None or not fresh.active or fresh.role != "admin":
        raise HTTPException(403, "Administrator access required")


def issue_session(db: Session, response: Response, user: AuthUser, request: Request) -> dict:
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    ttl = max(60, min(int(getattr(settings, "session_ttl_seconds", 43200)), 2592000))
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= now()))
    old_token = request.cookies.get(SESSION_COOKIE)
    if old_token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash(old_token)))
    db.add(AuthSession(
        token_hash=token_hash(token), user_id=user.id,
        csrf_token=csrf, expires_at=now() + timedelta(seconds=ttl),
    ))
    db.commit()
    for key, value, http_only in ((SESSION_COOKIE, token, True), (CSRF_COOKIE, csrf, False)):
        response.set_cookie(
            key, value, max_age=ttl, path="/", httponly=http_only,
            secure=bool(getattr(settings, "cookie_secure", False)), samesite="lax",
        )
    response.headers["Cache-Control"] = "no-store"
    return {"user": user_info(user), "csrf_token": csrf}


def record_login_attempt(db: Session, request: Request, email: str) -> None:
    # A global cap also bounds rotating identities/IPs and password-hashing work.
    lock_state(db)
    timestamp = now()
    db.execute(delete(AuthLoginBucket).where(AuthLoginBucket.expires_at <= timestamp))
    peer = request.client.host if request.client else "unknown"
    keys = ((token_hash("global"), 100), (token_hash(f"peer:{peer}"), 30),
            (token_hash(f"email:{email}"), 10))
    buckets = []
    for key, limit in keys:
        bucket = db.get(AuthLoginBucket, key)
        if bucket is None:
            bucket = AuthLoginBucket(key=key, attempts=0, expires_at=timestamp + timedelta(minutes=15))
            db.add(bucket)
        if bucket.attempts >= limit:
            db.rollback()
            raise HTTPException(429, "Too many login attempts; try again later", headers={"Retry-After": "900"})
        buckets.append(bucket)
    for bucket in buckets:
        bucket.attempts += 1
    db.commit()


@router.get("/status")
def status(response: Response, db: Session = Depends(get_db)) -> dict:
    state = db.get(AuthState, 1)
    response.headers["Cache-Control"] = "no-store"
    return {"setup_required": state is None or not state.setup_complete}


@router.post("/bootstrap", status_code=201)
def bootstrap(body: AccountInput, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    check_origin(request)
    expected = getattr(settings, "bootstrap_token", None)
    if not expected:
        raise HTTPException(503, "Bootstrap is disabled")
    supplied = request.headers.get("x-bootstrap-token", "")
    if not hmac.compare_digest(supplied.encode(), str(expected).encode()):
        raise HTTPException(403, "Bootstrap authorization required")
    state = lock_state(db)
    if state.setup_complete or db.scalar(select(func.count()).select_from(AuthUser)):
        raise HTTPException(409, "Setup is already complete")
    user = AuthUser(email=body.email, name=body.name, password_hash=hash_password(body.password), role="admin")
    db.add(user)
    state.setup_complete = True
    db.flush()
    return issue_session(db, response, user, request)


@router.post("/login")
def login(body: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    check_origin(request)
    record_login_attempt(db, request, body.email)
    user = db.scalar(select(AuthUser).where(AuthUser.email == body.email))
    valid = verify_password(body.password, user.password_hash if user else None)
    if not valid or user is None or not user.active:
        raise HTTPException(401, "Invalid email or password")
    return issue_session(db, response, user, request)


@router.post("/logout", status_code=204, dependencies=[Depends(require_same_origin)])
def logout(request: Request, response: Response, user: AuthUser = Depends(current_user),
           db: Session = Depends(get_db)) -> None:
    db.execute(delete(AuthSession).where(AuthSession.token_hash == request.state.auth_session.token_hash))
    db.commit()
    for cookie in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(cookie, path="/", secure=bool(getattr(settings, "cookie_secure", False)),
                               httponly=cookie == SESSION_COOKIE, samesite="lax")
    response.headers["Cache-Control"] = "no-store"


@router.get("/me")
def me(request: Request, response: Response, user: AuthUser = Depends(current_user)) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return {"user": user_info(user), "csrf_token": request.state.auth_session.csrf_token}


@router.post("/invites", status_code=201, dependencies=[Depends(require_same_origin)])
def create_invite(body: InviteInput, request: Request, response: Response,
                  user: AuthUser = Depends(admin), db: Session = Depends(get_db)) -> dict:
    locked_admin(db, user)
    if db.scalar(select(AuthUser.id).where(AuthUser.email == body.email)) is not None:
        raise HTTPException(409, "An account already exists")
    timestamp = now()
    # Reissuing an invitation revokes any outstanding token for this email.
    db.execute(update(AuthInvite).where(
        AuthInvite.email == body.email, AuthInvite.accepted_at.is_(None),
        AuthInvite.expires_at > timestamp,
    ).values(expires_at=timestamp))
    token = secrets.token_urlsafe(32)
    ttl = max(60, min(int(getattr(settings, "invite_ttl_seconds", 172800)), 2592000))
    invite = AuthInvite(email=body.email, role=body.role, token_hash=token_hash(token),
                        created_by=user.id, expires_at=timestamp + timedelta(seconds=ttl))
    db.add(invite)
    db.commit()
    db.refresh(invite)
    response.headers["Cache-Control"] = "no-store"
    return {**invite_info(invite), "token": token}


@router.get("/invites")
def list_invites(response: Response, user: AuthUser = Depends(admin), db: Session = Depends(get_db),
                 offset: int = 0) -> list[dict]:
    if offset < 0:
        raise HTTPException(422, "Offset must be nonnegative")
    response.headers["Cache-Control"] = "no-store"
    return [invite_info(invite) for invite in db.scalars(
        select(AuthInvite).order_by(AuthInvite.id.desc()).offset(offset).limit(200)
    )]


@router.post("/accept-invite", status_code=201)
def accept_invite(body: AcceptInviteInput, request: Request, response: Response,
                  db: Session = Depends(get_db)) -> dict:
    check_origin(request)
    lock_state(db)
    invite = db.scalar(select(AuthInvite).where(AuthInvite.token_hash == token_hash(body.token)))
    if (invite is None or invite.email != body.email or invite.accepted_at is not None
            or aware(invite.expires_at) <= now()
            or db.scalar(select(AuthUser.id).where(AuthUser.email == body.email)) is not None):
        raise HTTPException(400, "Invalid or expired invitation")
    user = AuthUser(email=body.email, name=body.name, password_hash=hash_password(body.password), role=invite.role)
    invite.accepted_at = now()
    db.add(user)
    db.flush()
    return issue_session(db, response, user, request)


@router.get("/users")
def list_users(response: Response, user: AuthUser = Depends(admin),
               db: Session = Depends(get_db), offset: int = 0) -> list[dict]:
    if offset < 0:
        raise HTTPException(422, "Offset must be nonnegative")
    response.headers["Cache-Control"] = "no-store"
    return [user_info(account) for account in db.scalars(
        select(AuthUser).order_by(AuthUser.id).offset(offset).limit(200)
    )]


@router.patch("/users/{user_id}", dependencies=[Depends(require_same_origin)])
def patch_user(user_id: int, body: UserPatch, response: Response,
               user: AuthUser = Depends(admin), db: Session = Depends(get_db)) -> dict:
    locked_admin(db, user)
    target = db.get(AuthUser, user_id, populate_existing=True)
    if target is None:
        raise HTTPException(404, "Account not found")
    role = body.role if body.role is not None else target.role
    active = body.active if body.active is not None else target.active
    if target.active and target.role == "admin" and (not active or role != "admin"):
        count = db.scalar(select(func.count()).select_from(AuthUser).where(
            AuthUser.active.is_(True), AuthUser.role == "admin",
        ))
        if count <= 1:
            raise HTTPException(409, "The final active administrator cannot be removed")
    if target.role != role or target.active != active:
        db.execute(delete(AuthSession).where(AuthSession.user_id == target.id))
    target.role, target.active = role, active
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return user_info(target)
