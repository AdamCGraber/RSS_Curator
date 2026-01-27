from pydantic import BaseModel
from typing import Optional

class SummaryOut(BaseModel):
    id: int
    article_id: Optional[int] = None
    cluster_id: Optional[int] = None
    draft_text: Optional[str] = None
    edited_text: Optional[str] = None

    class Config:
        from_attributes = True

class SummaryUpdate(BaseModel):
    edited_text: str
