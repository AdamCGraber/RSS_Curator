import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.source import Source
from app.models.sources_state import SourcesCache, SourcesVersion

logger = logging.getLogger("uvicorn.error")

CACHE_TTL = timedelta(minutes=20)


def _ensure_sources_version(db: Session) -> SourcesVersion:
    row = db.get(SourcesVersion, 1)
    if row is None:
        row = SourcesVersion(id=1, version=0)
        db.add(row)
        db.flush()
    return row


def get_sources_version(db: Session) -> int:
    return _ensure_sources_version(db).version


def bump_sources_version(db: Session) -> int:
    row = _ensure_sources_version(db)
    row.version += 1
    row.updated_at = datetime.now(timezone.utc)
    db.flush()
    return row.version


def refresh_sources_cache(db: Session, version: int) -> dict:
    now = datetime.now(timezone.utc)
    sources = (
        db.query(Source)
        .filter(Source.active == True)
        .order_by(Source.id.asc())
        .all()
    )
    payload = {
        "version": version,
        "generated_at": now.isoformat(),
        "sources": [
            {
                "id": s.id,
                "name": s.name,
                "feed_url": s.feed_url,
                "active": s.active,
            }
            for s in sources
        ],
    }

    cache = db.get(SourcesCache, 1)
    if cache is None:
        cache = SourcesCache(id=1, version=version, generated_at=now, payload=payload)
        db.add(cache)
    else:
        cache.version = version
        cache.generated_at = now
        cache.payload = payload

    db.flush()
    return payload


def get_active_sources_snapshot(db: Session) -> dict:
    version = get_sources_version(db)
    cache = db.get(SourcesCache, 1)
    now = datetime.now(timezone.utc)
    if cache and cache.version == version and cache.generated_at and cache.generated_at >= now - CACHE_TTL:
        return cache.payload
    return refresh_sources_cache(db, version)


def publish_sources_changed(db: Session, version: int) -> None:
    payload = json.dumps({"version": version})
    try:
        db.execute(text("NOTIFY sources_changed, :payload"), {"payload": payload})
        db.commit()
    except Exception:
        logger.exception("Failed to publish sources.changed event for version %s", version)
