from sqlalchemy import String, DateTime, func, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class Article(Base):
    __tablename__ = "articles"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    source = relationship("Source")

    url: Mapped[str] = mapped_column(String(1024), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512), index=True)
    published_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    fetched_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    raw_excerpt: Mapped[str] = mapped_column(Text, nullable=True)
    content_text: Mapped[str] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="INBOX", index=True)
    cluster_id: Mapped[int] = mapped_column(ForeignKey("clusters.id"), nullable=True, index=True)
    cluster = relationship("Cluster")
