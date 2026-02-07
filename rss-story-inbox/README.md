# RSS Curator (Story Inbox MVP)

RSS Curator is a **human-in-the-loop RSS curation tool** designed to help editors and analysts move from *raw feeds* to *publishable summaries* with minimal noise.

Instead of reading hundreds of individual articles, the system:

* Ingests RSS feeds
* Groups related articles into **stories**
* Ranks them by relevance
* Walks a human editor through a simple review workflow
* Optionally generates AI-assisted summaries for publishing

This repo represents an **MVP** focused on clarity, editorial control, and speed—not a fully automated news generator.

---

## Core Concepts

### Articles

Individual items pulled from RSS feeds.
Articles are deduplicated by URL and start in an **INBOX** state.

### Clusters (Stories)

Related articles grouped together based on:

* Title similarity
* Publication time window
* Source diversity (one article per source per cluster)

A cluster represents a single “story” covered by multiple outlets.

### Editorial Workflow

Clusters move through a simple lifecycle:

```
INBOX → KEPT → SHORTLIST → PUBLISHED
           ↘ REJECTED / DEFERRED
```

Actions apply to all inbox articles within a cluster.

---

## Features

### RSS Ingestion

* Add individual RSS feed URLs
* Import feeds via OPML
* Background worker periodically ingests new items

### Story Clustering

* Fuzzy title matching (RapidFuzz)
* Time-bounded grouping
* Canonical article selection per cluster

### Ranking & Queue

Clusters are ranked using:

* Number of distinct sources covering the story
* Recency
* Optional keyword “include terms”

Editors review stories one at a time via a **queue**.

### AI-Assisted Summaries (Optional)

If an OpenAI API key is provided, the app can:

* Extract article text
* Generate structured summaries (exec summary, key points, takeaways)
* Store drafts for human editing before publishing

AI is assistive, not autonomous.

---

## Architecture Overview

The app is split into four services, orchestrated with Docker Compose:

| Service    | Description                                        |
| ---------- | -------------------------------------------------- |
| **web**    | Next.js UI for editorial workflow                  |
| **api**    | FastAPI backend (business logic & database access) |
| **worker** | Scheduled job that triggers RSS ingestion          |
| **db**     | PostgreSQL database                                |

---

## Getting Started

### Prerequisites

* Docker
* Docker Compose

(Optional)

* OpenAI API key (for summary generation)

---

### Installation

Clone the repository:

```bash
git clone <repo-url>
cd RSS_Curator-main
```

Create an `.env` file in the project root:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=rss_story_inbox
DATABASE_URL=postgresql://postgres:postgres@db:5432/rss_story_inbox

OPENAI_API_KEY=sk-optional
```

Start the app:

```bash
docker compose up --build
```

---

### Accessing the App

| Component          | URL                                                      |
| ------------------ | -------------------------------------------------------- |
| Web UI             | [http://localhost:3000](http://localhost:3000)           |
| API Docs (Swagger) | [http://localhost:8000/docs](http://localhost:8000/docs) |
| API Base           | [http://localhost:8000](http://localhost:8000)           |

---

## Using the App

### 1. Add RSS Sources

From the UI (Profile page) or via API:

* Add RSS feed URLs manually
* Or import via OPML (`POST /admin/sources/import-opml`)

### 2. Configure Profile

Set:

* Audience description
* Editorial tone
* Include/exclude keywords

These influence ranking and AI summaries.

### 3. Ingest Feeds

Ingestion runs automatically via the worker, or manually:

```http
POST /admin/ingest
```

### 4. Review the Queue

* The queue shows one cluster at a time
* Actions: **Keep**, **Reject**, **Defer**

### 5. Shortlist & Summarize

* Promote kept clusters to the shortlist
* Generate AI summaries (if enabled)
* Edit drafts as needed

### 6. Publish

Publishing marks all shortlisted articles in a cluster as **PUBLISHED**.

---

## API Highlights

* `GET /queue/next` – fetch next ranked cluster
* `POST /queue/cluster/{id}/action` – keep/reject/defer
* `POST /shortlist/{cluster_id}/summarize` – generate AI summary
* `POST /admin/ingest` – trigger ingestion
* `POST /admin/sources/import-opml` – bulk feed import

Full API docs available at `/docs`.

---

## Design Philosophy

* **Human judgment first** – AI assists but never auto-publishes
* **Story-centric** – clusters matter more than individual articles
* **Low ceremony** – minimal workflow states, fast decisions
* **Composable** – simple services, clear boundaries

---

## Limitations / MVP Notes

* Clustering is title-based only (no embeddings yet)
* Ranking is heuristic, not ML-driven
* No authentication or multi-user support
* Designed for small-to-medium feed sets

---

## Future Directions (Ideas)

* Semantic clustering with embeddings
* Source weighting and trust scores
* Multi-profile / multi-publication support
* Export to CMS / newsletter tools
* Analytics on coverage and trends

---

## License

[Add license here]
