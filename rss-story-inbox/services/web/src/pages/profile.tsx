import { useEffect, useState } from "react";
import { apiGet, apiPost, apiPut } from "../lib/api";
import { Profile } from "../lib/types";

export default function ProfilePage() {
  const [p, setP] = useState<Profile | null>(null);
  const [name, setName] = useState("Example Feed");
  const [url, setUrl] = useState("");
  const [sources, setSources] = useState<any[]>([]);
  const [err, setErr] = useState("");

  async function load() {
    setErr("");
    try {
      const prof = await apiGet("/profile");
      setP(prof);
      setSources(await apiGet("/sources"));
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  }

  useEffect(() => { load(); }, []);

  async function saveProfile() {
    if (!p) return;
    const updated = await apiPut("/profile", {
      audience_text: p.audience_text,
      tone_text: p.tone_text,
      include_terms: p.include_terms,
      exclude_terms: p.exclude_terms
    });
    setP(updated);
    alert("Saved profile");
  }

  async function addSource() {
    if (!url.trim()) return;
    await apiPost("/sources", { name, feed_url: url });
    setUrl("");
    await load();
  }

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Profile</h1>
      {err && <p style={{ color: "crimson" }}>{err}</p>}
      {!p ? <p>Loading...</p> : (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <b>Audience</b>
              <textarea
                value={p.audience_text}
                onChange={(e) => setP({ ...p, audience_text: e.target.value })}
                style={{ width: "100%", minHeight: 80 }}
              />
            </div>
            <div>
              <b>Tone</b>
              <textarea
                value={p.tone_text}
                onChange={(e) => setP({ ...p, tone_text: e.target.value })}
                style={{ width: "100%", minHeight: 80 }}
              />
            </div>
            <div>
              <b>Include terms (comma-separated)</b>
              <input
                value={p.include_terms}
                onChange={(e) => setP({ ...p, include_terms: e.target.value })}
                style={{ width: "100%" }}
              />
            </div>
            <div>
              <b>Exclude terms (comma-separated)</b>
              <input
                value={p.exclude_terms}
                onChange={(e) => setP({ ...p, exclude_terms: e.target.value })}
                style={{ width: "100%" }}
              />
            </div>
          </div>
          <button onClick={saveProfile} style={{ marginTop: 10 }}>Save Profile</button>

          <hr style={{ margin: "18px 0" }} />

          <h3>Add RSS Source</h3>
          <div style={{ display: "flex", gap: 8 }}>
            <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
            <input placeholder="Feed URL" style={{ flex: 1 }} value={url} onChange={(e) => setUrl(e.target.value)} />
            <button onClick={addSource}>Add</button>
          </div>

          <h3 style={{ marginTop: 16 }}>Sources</h3>
          <ul>
            {sources.map(s => (
              <li key={s.id}>
                <b>{s.name}</b> — {s.feed_url}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
