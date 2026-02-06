from sqlalchemy import String, DateTime, func, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Cluster(Base):
    __tablename__ = "clusters"

    id: Mapped[int] = mapped_column(primary_key=True)
    cluster_title: Mapped[str] = mapped_column(String(512))
    canonical_article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), nullable=True)
    created_with_threshold: Mapped[float] = mapped_column(Float, default=0.88)
    created_with_time_window_days: Mapped[int] = mapped_column(Integer, default=2)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    coverage_count: Mapped[int] = mapped_column(Integer, default=1)
    latest_published_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
