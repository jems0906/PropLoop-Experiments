from alembic import op
import sqlalchemy as sa

revision = "0003_controlled_tests"
down_revision = "0002_metric_direction"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("metrics", sa.Column("comparison_mode", sa.String(length=20), nullable=False, server_default="before_after"))
    op.add_column("metrics", sa.Column("control_sample_size", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("metrics", sa.Column("treatment_sample_size", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "variant_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("experiment_id", sa.Integer(), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_key", sa.String(length=128), nullable=False),
        sa.Column("variant", sa.String(length=12), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("experiment_id", "subject_key", name="uq_assignment_experiment_subject"),
    )


def downgrade():
    op.drop_table("variant_assignments")
    op.drop_column("metrics", "treatment_sample_size")
    op.drop_column("metrics", "control_sample_size")
    op.drop_column("metrics", "comparison_mode")
