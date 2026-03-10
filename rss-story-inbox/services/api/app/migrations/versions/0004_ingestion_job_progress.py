"""Add ingestion_job table for persisted progress tracking."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_ingestion_job_progress"
down_revision = "0003_merge_heads"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ingestion_job",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("processed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_percent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ingestion_job_status"), "ingestion_job", ["status"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_ingestion_job_status"), table_name="ingestion_job")
    op.drop_table("ingestion_job")
