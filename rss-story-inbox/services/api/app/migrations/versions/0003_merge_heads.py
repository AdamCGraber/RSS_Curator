"""
Merge multiple heads into a single linear history.
"""

revision = "0003_merge_heads"
down_revision = ("0002_cluster_prefs", "0002_sources_state")
branch_labels = None
depends_on = None


def upgrade():
    # No-op merge migration: both branches are already applied by this point.
    pass


def downgrade():
    # No-op (you could implement explicit downgrades if you ever need them)
    pass