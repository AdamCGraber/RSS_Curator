import { CSSProperties, useEffect, useState } from "react";
import { apiGet, apiPost, apiPut } from "../lib/api";
import { Cluster } from "../lib/types";
import SummaryEditor from "../components/SummaryEditor";

const primaryUrlStyle: CSSProperties = {
  marginTop: 4,
  fontSize: 14,
  overflowWrap: "anywhere",
};

const primaryUrlLinkStyle: CSSProperties = {
  color: "#0a66c2",
  textDecoration: "underline",
};

function PrimaryUrl({ cluster }: { cluster: Cluster }) {
  if (!cluster.canonical?.url) return null;

  return (
    <div style={primaryUrlStyle}>
      <a
        href={cluster.canonical.url}
        target="_blank"
        rel="noopener noreferrer"
        style={primaryUrlLinkStyle}
      >
        {cluster.canonical.url}
      </a>
    </div>
  );
}

export default function ShortlistPage() {
  const [items, setItems] = useState<Cluster[]>([]);
  const [selected, setSelected] = useState<Cluster | null>(null);
  const [summaryId, setSummaryId] = useState<number | null>(null);
  const [text, setText] = useState("");
  const [err, setErr] = useState("");

  async function load() {
    setErr("");
    try {
      setItems(await apiGet("/shortlist"));
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  }

  async function loadSummary(clusterId: number) {
    const s = await apiGet(`/summaries/cluster/${clusterId}`);
    if (!s) {
      setSummaryId(null);
      setText("");
      return;
    }
    setSummaryId(s.id);
    setText(s.edited_text || s.draft_text || "");
  }

  useEffect(() => { load(); }, []);

  async function generate(clusterId: number) {
    await apiPost(`/shortlist/cluster/${clusterId}/generate-summary`);
    await loadSummary(clusterId);
  }

  async function save() {
    if (!summaryId) return;
    await apiPut(`/summaries/${summaryId}`, { edited_text: text });
    alert("Saved");
  }

  async function publish(clusterId: number) {
    await apiPost(`/shortlist/cluster/${clusterId}/publish`);
    await load();
    setSelected(null);
    setSummaryId(null);
    setText("");
  }

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Shortlist</h1>
      {err && <p style={{ color: "crimson" }}>{err}</p>}
      <button onClick={load}>Refresh</button>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 12 }}>
        <div>
          <b>Items</b>
          {items.length === 0 ? <p>No shortlist items.</p> : (
            <ul>
              {items.map(c => (
                <li key={c.id} style={{ marginBottom: 12 }}>
                  <button onClick={async () => { setSelected(c); await loadSummary(c.id); }}>
                    Open
                  </button>{" "}
                  <span>{c.cluster_title}</span>
                  <PrimaryUrl cluster={c} />
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          {selected ? (
            <>
              <h3 style={{ marginTop: 0, marginBottom: 0 }}>{selected.cluster_title}</h3>
              <PrimaryUrl cluster={selected} />
              <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                <button onClick={() => generate(selected.id)}>Generate summary</button>
                <button onClick={save} disabled={!summaryId}>Save edits</button>
                <button onClick={() => publish(selected.id)}>Publish</button>
              </div>
              <SummaryEditor text={text} onChange={setText} />
            </>
          ) : (
            <p>Select an item to generate/edit summary.</p>
          )}
        </div>
      </div>
    </div>
  );
}
