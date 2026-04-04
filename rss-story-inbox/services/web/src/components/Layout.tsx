import Link from "next/link";
import { useRouter } from "next/router";
import { useEffect, useState } from "react";
import { apiGet } from "../lib/api";

type IngestionJob = {
  job_id: string;
  status: "RUNNING" | "COMPLETED" | "FAILED" | "PAUSED";
};

const DISMISSED_JOB_STORAGE_KEY = "ingestion-alert-dismissed-job-id";
const LAST_RUNNING_JOB_STORAGE_KEY = "ingestion-alert-last-running-job-id";

export default function Layout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [completedJobId, setCompletedJobId] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;

    let mounted = true;

    const syncIngestionStatus = async () => {
      try {
        const latestRunning = (await apiGet("/admin/ingest/status/current")) as IngestionJob | null;
        if (!mounted) return;

        if (latestRunning?.status === "RUNNING") {
          window.sessionStorage.setItem(LAST_RUNNING_JOB_STORAGE_KEY, latestRunning.job_id);
          setCompletedJobId(null);
          return;
        }

        const lastRunningJobId = window.sessionStorage.getItem(LAST_RUNNING_JOB_STORAGE_KEY);
        let latestById: IngestionJob | null = null;
        if (lastRunningJobId) {
          try {
            latestById = (await apiGet(`/admin/ingest/status/${lastRunningJobId}`)) as IngestionJob;
          } catch {
            latestById = null;
          }
        }

        let candidateStatus = latestById;
        if (!candidateStatus || candidateStatus.status !== "COMPLETED") {
          candidateStatus = (await apiGet("/admin/ingest/status/latest")) as IngestionJob | null;
        }

        if (candidateStatus?.status === "RUNNING") {
          window.sessionStorage.setItem(LAST_RUNNING_JOB_STORAGE_KEY, candidateStatus.job_id);
          setCompletedJobId(null);
          return;
        }

        if (!mounted) return;
        if (!candidateStatus || candidateStatus.status !== "COMPLETED") {
          setCompletedJobId(null);
          return;
        }

        const dismissedJobId = window.sessionStorage.getItem(DISMISSED_JOB_STORAGE_KEY);
        if (dismissedJobId === candidateStatus.job_id) {
          return;
        }

        setCompletedJobId(candidateStatus.job_id);
      } catch {
        // no-op: this endpoint is best effort
      }
    };

    void syncIngestionStatus();
    const interval = window.setInterval(() => {
      void syncIngestionStatus();
    }, 4000);

    return () => {
      mounted = false;
      window.clearInterval(interval);
    };
  }, []);

  function dismissCompletedAlert() {
    if (typeof window !== "undefined" && completedJobId) {
      window.sessionStorage.setItem(DISMISSED_JOB_STORAGE_KEY, completedJobId);
    }
    setCompletedJobId(null);
  }

  function seeResults() {
    dismissCompletedAlert();
    void router.push("/");
  }

  const showCompletionAlert = Boolean(completedJobId) && router.pathname !== "/";

  return (
    <div style={{ maxWidth: 980, margin: "0 auto", padding: 16, fontFamily: "system-ui" }}>
      <header style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>RSS Story Inbox</h2>
        <nav style={{ display: "flex", gap: 10 }}>
          <Link href="/">Queue</Link>
          <Link href="/kept">Kept</Link>
          <Link href="/shortlist">Shortlist</Link>
          <Link href="/published">Published</Link>
          <Link href="/profile">Profile</Link>
        </nav>
      </header>

      {showCompletionAlert && (
        <div
          role="status"
          aria-live="polite"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            flexWrap: "wrap",
            border: "1px solid #10b981",
            borderRadius: 8,
            background: "#ecfdf5",
            color: "#065f46",
            padding: "10px 12px",
            marginBottom: 16,
          }}
        >
          <span>Ingestion has completed.</span>
          <button onClick={dismissCompletedAlert}>Dismiss</button>
          <button onClick={seeResults}>See results</button>
        </div>
      )}

      {children}
    </div>
  );
}
