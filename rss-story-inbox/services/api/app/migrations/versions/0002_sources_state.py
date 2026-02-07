from alembic import op
import sqlalchemy as sa

revision = "0002_sources_state"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sources_version",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "sources_cache",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
    )


def downgrade():
    op.drop_table("sources_cache")
    op.drop_table("sources_version")
