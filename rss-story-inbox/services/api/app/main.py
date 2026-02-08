import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import health, sources, profile, queue, kept, shortlist, published, summaries, admin_ingest, admin_opml, admin_sources

app = FastAPI(title="RSS Story Inbox (MVP)")
logger = logging.getLogger("uvicorn.error")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
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
app.include_router(admin_sources.router)


@app.on_event("startup")
def log_openai_env():
    logger.info("OPENAI_API_KEY loaded? %s", "yes" if os.getenv("OPENAI_API_KEY") else "no")
