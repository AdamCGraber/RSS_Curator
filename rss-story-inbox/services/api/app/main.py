from fastapi import FastAPI
from app.api.routes import health, sources, profile, queue, kept, shortlist, published, summaries, admin_ingest

app = FastAPI(title="RSS Story Inbox (MVP)")

app.include_router(health.router)
app.include_router(sources.router)
app.include_router(profile.router)
app.include_router(queue.router)
app.include_router(kept.router)
app.include_router(shortlist.router)
app.include_router(summaries.router)
app.include_router(published.router)
app.include_router(admin_ingest.router)
