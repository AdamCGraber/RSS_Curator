import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../lib/api";
import { PublishedItem } from "../lib/types";

function formatReadableDate(value?: string) {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const formatOptions = { timeZone: "UTC" } as const;

  const weekday = new Intl.DateTimeFormat("en-US", { weekday: "long", ...formatOptions }).format(date);
  const month = new Intl.DateTimeFormat("en-US", { month: "long", ...formatOptions }).format(date);
  const day = new Intl.DateTimeFormat("en-US", { day: "numeric", ...formatOptions }).format(date);
  const year = new Intl.DateTimeFormat("en-US", { year: "numeric", ...formatOptions }).format(date);
  return `${weekday}, ${month}, ${day}, ${year}`;
}

function toSafeHttpUrl(value?: string) {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return null;
    }
    return parsed.toString();
  } catch (error) {
    return null;
  }
}

export default function PublishedPage() {
  const [items, setItems] = useState<PublishedItem[]>([]);
  const [err, setErr] = useState("");

  async function load() {
    setErr("");
    try {
      const publishedItems = await apiGet("/published");
      setItems([...publishedItems].sort((a, b) => (b.score ?? 0) - (a.score ?? 0)));
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  }

  useEffect(() => { load(); }, []);

  async function remove(clusterId: number) {
    await apiPost(`/published/cluster/${clusterId}/remove`);
    await load();
  }

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Published</h1>
      {err && <p style={{ color: "crimson" }}>{err}</p>}
      <button onClick={load}>Refresh</button>

      {items.length === 0 ? <p>No published items yet.</p> : (
        <div style={{ marginTop: 12 }}>
          {items.map(it => {
            const safeUrl = toSafeHttpUrl(it.url);
            return (
              <div key={it.cluster_id} style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12, marginBottom: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                  <h3 style={{ marginTop: 0, marginBottom: 0 }}>{it.title}</h3>
                  <button onClick={() => remove(it.cluster_id)}>Remove</button>
                </div>
                <div style={{ color: "#555", marginBottom: 8 }}>
                  Coverage: {it.coverage_count}
                </div>
                {safeUrl && (
                  <div style={{ marginBottom: 4, overflowWrap: "anywhere" }}>
                    <a href={safeUrl} target="_blank" rel="noopener noreferrer">
                      {safeUrl}
                    </a>{" "}
                    <span style={{ color: "#555" }}>— score {it.score.toFixed(1)}</span>
                  </div>
                )}
                <div style={{ color: "#555", fontSize: 14 }}>
                  {formatReadableDate(it.latest_published_at)}
                </div>
                <pre style={{ whiteSpace: "pre-wrap", marginTop: 10 }}>
                  {it.summary || "(No summary yet)"}
                </pre>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
