from alembic import op
import sqlalchemy as sa

revision = "0004_team_auth"
down_revision = "0003_controlled_tests"
branch_labels = None
depends_on = None


def upgrade():
    state = op.create_table(
        "auth_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("setup_complete", sa.Boolean(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_auth_state_singleton"),
    )
    op.bulk_insert(state, [{"id": 1, "setup_complete": False, "generation": 0}])
    op.create_table(
        "auth_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'reviewer', 'member')", name="ck_auth_users_role"),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_table(
        "auth_invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("auth_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('admin', 'reviewer', 'member')", name="ck_auth_invites_role"),
    )
    op.create_table(
        "auth_login_buckets",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auth_login_buckets_expires_at", "auth_login_buckets", ["expires_at"])


def downgrade():
    op.drop_index("ix_auth_login_buckets_expires_at", table_name="auth_login_buckets")
    op.drop_table("auth_login_buckets")
    op.drop_table("auth_invites")
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("auth_users")
    op.drop_table("auth_state")
