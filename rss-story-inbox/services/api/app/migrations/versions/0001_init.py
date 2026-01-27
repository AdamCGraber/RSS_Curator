from alembic import op
import sqlalchemy as sa

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("feed_url", sa.String(length=1024), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_sources_feed_url", "sources", ["feed_url"], unique=True)

    op.create_table(
        "clusters",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("cluster_title", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("coverage_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("latest_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Float, nullable=False, server_default="0"),
    )
    op.create_index("ix_clusters_score", "clusters", ["score"])
    op.create_index("ix_clusters_latest", "clusters", ["latest_published_at"])

    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("audience_text", sa.Text, nullable=False),
        sa.Column("tone_text", sa.Text, nullable=False),
        sa.Column("include_terms", sa.Text, nullable=False, server_default=""),
        sa.Column("exclude_terms", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "articles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("raw_excerpt", sa.Text, nullable=True),
        sa.Column("content_text", sa.Text, nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="INBOX"),
        sa.Column("cluster_id", sa.Integer, sa.ForeignKey("clusters.id"), nullable=True),
    )
    op.create_index("ix_articles_url", "articles", ["url"], unique=True)
    op.create_index("ix_articles_status_published", "articles", ["status", "published_at"])
    op.create_index("ix_articles_cluster_id", "articles", ["cluster_id"])

    op.create_table(
        "summaries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("article_id", sa.Integer, sa.ForeignKey("articles.id"), nullable=True),
        sa.Column("cluster_id", sa.Integer, sa.ForeignKey("clusters.id"), nullable=True),
        sa.Column("draft_text", sa.Text, nullable=True),
        sa.Column("edited_text", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_summaries_cluster_id", "summaries", ["cluster_id"])

def downgrade():
    op.drop_table("summaries")
    op.drop_table("articles")
    op.drop_table("profiles")
    op.drop_table("clusters")
    op.drop_table("sources")
