"""Add explicit story time window start/end columns."""

from alembic import op
import sqlalchemy as sa

revision = "0007_explicit_time_window_dates"
down_revision = "0006_qualifying_terms_snapshot"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user_preferences", sa.Column("cluster_time_window_start", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user_preferences", sa.Column("cluster_time_window_end", sa.DateTime(timezone=True), nullable=True))

    op.add_column("clusters", sa.Column("created_with_time_window_start", sa.DateTime(timezone=True), nullable=True))
    op.add_column("clusters", sa.Column("created_with_time_window_end", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("clusters", "created_with_time_window_end")
    op.drop_column("clusters", "created_with_time_window_start")

    op.drop_column("user_preferences", "cluster_time_window_end")
    op.drop_column("user_preferences", "cluster_time_window_start")
