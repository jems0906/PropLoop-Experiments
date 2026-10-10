from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuthState(Base):
    """A migration-seeded row serializes bootstrap and administrator changes."""

    __tablename__ = "auth_state"
    __table_args__ = (CheckConstraint("id = 1", name="ck_auth_state_singleton"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    setup_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    generation: Mapped[int] = mapped_column(Integer, default=0)


class AuthUser(Base):
    __tablename__ = "auth_users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'reviewer', 'member')", name="ck_auth_users_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("auth_users.id", ondelete="CASCADE"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuthInvite(Base):
    __tablename__ = "auth_invites"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'reviewer', 'member')", name="ck_auth_invites_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(16))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("auth_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuthLoginBucket(Base):
    __tablename__ = "auth_login_buckets"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
