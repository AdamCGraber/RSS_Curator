import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../lib/api";
import { Cluster } from "../lib/types";

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
              <b>{c.cluster_title}</b> — coverage {c.coverage_count}
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
