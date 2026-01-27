# RSS Story Inbox (MVP)

A minimal, industry-agnostic, human-in-the-loop RSS curation workflow:
- Ingest RSS feeds
- Cluster into stories (simple title similarity + time window)
- Rank by coverage + recency (+ optional include terms)
- Review one story at a time (Keep / Reject / Defer)
- Promote kept stories to Shortlist
- Generate/edit summaries (OpenAI) and publish
- Accumulates over time in Postgres

## Prerequisites
- Docker Desktop

## Setup

1) Copy env and set `OPENAI_API_KEY`:
```bash
cp .env.example .env
# edit .env and add OPENAI_API_KEY
```

2) Start:
```bash
docker compose up --build
```

3) Open:
- Web UI: http://localhost:3000
- API docs: http://localhost:8000/docs

## Add RSS sources
Go to http://localhost:3000/profile and add RSS feed URLs.

## Run ingest now
- From Queue screen click **Run ingest now**
- Or PowerShell: `./scripts/ingest-now.ps1`
- Or: `docker compose exec worker python worker.py ingest`

## MVP workflow
1) Queue: review clusters first (Keep/Reject/Defer)
2) Kept: promote to Shortlist
3) Shortlist: generate summary; edit; publish
4) Published: view archive

## Notes
- Clustering is intentionally simple (fast MVP). Swap `services/api/app/services/cluster/clusterer.py` later.
- Summary uses article extraction when possible, otherwise RSS excerpt fallback.
