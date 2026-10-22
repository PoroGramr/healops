"""Track consecutive failures for bounded automatic restart policy."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # Initial MVP migration used live metadata: a fresh install already has this column.
    if "failure_streak" not in {
        c["name"] for c in sa.inspect(op.get_bind()).get_columns("containers")
    }:
        op.add_column(
            "containers",
            sa.Column("failure_streak", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade():
    op.drop_column("containers", "failure_streak")
