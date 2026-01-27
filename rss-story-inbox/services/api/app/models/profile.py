from sqlalchemy import Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    audience_text: Mapped[str] = mapped_column(Text)
    tone_text: Mapped[str] = mapped_column(Text)
    include_terms: Mapped[str] = mapped_column(Text, default="")
    exclude_terms: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
