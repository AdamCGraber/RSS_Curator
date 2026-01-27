from sqlalchemy import String, DateTime, func, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class Cluster(Base):
    __tablename__ = "clusters"
    id: Mapped[int] = mapped_column(primary_key=True)
    cluster_title: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    coverage_count: Mapped[int] = mapped_column(Integer, default=1)
    latest_published_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
