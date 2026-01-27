from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.summary import Summary
from app.schemas.summary import SummaryOut, SummaryUpdate

router = APIRouter(prefix="/summaries", tags=["summaries"])

@router.get("/cluster/{cluster_id}", response_model=SummaryOut | None)
def get_cluster_summary(cluster_id: int, db: Session = Depends(get_db)):
    s = db.query(Summary).filter(Summary.cluster_id == cluster_id).first()
    return s

@router.put("/{summary_id}", response_model=SummaryOut)
def update_summary(summary_id: int, payload: SummaryUpdate, db: Session = Depends(get_db)):
    s = db.query(Summary).get(summary_id)
    if not s:
        raise HTTPException(404, "Summary not found")
    s.edited_text = payload.edited_text
    db.commit()
    db.refresh(s)
    return s
