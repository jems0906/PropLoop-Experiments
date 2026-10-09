from alembic import op
import sqlalchemy as sa

revision = "0002_metric_direction"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("metrics", sa.Column("direction", sa.String(length=12), nullable=False, server_default="higher"))


def downgrade():
    op.drop_column("metrics", "direction")
