from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.profile import Profile
from app.core.config import settings
from app.schemas.profile import ProfileOut, ProfileUpdate

router = APIRouter(prefix="/profile", tags=["profile"])

def ensure_profile(db: Session) -> Profile:
    p = db.query(Profile).order_by(Profile.id.asc()).first()
    if p:
        return p
    p = Profile(
        audience_text=settings.default_audience,
        tone_text=settings.default_tone,
        include_terms=settings.default_include_terms,
        exclude_terms=settings.default_exclude_terms,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p

@router.get("", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db)):
    return ensure_profile(db)

@router.put("", response_model=ProfileOut)
def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db)):
    p = ensure_profile(db)
    p.audience_text = payload.audience_text
    p.tone_text = payload.tone_text
    p.include_terms = payload.include_terms
    p.exclude_terms = payload.exclude_terms
    db.commit()
    db.refresh(p)
    return p
