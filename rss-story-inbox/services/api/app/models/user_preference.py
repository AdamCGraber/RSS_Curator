from sqlalchemy import Float, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    cluster_similarity_threshold: Mapped[float] = mapped_column(Float, default=0.88)
    cluster_time_window_days: Mapped[int] = mapped_column(Integer, default=2)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
