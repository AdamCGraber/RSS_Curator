import os
import sys
import requests
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler

API_BASE = os.getenv("API_BASE_URL", "http://api:8000")

def run_ingest():
    try:
        r = requests.post(f"{API_BASE}/admin/ingest", timeout=300)
        print(datetime.utcnow().isoformat(), "ingest:", r.status_code, r.text[:300])
    except Exception as e:
        print("ingest failed:", e)

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"

    if cmd == "ingest":
        run_ingest()
        return

    hour = int(os.getenv("INGEST_HOUR_LOCAL", "2"))
    minute = int(os.getenv("INGEST_MINUTE_LOCAL", "0"))

    sched = BlockingScheduler()
    sched.add_job(run_ingest, "cron", hour=hour, minute=minute)
    print(f"Worker scheduler running. Ingest daily at {hour:02d}:{minute:02d}. API={API_BASE}")
    sched.start()

if __name__ == "__main__":
    main()
