from alembic import op
import sqlalchemy as sa

revision = "0006_coding_agent"
down_revision = "0005_lifecycle_outcomes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("experiment_id", sa.Integer(), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("auth_users.id"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("repository", sa.String(length=300), nullable=False),
        sa.Column("branch", sa.String(length=300), nullable=True),
        sa.Column("pull_request_url", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("error", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('running', 'pull_request', 'failed')", name="ck_agent_runs_status"),
    )
    op.create_index("ix_agent_runs_experiment_id", "agent_runs", ["experiment_id"])


def downgrade():
    op.drop_index("ix_agent_runs_experiment_id", table_name="agent_runs")
    op.drop_table("agent_runs")
