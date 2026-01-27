from typing import List, Tuple
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.source import Source

router = APIRouter(prefix="/admin", tags=["admin"])


def _extract_feed_urls_from_opml(opml_bytes: bytes) -> Tuple[List[str], List[str]]:
    """
    Returns (feed_urls, errors)
    feed_urls are extracted from outline nodes with xmlUrl attribute.
    """
    errors: List[str] = []
    feed_urls: List[str] = []

    try:
        root = ET.fromstring(opml_bytes)
    except Exception as e:
        return [], [f"Failed to parse OPML XML: {e}"]

    # OPML typically has <opml><body><outline ... /></body></opml>
    # We scan all outline nodes at any depth.
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
async def import_opml(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload an OPML file and bulk-import RSS feeds from outline xmlUrl attributes.
    """
    content = await file.read()
    feed_urls, errors = _extract_feed_urls_from_opml(content)

    added = 0
    skipped = 0

    for feed_url in feed_urls:
        exists = db.query(Source).filter(Source.feed_url == feed_url).first()
        if exists:
            skipped += 1
            continue

        # Name heuristic: prefer outline title/text if you later want, but MVP keeps it simple.
        name = "Imported Feed"
        db.add(Source(name=name, feed_url=feed_url, active=True))
        added += 1

    db.commit()

    return {
        "ok": True,
        "total_found": len(feed_urls),
        "added": added,
        "skipped": skipped,
        "errors": errors,
    }
