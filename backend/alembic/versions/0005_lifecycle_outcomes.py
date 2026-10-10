from alembic import op
import sqlalchemy as sa

revision = "0005_lifecycle_outcomes"
down_revision = "0004_team_auth"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("experiments", sa.Column("cycle", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("experiments", sa.Column("approvals", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("experiments", sa.Column("history", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("decisions", sa.Column("reviewer_id", sa.Integer(), nullable=True))
    op.add_column("decisions", sa.Column("reviewer_name", sa.String(180), nullable=True))
    op.create_table(
        "observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("experiment_id", sa.Integer(), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_key", sa.String(128), nullable=False),
        sa.Column("exposed", sa.Boolean(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("errored", sa.Boolean(), nullable=False),
        sa.Column("csat", sa.Float(), nullable=True),
        sa.Column("duration_minutes", sa.Float(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("experiment_id", "subject_key", name="uq_observation_subject"),
    )


def downgrade():
    op.drop_table("observations")
    op.drop_column("decisions", "reviewer_name")
    op.drop_column("decisions", "reviewer_id")
    for name in ("history", "approvals", "cycle"):
        op.drop_column("experiments", name)
