import { useEffect, useMemo, useRef, useState } from "react";
import { apiGet, apiPost } from "../lib/api";
import { Cluster } from "../lib/types";
import StoryCard from "../components/StoryCard";
import ActionButtons from "../components/ActionButtons";

type IngestionJob = {
  job_id: string;
  status: "running" | "completed" | "failed";
  started_at: string;
  completed_at?: string | null;
  inserted?: number | null;
  skipped?: number | null;
  cluster_similarity_threshold?: number | null;
  cluster_time_window_days?: number | null;
  error?: string | null;
  message?: string | null;
};

const STALLED_SECONDS = 90;

export default function QueuePage() {
  const [c, setC] = useState<Cluster | null>(null);
  const [err, setErr] = useState<string>("");
  const [notice, setNotice] = useState<string>("");
  const [thresholdPct, setThresholdPct] = useState<number>(88);
  const [timeWindowDays, setTimeWindowDays] = useState<number>(2);
  const [ingestionJob, setIngestionJob] = useState<IngestionJob | null>(null);
  const [ingestionModalOpen, setIngestionModalOpen] = useState<boolean>(false);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);

  const modalRef = useRef<HTMLDivElement | null>(null);
  const startTimestampRef = useRef<number | null>(null);

  const running = ingestionJob?.status === "running";

  const elapsedLabel = useMemo(() => {
    const minutes = Math.floor(elapsedSeconds / 60);
    const seconds = elapsedSeconds % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }, [elapsedSeconds]);

  function parseError(e: any) {
    const message = e?.message || String(e);
    try {
      const parsed = JSON.parse(message);
      if (parsed?.detail) {
        if (typeof parsed.detail === "string") {
          return parsed.detail;
        }
        if (Array.isArray(parsed.detail)) {
          return parsed.detail
            .map((item) => item?.msg || item?.message || JSON.stringify(item))
            .join("; ");
        }
        return JSON.stringify(parsed.detail);
      }
    } catch {
      // ignore JSON parse errors
    }
    return message;
  }

  async function load(options?: { clearNotice?: boolean }) {
    const { clearNotice = false } = options ?? {};
    setErr("");
    if (clearNotice) {
      setNotice("");
    }
    try {
      const next = await apiGet("/queue/next");
      setC(next);
    } catch (e: any) {
      setErr(parseError(e));
    }
  }

  async function loadIngestSettings() {
    try {
      const settings = await apiGet("/admin/ingest/settings");
      setThresholdPct(Math.round((settings.cluster_similarity_threshold ?? 0.88) * 100));
      setTimeWindowDays(settings.cluster_time_window_days ?? 2);
    } catch {
      // ignore and use defaults
    }
  }

  async function syncCurrentIngestionStatus(options?: { openModalWhenRunning?: boolean }) {
    try {
      const current = await apiGet("/admin/ingest/status/current");
      if (current?.job_id) {
        setIngestionJob(current);
        if (options?.openModalWhenRunning) {
          setIngestionModalOpen(true);
        }
      }
    } catch {
      // ignore status read failure
    }
  }

  useEffect(() => {
    load();
    loadIngestSettings();
    syncCurrentIngestionStatus({ openModalWhenRunning: true });
  }, []);

  useEffect(() => {
    if (!ingestionJob) {
      startTimestampRef.current = null;
      setElapsedSeconds(0);
      return;
    }

    const startedMs = new Date(ingestionJob.started_at).getTime();
    startTimestampRef.current = Number.isNaN(startedMs) ? Date.now() : startedMs;

    const update = () => {
      if (!startTimestampRef.current) {
        setElapsedSeconds(0);
        return;
      }
      const seconds = Math.max(0, Math.floor((Date.now() - startTimestampRef.current) / 1000));
      setElapsedSeconds(seconds);
    };

    update();
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [ingestionJob?.job_id, ingestionJob?.started_at]);

  useEffect(() => {
    if (!running || !ingestionJob?.job_id) {
      return;
    }

    let canceled = false;
    let polls = 0;
    let timeoutId: number | null = null;

    const poll = async () => {
      polls += 1;
      try {
        const latest = await apiGet(`/admin/ingest/status/${ingestionJob.job_id}`);
        if (canceled) return;
        setIngestionJob(latest);

        if (latest.status === "completed") {
          console.info("ingestion_completed", { job_id: latest.job_id, completed_at: latest.completed_at });
          setNotice(
            `Ingestion complete: ${latest.inserted ?? 0} inserted, ${latest.skipped ?? 0} skipped. Refreshing queue...`
          );
          await load({ clearNotice: false });
          return;
        }

        if (latest.status === "failed") {
          console.info("ingestion_failed", { job_id: latest.job_id, error: latest.error });
          setIngestionModalOpen(true);
          return;
        }

        const delayMs = polls <= 10 ? 1000 : 2500;
        timeoutId = window.setTimeout(poll, delayMs);
      } catch (e: any) {
        const message = parseError(e);
        const terminalStatusError = message.includes("Ingestion job not found") || message.includes("status 404");

        if (terminalStatusError) {
          setIngestionJob((prev) => ({
            job_id: prev?.job_id || ingestionJob.job_id,
            status: "failed",
            started_at: prev?.started_at || new Date().toISOString(),
            completed_at: new Date().toISOString(),
            error: "Ingestion status is no longer available (job not found). Please retry ingestion.",
            message: "Ingestion failed.",
          }));
          setIngestionModalOpen(true);
          console.info("ingestion_failed", { job_id: ingestionJob.job_id, error: message });
          return;
        }

        if (!canceled) {
          timeoutId = window.setTimeout(poll, 3000);
        }
      }
    };

    poll();

    return () => {
      canceled = true;
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [running, ingestionJob?.job_id]);

  useEffect(() => {
    if (!ingestionModalOpen) {
      return;
    }

    const root = modalRef.current;
    const selector = "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])";
    const focusables = root ? Array.from(root.querySelectorAll<HTMLElement>(selector)) : [];
    focusables[0]?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Tab" || focusables.length === 0) {
        return;
      }
      const currentIndex = focusables.indexOf(document.activeElement as HTMLElement);
      const nextIndex = event.shiftKey
        ? (currentIndex <= 0 ? focusables.length - 1 : currentIndex - 1)
        : (currentIndex === focusables.length - 1 ? 0 : currentIndex + 1);
      event.preventDefault();
      focusables[nextIndex]?.focus();
    };

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [ingestionModalOpen, running]);

  async function act(action: "keep" | "reject" | "defer") {
    if (!c) return;
    setErr("");
    setNotice("");
    try {
      await apiPost(`/queue/cluster/${c.id}/action`, { action });
      await load({ clearNotice: true });
    } catch (e: any) {
      setErr(parseError(e));
    }
  }

  async function startIngestion() {
    setErr("");
    setNotice("");
    setIngestionModalOpen(true);
    const clickTime = Date.now();
    console.info("ingestion_start_clicked", { at: new Date(clickTime).toISOString() });

    let start: { job_id: string; already_running?: boolean };
    try {
      start = await apiPost("/admin/ingest", {
        cluster_similarity_threshold: thresholdPct / 100,
        cluster_time_window_days: timeWindowDays,
      });
    } catch (e: any) {
      const message = parseError(e);
      setIngestionJob({
        job_id: "start-failure",
        status: "failed",
        started_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
        error: message,
        message: "Ingestion failed.",
      });
      setIngestionModalOpen(true);
      return;
    }

    setIngestionJob({
      job_id: start.job_id,
      status: "running",
      started_at: new Date().toISOString(),
      message: "Ingestion running…",
    });

    if (start.already_running) {
      setNotice("Ingestion already running. Showing current job status.");
    }

    try {
      const status = await apiGet(`/admin/ingest/status/${start.job_id}`);
      setIngestionJob(status);
      console.info("ingestion_job_started", { job_id: status.job_id, already_running: start.already_running });
    } catch (e: any) {
      console.warn("ingestion_status_initial_fetch_failed", {
        job_id: start.job_id,
        error: parseError(e),
      });
      console.info("ingestion_job_started", { job_id: start.job_id, already_running: start.already_running });
    }
  }

  async function retryIngestion() {
    console.info("ingestion_retry_clicked", { at: new Date().toISOString() });
    await startIngestion();
  }

  const runningMessage =
    elapsedSeconds >= STALLED_SECONDS
      ? "Still working… this is taking longer than usual. You can run in background and continue reviewing the Queue."
      : "We’re fetching and processing new items. This can take a minute.";

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Queue</h1>
      <p>Review one story at a time. Keep / Reject / Defer.</p>

      {running && (
        <div
          role="status"
          aria-live="polite"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 10,
            marginBottom: 12,
            border: "1px solid #c7d2fe",
            borderRadius: 8,
            background: "#eef2ff",
            padding: "10px 12px",
          }}
        >
          <span aria-label="Ingestion in progress">⏳ Ingestion running… ({elapsedLabel})</span>
          <button
            onClick={() => setIngestionModalOpen(true)}
            style={{ textDecoration: "underline", background: "transparent", border: "none", cursor: "pointer" }}
          >
            View status
          </button>
        </div>
      )}

      <div style={{ marginBottom: 12, border: "1px solid #ddd", borderRadius: 8, padding: 12 }}>
        <h3 style={{ marginTop: 0 }}>Ingestion configuration</h3>
        <label>
          <b>Story similarity threshold</b> ({thresholdPct}%)
        </label>
        <input
          type="range"
          min={0}
          max={100}
          value={thresholdPct}
          onChange={(e) => setThresholdPct(Number(e.target.value))}
          style={{ width: "100%", marginTop: 6 }}
        />
        <p style={{ marginTop: 4, color: "#555" }}>
          Higher values create fewer, tighter clusters. Lower values group more loosely related stories.
        </p>

        <label htmlFor="window-days"><b>Story time window (days)</b></label>
        <input
          id="window-days"
          type="number"
          min={1}
          max={30}
          value={timeWindowDays}
          onChange={(e) => setTimeWindowDays(Number(e.target.value))}
          style={{ marginLeft: 8, width: 80 }}
        />
        <p style={{ marginTop: 4, color: "#555" }}>
          Only articles published within this window will be compared as the same story.
        </p>

        <button onClick={startIngestion}>Start ingestion</button>
        <button onClick={() => load({ clearNotice: true })} style={{ marginLeft: 8 }}>Refresh</button>
      </div>

      {notice && <p style={{ color: "seagreen" }}>{notice}</p>}
      {err && <p style={{ color: "crimson" }}>{err}</p>}
      {!c && !err && <p>No items in queue. Add sources in Profile, then ingest.</p>}
      {c && (
        <>
          <StoryCard c={c} />
          <ActionButtons
            onKeep={() => act("keep")}
            onReject={() => act("reject")}
            onDefer={() => act("defer")}
          />
        </>
      )}

      {ingestionModalOpen && ingestionJob && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="ingest-modal-title"
          aria-describedby="ingest-modal-desc"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.45)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            zIndex: 1000,
            padding: 16,
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget && !running) {
              setIngestionModalOpen(false);
            }
          }}
        >
          <div
            ref={modalRef}
            style={{ width: "min(560px, 100%)", borderRadius: 10, background: "#fff", padding: 18, boxShadow: "0 16px 36px rgba(0,0,0,0.25)" }}
          >
            <h2 id="ingest-modal-title" style={{ marginTop: 0 }}>
              {running ? "Ingestion running…" : ingestionJob.status === "completed" ? "Ingestion complete." : "Ingestion failed."}
            </h2>

            <p id="ingest-modal-desc" style={{ marginTop: 0 }} aria-live="polite">
              {running ? runningMessage : ingestionJob.status === "completed" ? "Queue is ready to refresh with newly processed items." : "We could not complete ingestion. Review the error and retry."}
            </p>

            {running && (
              <>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  <span aria-label="Ingestion in progress">⏳</span>
                  <span>Elapsed time: {elapsedLabel}</span>
                </div>
                <div aria-hidden="true" style={{ height: 8, borderRadius: 999, background: "#e5e7eb", overflow: "hidden", marginBottom: 16 }}>
                  <div style={{ width: "35%", height: "100%", background: "#4f46e5", animation: "pulse 1.2s ease-in-out infinite" }} />
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    onClick={() => {
                      console.info("ingestion_run_in_background_clicked", { job_id: ingestionJob.job_id });
                      setIngestionModalOpen(false);
                    }}
                  >
                    Run in background
                  </button>
                </div>
              </>
            )}

            {ingestionJob.status === "completed" && (
              <div style={{ display: "grid", gap: 6 }}>
                <p style={{ marginBottom: 0 }}>
                  Inserted: {ingestionJob.inserted ?? 0}; Skipped: {ingestionJob.skipped ?? 0}
                </p>
                <div>
                  <button
                    onClick={async () => {
                      await load({ clearNotice: false });
                      setIngestionModalOpen(false);
                    }}
                  >
                    Refresh Queue
                  </button>
                  <button onClick={() => setIngestionModalOpen(false)} style={{ marginLeft: 8 }}>Dismiss</button>
                </div>
              </div>
            )}

            {ingestionJob.status === "failed" && (
              <div>
                <p style={{ color: "crimson", marginBottom: 6 }}>{ingestionJob.error || "Ingestion failed unexpectedly."}</p>
                <details>
                  <summary>Details</summary>
                  <pre style={{ background: "#f8fafc", padding: 10, borderRadius: 6, overflowX: "auto" }}>
{JSON.stringify(ingestionJob, null, 2)}
                  </pre>
                </details>
                <div style={{ marginTop: 10 }}>
                  <button onClick={retryIngestion}>Retry ingestion</button>
                  <button
                    style={{ marginLeft: 8 }}
                    onClick={() => {
                      navigator.clipboard?.writeText(JSON.stringify(ingestionJob, null, 2));
                    }}
                  >
                    Copy error details
                  </button>
                  <button onClick={() => setIngestionModalOpen(false)} style={{ marginLeft: 8 }}>Dismiss</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
