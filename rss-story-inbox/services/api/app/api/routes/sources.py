from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.source import Source
from app.schemas.source import SourceCreate, SourceOut

router = APIRouter(prefix="/sources", tags=["sources"])

@router.get("", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db)):
    return db.query(Source).order_by(Source.id.asc()).all()

@router.post("", response_model=SourceOut)
def add_source(payload: SourceCreate, db: Session = Depends(get_db)):
    s = Source(name=payload.name, feed_url=payload.feed_url, active=True)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s
