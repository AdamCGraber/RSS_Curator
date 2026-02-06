import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../lib/api";
import { Cluster } from "../lib/types";
import StoryCard from "../components/StoryCard";
import ActionButtons from "../components/ActionButtons";

export default function QueuePage() {
  const [c, setC] = useState<Cluster | null>(null);
  const [err, setErr] = useState<string>("");
  const [notice, setNotice] = useState<string>("");
  const [thresholdPct, setThresholdPct] = useState<number>(88);
  const [timeWindowDays, setTimeWindowDays] = useState<number>(2);

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

  useEffect(() => {
    load();
    loadIngestSettings();
  }, []);

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

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Queue</h1>
      <p>Review one story at a time. Keep / Reject / Defer.</p>

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

        <button
          onClick={async () => {
            setErr("");
            setNotice("");
            try {
              const result = await apiPost("/admin/ingest", {
                cluster_similarity_threshold: thresholdPct / 100,
                cluster_time_window_days: timeWindowDays,
              });
              setNotice(
                `Ingest complete: ${result.inserted} inserted, ${result.skipped} skipped. Threshold ${Math.round(
                  result.cluster_similarity_threshold * 100
                )}%, window ${result.cluster_time_window_days} day(s).`
              );
              await load();
            } catch (e: any) {
              setErr(parseError(e));
            }
          }}
        >
          Start ingestion
        </button>
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
    </div>
  );
}
