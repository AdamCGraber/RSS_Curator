from alembic import op
import sqlalchemy as sa

revision = "0002_cluster_prefs"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.Integer, primary_key=True),
        sa.Column("cluster_similarity_threshold", sa.Float, nullable=False, server_default="0.88"),
        sa.Column("cluster_time_window_days", sa.Integer, nullable=False, server_default="2"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.add_column("clusters", sa.Column("canonical_article_id", sa.Integer, sa.ForeignKey("articles.id"), nullable=True))
    op.add_column("clusters", sa.Column("created_with_threshold", sa.Float, nullable=False, server_default="0.88"))
    op.add_column("clusters", sa.Column("created_with_time_window_days", sa.Integer, nullable=False, server_default="2"))


def downgrade():
    op.drop_column("clusters", "created_with_time_window_days")
    op.drop_column("clusters", "created_with_threshold")
    op.drop_column("clusters", "canonical_article_id")
    op.drop_table("user_preferences")
