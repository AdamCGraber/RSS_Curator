from sqlalchemy import Text, DateTime, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class Summary(Base):
    __tablename__ = "summaries"
    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), nullable=True, index=True)
    cluster_id: Mapped[int] = mapped_column(ForeignKey("clusters.id"), nullable=True, index=True)

    draft_text: Mapped[str] = mapped_column(Text, nullable=True)
    edited_text: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    article = relationship("Article")
    cluster = relationship("Cluster")
