import logging
import uuid

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.article import Article
from app.models.cluster import Cluster
from app.models.source import Source
from app.schemas.source_admin import BulkDeleteSources
from app.services.sources_state import (
    bump_sources_version,
    get_sources_version,
    publish_sources_changed,
    refresh_sources_cache,
)

router = APIRouter(prefix="/admin/sources", tags=["admin"])
logger = logging.getLogger("uvicorn.error")


@router.post("/delete-bulk")
def delete_sources_bulk(
    payload: BulkDeleteSources,
    request: Request,
    db: Session = Depends(get_db),
):
    request_id = uuid.uuid4().hex[:8]
    origin = request.headers.get("origin")
    source_ids_raw = payload.source_ids or []

    ids: list[int] = []
    invalid_ids: list[str] = []
    for raw in source_ids_raw:
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            invalid_ids.append(str(raw))

    if invalid_ids or not ids:
        logger.info(
            "bulk_delete_sources validation error request_id=%s origin=%s invalid_ids=%s",
            request_id,
            origin,
            invalid_ids,
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "VALIDATION_ERROR",
                "message": "source_ids must be a non-empty array of IDs",
                "request_id": request_id,
            },
        )

    unique_ids = sorted(set(ids))
    try:
        with db.begin():
            existing_rows = (
                db.query(Source.id)
                .filter(Source.id.in_(unique_ids))
                .all()
            )
            existing_ids = {row[0] for row in existing_rows}
            not_found_ids = sorted(set(unique_ids) - existing_ids)

            deleted_count = 0
            version = get_sources_version(db)
            if existing_ids:
                db.execute(delete(Article).where(Article.source_id.in_(existing_ids)))
                result = db.execute(delete(Source).where(Source.id.in_(existing_ids)))
                deleted_count = result.rowcount or 0
                if deleted_count:
                    version = bump_sources_version(db)
                    refresh_sources_cache(db, version)

        if deleted_count:
            publish_sources_changed(db, version)

        logger.info(
            "bulk_delete_sources success request_id=%s origin=%s requested=%s deleted=%s not_found=%s version=%s",
            request_id,
            origin,
            len(unique_ids),
            deleted_count,
            len(not_found_ids),
            version,
        )
        return {
            "deleted_count": deleted_count,
            "requested_count": len(unique_ids),
            "not_found_ids": not_found_ids,
            "version": version,
        }
    except Exception:
        logger.exception(
            "bulk_delete_sources error request_id=%s origin=%s source_ids=%s",
            request_id,
            origin,
            unique_ids,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_ERROR",
                "message": "Unhandled server error",
                "request_id": request_id,
            },
        )


@router.post("/delete-all")
def delete_sources_all(db: Session = Depends(get_db)):
    deleted_count = 0
    with db.begin():
        db.execute(update(Article).values(cluster_id=None))
        db.execute(update(Cluster).values(canonical_article_id=None))
        db.execute(delete(Cluster))
        db.execute(delete(Article))
        result = db.execute(delete(Source))
        deleted_count = result.rowcount or 0
        version = get_sources_version(db)
        if deleted_count:
            version = bump_sources_version(db)
            refresh_sources_cache(db, version)

    if deleted_count:
        publish_sources_changed(db, version)

    return {"ok": True, "deleted": deleted_count, "version": version}
