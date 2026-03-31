"""Add queue-time qualifying terms snapshot to clusters."""

from alembic import op
import sqlalchemy as sa

revision = "0006_cluster_qualifying_terms_snapshot"
down_revision = "0005_profile_include_terms_2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("clusters", sa.Column("qualifying_terms_snapshot", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("clusters", "qualifying_terms_snapshot")
