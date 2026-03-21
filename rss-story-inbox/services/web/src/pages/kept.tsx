import { CSSProperties, useEffect, useState } from "react";
import { apiGet, apiPost } from "../lib/api";
import { Cluster } from "../lib/types";

const primaryUrlStyle: CSSProperties = {
  marginTop: 4,
  fontSize: 14,
  overflowWrap: "anywhere",
};

const primaryUrlLinkStyle: CSSProperties = {
  color: "#0a66c2",
  textDecoration: "underline",
};

export default function KeptPage() {
  const [items, setItems] = useState<Cluster[]>([]);
  const [err, setErr] = useState("");

  async function load() {
    setErr("");
    try {
      setItems(await apiGet("/kept"));
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  }

  useEffect(() => { load(); }, []);

  async function promote(id: number) {
    await apiPost(`/kept/cluster/${id}/promote`);
    await load();
  }

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Kept</h1>
      {err && <p style={{ color: "crimson" }}>{err}</p>}
      <button onClick={load}>Refresh</button>

      {items.length === 0 ? <p>No kept items yet.</p> : (
        <ul>
          {items.map(c => (
            <li key={c.id} style={{ marginBottom: 10 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
                <b>{c.cluster_title}</b>
                <span style={{ color: "#555" }}>score {c.score.toFixed(1)}</span>
                <span>— coverage {c.coverage_count}</span>
              </div>
              {c.canonical?.url && (
                <div style={primaryUrlStyle}>
                  <a
                    href={c.canonical.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={primaryUrlLinkStyle}
                  >
                    {c.canonical.url}
                  </a>
                </div>
              )}
              <div style={{ marginTop: 6 }}>
                <button onClick={() => promote(c.id)}>Promote to Shortlist</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
