from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class ClusterArticle(BaseModel):
    id: int
    title: str
    url: str
    source_name: str
    published_at: Optional[datetime] = None

class ClusterOut(BaseModel):
    id: int
    cluster_title: str
    coverage_count: int
    latest_published_at: Optional[datetime] = None
    score: float
    why: str
    canonical: Optional[ClusterArticle] = None
    coverage: List[ClusterArticle] = []
