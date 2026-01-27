import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../lib/api";
import { Cluster } from "../lib/types";
import StoryCard from "../components/StoryCard";
import ActionButtons from "../components/ActionButtons";

export default function QueuePage() {
  const [c, setC] = useState<Cluster | null>(null);
  const [err, setErr] = useState<string>("");

  async function load() {
    setErr("");
    try {
      const next = await apiGet("/queue/next");
      setC(next);
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  }

  useEffect(() => { load(); }, []);

  async function act(action: "keep" | "reject" | "defer") {
    if (!c) return;
    await apiPost(`/queue/cluster/${c.id}/action`, { action });
    await load();
  }

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Queue</h1>
      <p>Review one story at a time. Keep / Reject / Defer.</p>

      <div style={{ marginBottom: 12 }}>
        <button onClick={async () => { await apiPost("/admin/ingest"); await load(); }}>
          Run ingest now
        </button>
        <button onClick={load} style={{ marginLeft: 8 }}>Refresh</button>
      </div>

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
