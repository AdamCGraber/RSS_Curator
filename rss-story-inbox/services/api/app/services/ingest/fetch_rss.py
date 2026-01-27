import feedparser
from dateutil import parser as dtparser
from typing import List, Dict, Any

def fetch_feed(feed_url: str) -> List[Dict[str, Any]]:
    d = feedparser.parse(feed_url)
    items: List[Dict[str, Any]] = []
    for e in getattr(d, "entries", []):
        url = getattr(e, "link", None)
        title = getattr(e, "title", None) or ""
        summary = getattr(e, "summary", None)

        published = None
        for key in ["published", "updated", "created"]:
            if hasattr(e, key):
                try:
                    published = dtparser.parse(getattr(e, key))
                    break
                except Exception:
                    pass

        if not url or not title:
            continue

        items.append({"url": url, "title": title, "summary": summary, "published_at": published})
    return items
