import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "../lib/api";
import { Cluster } from "../lib/types";
import StoryCard from "../components/StoryCard";
import ActionButtons from "../components/ActionButtons";
import QuickKeyModule, { QueueAction } from "../components/QuickKeyModule";

type IngestionJob = {
  job_id: string;
  status: "RUNNING" | "COMPLETED" | "FAILED" | "PAUSED";
  phase?: "DISCOVERING_FEEDS" | "IMPORTING_ITEMS" | "CLUSTERING" | "SCORING" | "FINALIZING";
  started_at: string;
  updated_at: string;
  total_items: number;
  processed_items: number;
  progress_percent: number;
};

type IngestionJobStartResponse = {
  job_id: string;
  status: "RUNNING";
  already_running?: boolean;
};

type QueueActionResponse = {
  ok: boolean;
  affected_article_ids: number[];
};

type QueueCountResponse = {
  articles_to_review: number;
};

export default function QueuePage() {
  const [c, setC] = useState<Cluster | null>(null);
  const [articlesToReview, setArticlesToReview] = useState<number | null>(null);
  const [countWarning, setCountWarning] = useState<string>("");
  const [countWarningDismissed, setCountWarningDismissed] = useState<boolean>(false);
  const [countRetryLoading, setCountRetryLoading] = useState<boolean>(false);
  const [previousCluster, setPreviousCluster] = useState<Cluster | null>(null);
  const [previousActionArticleIds, setPreviousActionArticleIds] = useState<number[]>([]);
  const [err, setErr] = useState<string>("");
  const [notice, setNotice] = useState<string>("");
  const [thresholdPct, setThresholdPct] = useState<number>(88);
  const [timeWindowDays, setTimeWindowDays] = useState<number>(2);
  const [ingestionJob, setIngestionJob] = useState<IngestionJob | null>(null);
  const [ingestionModalOpen, setIngestionModalOpen] = useState<boolean>(false);
  const [settingsModalOpen, setSettingsModalOpen] = useState<boolean>(false);

  const modalRef = useRef<HTMLDivElement | null>(null);
  const settingsModalRef = useRef<HTMLDivElement | null>(null);
  const running = ingestionJob?.status === "RUNNING";

  const ingestionPhases = ["DISCOVERING_FEEDS", "IMPORTING_ITEMS", "CLUSTERING", "SCORING", "FINALIZING"] as const;
  const phaseTitleMap: Record<(typeof ingestionPhases)[number], string> = {
    DISCOVERING_FEEDS: "Discovering Feeds",
    IMPORTING_ITEMS: "Importing Items",
    CLUSTERING: "Clustering",
    SCORING: "Scoring",
    FINALIZING: "Finalizing",
  };

  function getPhaseStatus(job: IngestionJob) {
    const phase = job.phase && ingestionPhases.includes(job.phase) ? job.phase : "DISCOVERING_FEEDS";
    const phaseIndex = ingestionPhases.indexOf(phase) + 1;
    return `Phase ${phaseIndex} of ${ingestionPhases.length}: ${phaseTitleMap[phase]}`;
  }

  function getPhaseCountText(job: IngestionJob) {
    const phase = job.phase && ingestionPhases.includes(job.phase) ? job.phase : "DISCOVERING_FEEDS";
    if (phase === "DISCOVERING_FEEDS") return `${job.processed_items} feeds discovered`;
    if (phase === "IMPORTING_ITEMS") return `${job.processed_items} items imported`;
    if (phase === "CLUSTERING") return `${job.processed_items} clusters collected`;
    if (phase === "SCORING") return `${job.processed_items} clusters/items scored`;
    return "Finalizing";
  }

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

  async function handleTerminalIngestionStatus(status: IngestionJob) {
    if (status.status === "COMPLETED") {
      console.info("ingestion_completed", { job_id: status.job_id, updated_at: status.updated_at });
      setNotice("Ingestion complete. Refreshing queue...");
      await load({ clearNotice: false });
      return;
    }

    if (status.status === "FAILED") {
      console.info("ingestion_failed", { job_id: status.job_id });
      setIngestionModalOpen(true);
    }
  }

  async function refreshQueueCount(options?: { showWarning?: boolean; reopenDismissedWarning?: boolean }) {
    const { showWarning = true, reopenDismissedWarning = false } = options ?? {};
    try {
      const count = await (apiGet("/queue/count") as Promise<QueueCountResponse>);
      setArticlesToReview(count.articles_to_review ?? 0);
      setCountWarning("");
      setCountWarningDismissed(false);
      return true;
    } catch (e: any) {
      setArticlesToReview(null);
      if (showWarning) {
        const detail = parseError(e);
        setCountWarning(`Could not load queue count (${detail}).`);
        setCountWarningDismissed((wasDismissed) => (reopenDismissedWarning ? false : wasDismissed));
      }
      return false;
    }
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
      setPreviousCluster(null);
      setPreviousActionArticleIds([]);
      await refreshQueueCount({ showWarning: true });
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

  async function syncCurrentIngestionStatus(options: {
    openModalWhenRunning?: boolean;
    jobId?: string;
  } = {}) {
    const { openModalWhenRunning, jobId } = options;

    try {
      let latest: IngestionJob | null = null;

      if (jobId) {
        latest = (await apiGet(`/admin/ingest/status/${jobId}`)) as IngestionJob;
      } else {
        latest = (await apiGet("/admin/ingest/status/current")) as IngestionJob | null;
      }

      if (!latest) return;

      setIngestionJob(latest);
      if (latest.status === "RUNNING" && openModalWhenRunning) {
        setIngestionModalOpen(true);
      }

      if (latest.status !== "RUNNING") {
        await handleTerminalIngestionStatus(latest);
      }
    } catch {
      // best effort; endpoint may not exist in all deployments
    }
  }

  async function act(action: "keep" | "reject") {
    if (!c) return;
    const currentCluster = c;
    setErr("");
    setNotice("");
    try {
      const actionResult = await apiPost(`/queue/cluster/${c.id}/action`, { action }) as QueueActionResponse;
      setPreviousCluster(currentCluster);
      setPreviousActionArticleIds(actionResult.affected_article_ids || []);
      const next = await apiGet("/queue/next");
      setC(next);
      await refreshQueueCount({ showWarning: true });
    } catch (e: any) {
      setErr(parseError(e));
    }
  }

  async function handleUndo() {
    if (!previousCluster || previousActionArticleIds.length === 0) return;
    setErr("");
    setNotice("");
    try {
      await apiPost(`/queue/cluster/${previousCluster.id}/undo`, {
        article_ids: previousActionArticleIds,
      });
      setC(previousCluster);
      await refreshQueueCount({ showWarning: true });
      setPreviousCluster(null);
      setPreviousActionArticleIds([]);
    } catch (e: any) {
      setErr(parseError(e));
    }
  }

  async function handleRetryCount() {
    setCountRetryLoading(true);
    try {
      await refreshQueueCount({ showWarning: true, reopenDismissedWarning: true });
    } finally {
      setCountRetryLoading(false);
    }
  }

  function handleDismissCountWarning() {
    setCountWarningDismissed(true);
  }

  function handleQuickAction(action: QueueAction) {
    if (action === "undo") {
      void handleUndo();
      return;
    }
    void act(action);
  }

  async function startIngestion() {
    setErr("");
    setNotice("");
    setIngestionModalOpen(true);

    let jobStart: IngestionJobStartResponse;
    try {
      jobStart = await apiPost("/admin/ingest", {
        cluster_similarity_threshold: thresholdPct / 100,
        cluster_time_window_days: timeWindowDays,
      });
    } catch (e: any) {
      const message = parseError(e);
      setIngestionJob({
        job_id: "sync-ingest",
        status: "FAILED",
        started_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        total_items: 0,
        processed_items: 0,
        progress_percent: 0,
      });
      setErr(message);
      setIngestionModalOpen(true);
      return;
    }

    if (jobStart.status !== "RUNNING" || !jobStart.job_id) {
      setErr("Ingestion start returned an invalid response.");
      return;
    }

    setIngestionJob({
      job_id: jobStart.job_id,
      status: "RUNNING",
      started_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      total_items: 0,
      processed_items: 0,
      progress_percent: 0,
    });

    void syncCurrentIngestionStatus({
      jobId: jobStart.job_id,
      openModalWhenRunning: true,
    });
  }

  async function retryIngestion() {
    await startIngestion();
  }

  async function handleRefreshQueueFromModal() {
    await load({ clearNotice: false });
    setIngestionModalOpen(false);
  }

  function handleCopyErrorDetails() {
    navigator.clipboard?.writeText(JSON.stringify(ingestionJob, null, 2));
  }

  useEffect(() => {
    void (async () => {
      await Promise.allSettled([
        load(),
        loadIngestSettings(),
        syncCurrentIngestionStatus({ openModalWhenRunning: true }),
      ]);
    })();
  }, []);

  useEffect(() => {
    if (!running || !ingestionJob?.job_id) return;

    const interval = window.setInterval(() => {
      void syncCurrentIngestionStatus({ jobId: ingestionJob.job_id });
    }, 4000);

    return () => window.clearInterval(interval);
  }, [ingestionJob?.job_id, running]);

  useEffect(() => {
    if (!ingestionModalOpen) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !running) {
        setIngestionModalOpen(false);
        return;
      }

      if (event.key !== "Tab") return;
      const root = modalRef.current;
      if (!root) return;

      const focusables = Array.from(
        root.querySelectorAll<HTMLElement>(
          'button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])'
        )
      ).filter((el) => !el.hasAttribute("disabled"));

      if (focusables.length === 0) return;

      const currentIndex = focusables.indexOf(document.activeElement as HTMLElement);
      const nextIndex = event.shiftKey
        ? currentIndex <= 0
          ? focusables.length - 1
          : currentIndex - 1
        : currentIndex === focusables.length - 1
          ? 0
          : currentIndex + 1;

      event.preventDefault();
      focusables[nextIndex]?.focus();
    };

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [ingestionModalOpen, running]);

  useEffect(() => {
    if (!settingsModalOpen) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSettingsModalOpen(false);
      }
    };

    document.addEventListener("keydown", onKeyDown);
    settingsModalRef.current?.querySelector<HTMLElement>("button, input, [tabindex]")?.focus();

    return () => document.removeEventListener("keydown", onKeyDown);
  }, [settingsModalOpen]);

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Queue</h1>
      <p>Review one story at a time. Keep / Reject.</p>

      {running && ingestionJob && (
        <div
          role="status"
          aria-live="polite"
          style={{
            display: "grid",
            gap: 8,
            marginBottom: 12,
            border: "1px solid #c7d2fe",
            borderRadius: 8,
            background: "#eef2ff",
            padding: "10px 12px",
          }}
        >
          <span aria-label="Ingestion in progress">⏳ Ingestion running…</span>
          <div
            style={{
              height: 10,
              borderRadius: 999,
              overflow: "hidden",
              background: "#dbeafe",
            }}
          >
            <div
              style={{
                width: `${Math.min(100, Math.max(0, ingestionJob.progress_percent || 0))}%`,
                height: "100%",
                background: "#4f46e5",
                transition: "width 0.5s ease",
              }}
            />
          </div>
          <span>
            {getPhaseStatus(ingestionJob)} · {Math.round(ingestionJob.progress_percent || 0)}% · {getPhaseCountText(ingestionJob)}
          </span>
        </div>
      )}

      <div
        style={{
          position: "sticky",
          top: 12,
          zIndex: 20,
          display: "flex",
          alignItems: "center",
          gap: 10,
          flexWrap: "wrap",
          background: "#fff",
          border: "1px solid #e5e7eb",
          borderRadius: 8,
          padding: "10px 12px",
          marginBottom: 16,
        }}
      >
        <button onClick={startIngestion}>Start ingestion</button>
        <button onClick={() => load({ clearNotice: true })}>Refresh</button>
        <div
          style={{
            width: 1,
            alignSelf: "stretch",
            background: "#e5e7eb",
            margin: "0 2px",
          }}
          aria-hidden="true"
        />
        <ActionButtons
          onKeep={() => void act("keep")}
          onReject={() => void act("reject")}
          onUndo={() => void handleUndo()}
          disabled={!c}
          undoDisabled={!previousCluster || previousActionArticleIds.length === 0}
          articlesToReview={articlesToReview}
        />
        <div style={{ marginLeft: "auto" }} />
        <button onClick={() => setSettingsModalOpen(true)}>Settings</button>
      </div>

      {notice && <p style={{ color: "seagreen" }}>{notice}</p>}
      {countWarning && !countWarningDismissed && (
        <div
          role="status"
          aria-live="polite"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            flexWrap: "wrap",
            border: "1px solid #f59e0b",
            borderRadius: 8,
            background: "#fffbeb",
            color: "#92400e",
            padding: "10px 12px",
            marginBottom: 10,
          }}
        >
          <span>{countWarning} You can keep reviewing while count is unavailable.</span>
          <button onClick={() => void handleRetryCount()} disabled={countRetryLoading}>
            {countRetryLoading ? "Retrying..." : "Retry count"}
          </button>
          <button onClick={handleDismissCountWarning} disabled={countRetryLoading}>
            Cancel
          </button>
        </div>
      )}
      {err && <p style={{ color: "crimson" }}>{err}</p>}
      {!c && !err && <p>No items in queue. Add sources in Profile, then ingest.</p>}
      {c && <StoryCard c={c} />}

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-modal-title"
        aria-hidden={!settingsModalOpen}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.45)",
          display: settingsModalOpen ? "flex" : "none",
          justifyContent: "center",
          alignItems: "center",
          zIndex: 1000,
          padding: 16,
        }}
        onClick={(e) => {
          if (e.target === e.currentTarget) {
            setSettingsModalOpen(false);
          }
        }}
      >
        <div
          ref={settingsModalRef}
          style={{
            width: "min(700px, 100%)",
            borderRadius: 10,
            background: "#fff",
            padding: 18,
            boxShadow: "0 16px 36px rgba(0,0,0,0.25)",
          }}
        >
          <h2 id="settings-modal-title" style={{ marginTop: 0 }}>
            Settings
          </h2>

          <div style={{ marginBottom: 16 }}>
            <label htmlFor="threshold-range">
              <b>Story similarity threshold</b> ({thresholdPct}%)
            </label>
            <input
              id="threshold-range"
              type="range"
              min={50}
              max={100}
              value={thresholdPct}
              onChange={(e) => setThresholdPct(Number(e.target.value))}
              style={{ width: "100%", marginTop: 6 }}
            />
            <p style={{ marginTop: 4, color: "#555" }}>
              Higher values create fewer, tighter clusters. Lower values group more loosely related stories.
            </p>

            <label htmlFor="window-days">
              <b>Story time window (days)</b>
            </label>
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
          </div>

          <QuickKeyModule
            onAction={handleQuickAction}
            disabled={(!c && !(previousCluster && previousActionArticleIds.length > 0)) || ingestionModalOpen}
          />

          <div style={{ marginTop: 12 }}>
            <button onClick={() => setSettingsModalOpen(false)}>Close</button>
          </div>
        </div>
      </div>

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
            style={{
              width: "min(560px, 100%)",
              borderRadius: 10,
              background: "#fff",
              padding: 18,
              boxShadow: "0 16px 36px rgba(0,0,0,0.25)",
            }}
          >
            <h2 id="ingest-modal-title" style={{ marginTop: 0 }}>
              {running ? "Ingestion running…" : ingestionJob.status === "COMPLETED" ? "Ingestion complete." : "Ingestion failed."}
            </h2>

            <p id="ingest-modal-desc" style={{ marginTop: 0 }} aria-live="polite">
              {running
                ? "Ingestion is running in the background."
                : ingestionJob.status === "COMPLETED"
                  ? "Queue is ready to refresh with newly processed items."
                  : "We could not complete ingestion. Review the error and retry."}
            </p>

            {running && (
              <>
                <div style={{ display: "grid", gap: 8, marginBottom: 12 }}>
                  <div>Status: {getPhaseStatus(ingestionJob)}</div>
                  <div
                    aria-hidden="true"
                    style={{ height: 16, borderRadius: 8, background: "#eee", overflow: "hidden" }}
                  >
                    <div
                      style={{
                        height: "100%",
                        background: "#4caf50",
                        transition: "width 0.5s ease",
                        width: `${Math.min(100, Math.max(0, ingestionJob.progress_percent || 0))}%`,
                      }}
                    />
                  </div>
                  <div>{Math.round(ingestionJob.progress_percent || 0)}%</div>
                  <div>{getPhaseCountText(ingestionJob)}</div>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button onClick={() => setIngestionModalOpen(false)}>Run in background</button>
                </div>
              </>
            )}

            {ingestionJob.status === "COMPLETED" && (
              <div style={{ display: "grid", gap: 6 }}>
                <p style={{ marginBottom: 0 }}>
                  {ingestionJob.processed_items} / {ingestionJob.total_items} items processed
                </p>
                <div>
                  <button onClick={handleRefreshQueueFromModal}>Refresh Queue</button>
                  <button onClick={() => setIngestionModalOpen(false)} style={{ marginLeft: 8 }}>
                    Dismiss
                  </button>
                </div>
              </div>
            )}

            {ingestionJob.status === "FAILED" && (
              <div>
                <p style={{ color: "crimson", marginBottom: 6 }}>Ingestion failed unexpectedly.</p>
                <details>
                  <summary>Details</summary>
                  <pre
                    style={{
                      background: "#f8fafc",
                      padding: 10,
                      borderRadius: 6,
                      overflowX: "auto",
                    }}
                  >
                    {JSON.stringify(ingestionJob, null, 2)}
                  </pre>
                </details>
                <div style={{ marginTop: 10 }}>
                  <button onClick={retryIngestion}>Retry ingestion</button>
                  <button style={{ marginLeft: 8 }} onClick={handleCopyErrorDetails}>
                    Copy error details
                  </button>
                  <button onClick={() => setIngestionModalOpen(false)} style={{ marginLeft: 8 }}>
                    Dismiss
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
