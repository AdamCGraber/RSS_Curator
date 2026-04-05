"""Add explicit date-range fields for ingestion time windows."""

from alembic import op
import sqlalchemy as sa

revision = "0006_time_window_date_range"
down_revision = "0005_profile_include_terms_2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user_preferences", sa.Column("cluster_time_window_start", sa.Date(), nullable=True))
    op.add_column("user_preferences", sa.Column("cluster_time_window_end", sa.Date(), nullable=True))

    op.add_column("clusters", sa.Column("created_with_time_window_start", sa.DateTime(timezone=True), nullable=True))
    op.add_column("clusters", sa.Column("created_with_time_window_end", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("clusters", "created_with_time_window_end")
    op.drop_column("clusters", "created_with_time_window_start")
    op.drop_column("user_preferences", "cluster_time_window_end")
    op.drop_column("user_preferences", "cluster_time_window_start")
