import { useEffect, useState } from "react";
import { apiGet } from "../lib/api";
import { PublishedItem } from "../lib/types";

export default function PublishedPage() {
  const [items, setItems] = useState<PublishedItem[]>([]);
  const [err, setErr] = useState("");

  async function load() {
    setErr("");
    try {
      setItems(await apiGet("/published"));
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Published</h1>
      {err && <p style={{ color: "crimson" }}>{err}</p>}
      <button onClick={load}>Refresh</button>

      {items.length === 0 ? <p>No published items yet.</p> : (
        <div style={{ marginTop: 12 }}>
          {items.map(it => (
            <div key={it.cluster_id} style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12, marginBottom: 12 }}>
              <h3 style={{ marginTop: 0 }}>{it.title}</h3>
              <div style={{ color: "#555" }}>
                Coverage: {it.coverage_count} — Latest: {it.latest_published_at || "n/a"}
              </div>
              <pre style={{ whiteSpace: "pre-wrap", marginTop: 10 }}>
                {it.summary || "(No summary yet)"}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
