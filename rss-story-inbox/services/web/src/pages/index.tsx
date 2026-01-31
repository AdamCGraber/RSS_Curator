import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../lib/api";
import { Cluster } from "../lib/types";
import StoryCard from "../components/StoryCard";
import ActionButtons from "../components/ActionButtons";

export default function QueuePage() {
  const [c, setC] = useState<Cluster | null>(null);
  const [err, setErr] = useState<string>("");
  const [notice, setNotice] = useState<string>("");

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

  useEffect(() => { load(); }, []);

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

      <div style={{ marginBottom: 12 }}>
        <button
          onClick={async () => {
            setErr("");
            setNotice("");
            try {
              const result = await apiPost("/admin/ingest");
              setNotice(`Ingest complete: ${result.inserted} inserted, ${result.skipped} skipped.`);
              await load();
            } catch (e: any) {
              setErr(parseError(e));
            }
          }}
        >
          Run ingest now
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
