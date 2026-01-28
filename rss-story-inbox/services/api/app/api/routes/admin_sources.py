from fastapi import APIRouter, Depends
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.source import Source
from app.schemas.source_admin import BulkDeleteSources

router = APIRouter(prefix="/admin/sources", tags=["admin"])


@router.post("/delete-bulk")
def delete_sources_bulk(payload: BulkDeleteSources, db: Session = Depends(get_db)):
    ids = list({int(x) for x in payload.source_ids})
    if not ids:
        return {"ok": True, "deleted": 0}

    result = db.execute(delete(Source).where(Source.id.in_(ids)))
    db.commit()
    return {"ok": True, "deleted": result.rowcount or 0}


@router.post("/delete-all")
def delete_sources_all(db: Session = Depends(get_db)):
    result = db.execute(delete(Source))
    db.commit()
    return {"ok": True, "deleted": result.rowcount or 0}
