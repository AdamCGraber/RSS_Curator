from typing import List, Tuple
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.source import Source

router = APIRouter(prefix="/admin", tags=["admin"])


def _extract_feed_urls_from_opml(opml_bytes: bytes) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    feed_urls: List[str] = []

    try:
        root = ET.fromstring(opml_bytes)
    except Exception as e:
        return [], [f"Failed to parse OPML XML: {e}"]

    for outline in root.findall(".//outline"):
        xml_url = outline.attrib.get("xmlUrl") or outline.attrib.get("xmlurl")
        if not xml_url:
            continue
        xml_url = xml_url.strip()
        if xml_url:
            feed_urls.append(xml_url)

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for u in feed_urls:
        if u in seen:
            continue
        seen.add(u)
        deduped.append(u)

    return deduped, errors


@router.post("/sources/import-opml")
def import_opml(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Sync route + sync DB: FastAPI will run this in a threadpool.
    Reads OPML bytes, extracts xmlUrl entries, inserts missing sources.
    """
    content = file.file.read()

    feed_urls, errors = _extract_feed_urls_from_opml(content)

    added = 0
    skipped = 0

    existing = {
        r[0]
        for r in db.query(Source.feed_url)
        .filter(Source.feed_url.in_(feed_urls))
        .all()
    }

    for feed_url in feed_urls:
        if feed_url in existing:
            skipped += 1
            continue
        db.add(Source(name="Imported Feed", feed_url=feed_url, active=True))
        added += 1

    db.commit()

    return {
        "ok": True,
        "total_found": len(feed_urls),
        "added": added,
        "skipped": skipped,
        "errors": errors,
    }
