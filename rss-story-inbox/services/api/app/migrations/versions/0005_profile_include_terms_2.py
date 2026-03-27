"""Add secondary include terms field to profiles."""

from alembic import op
import sqlalchemy as sa

revision = "0005_profile_include_terms_2"
down_revision = "0004_ingestion_job_progress"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("profiles", sa.Column("include_terms_2", sa.Text(), nullable=False, server_default=""))


def downgrade():
    op.drop_column("profiles", "include_terms_2")
