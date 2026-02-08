from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session
from xml.etree import ElementTree as ET
from typing import List, Tuple, Dict, Any
import html

from app.core.db import get_db
from app.models.source import Source
from app.services.sources_state import bump_sources_version, publish_sources_changed, refresh_sources_cache

router = APIRouter(prefix="/admin", tags=["admin"])


def _best_name(attrs: Dict[str, str]) -> str:
    # Prefer title, then text; decode HTML entities (e.g., NYT &gt; ...)
    raw = attrs.get("title") or attrs.get("text") or "Imported Feed"
    return html.unescape(raw).strip() or "Imported Feed"


def _extract_feeds_from_opml(opml_bytes: bytes) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Returns (feeds, errors)

    feeds = [
      {
        "feed_url": "...",
        "name": "...",
        "site_url": "...",   # htmlUrl if present
        "category": "..."    # parent folder text/title if present
      },
      ...
    ]
    """
    errors: List[str] = []
    try:
        root = ET.fromstring(opml_bytes)
    except Exception as e:
        return [], [f"Failed to parse OPML XML: {e}"]

    feeds: List[Dict[str, Any]] = []

    # Walk the tree manually so we can capture parent folder/category
    def walk(node: ET.Element, current_category: str | None = None):
        if node.tag == "outline":
            xml_url = node.attrib.get("xmlUrl") or node.attrib.get("xmlurl")
            if xml_url:
                feed_url = xml_url.strip()
                if feed_url:
                    feeds.append(
                        {
                            "feed_url": feed_url,
                            "name": _best_name(node.attrib),
                            "site_url": (node.attrib.get("htmlUrl") or node.attrib.get("htmlurl") or "").strip() or None,
                            "category": current_category or None,
                        }
                    )

                node_category = current_category
            else:
                node_category = node.attrib.get("title") or node.attrib.get("text")
                node_category = html.unescape(node_category).strip() if node_category else current_category

            # Recurse into children
            for child in list(node):
                walk(child, node_category)
        else:
            for child in list(node):
                walk(child, current_category)

    walk(root, None)

    # Deduplicate by feed_url while preserving order
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for f in feeds:
        u = f["feed_url"]
        if u in seen:
            continue
        seen.add(u)
        deduped.append(f)

    return deduped, errors


@router.post("/sources/import-opml")
def import_opml(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Sync route + sync DB: FastAPI runs this in a threadpool.
    Parses OPML and imports RSS feeds from xmlUrl with nice names.
    Returns a detailed report for UX + downloadable results.
    """
    content = file.file.read()  # sync read
    feeds, errors = _extract_feeds_from_opml(content)

    feed_urls = [f["feed_url"] for f in feeds]

    # Prefetch existing in one query
    existing_urls = {
        r[0]
        for r in db.query(Source.feed_url)
        .filter(Source.feed_url.in_(feed_urls))
        .all()
    }

    added_items = []
    skipped_items = []

    with db.begin():
        for f in feeds:
            if f["feed_url"] in existing_urls:
                skipped_items.append(f)
                continue

            # Use OPML title/text as the source name
            db.add(Source(name=f["name"], feed_url=f["feed_url"], active=True))
            added_items.append(f)

        version = None
        if added_items:
            version = bump_sources_version(db)
            refresh_sources_cache(db, version)

    if version is not None:
        publish_sources_changed(db, version)

    return {
        "ok": True,
        "total_found": len(feeds),
        "added": len(added_items),
        "skipped": len(skipped_items),
        "errors": errors,
        "version": version,
        "added_items": added_items,
        "skipped_items": skipped_items,
    }
