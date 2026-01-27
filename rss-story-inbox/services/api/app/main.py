from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import health, sources, profile, queue, kept, shortlist, published, summaries, admin_ingest, admin_opml

app = FastAPI(title="RSS Story Inbox (MVP)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(sources.router)
app.include_router(profile.router)
app.include_router(queue.router)
app.include_router(kept.router)
app.include_router(shortlist.router)
app.include_router(summaries.router)
app.include_router(published.router)
app.include_router(admin_ingest.router)
app.include_router(admin_opml.router)
