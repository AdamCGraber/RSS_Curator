import { useEffect, useState } from "react";
import { apiGet, apiPost, apiPut, apiPostFile } from "../lib/api";
import { Profile } from "../lib/types";

export default function ProfilePage() {
  const [p, setP] = useState<Profile | null>(null);
  const [name, setName] = useState("Example Feed");
  const [url, setUrl] = useState("");
  const [sources, setSources] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const [opmlFile, setOpmlFile] = useState<File | null>(null);
  const [opmlStatus, setOpmlStatus] = useState<string>("");
  const [opmlReport, setOpmlReport] = useState<any | null>(null);
  const [isImporting, setIsImporting] = useState<boolean>(false);

  function downloadJson(filename: string, data: any) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

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

  async function uploadOpml() {
    if (!opmlFile) return;

    setIsImporting(true);
    setOpmlStatus("Importing OPML…");
    setOpmlReport(null);

    try {
      const fd = new FormData();
      fd.append("file", opmlFile);

      const result = await apiPostFile("/admin/sources/import-opml", fd);
      setOpmlReport(result);

      setOpmlStatus(
        `Done. Found ${result.total_found}, added ${result.added}, skipped ${result.skipped}.`
          + (result.errors?.length ? ` Errors: ${result.errors.join(" | ")}` : "")
      );

      setOpmlFile(null);
      await load();
    } catch (e: any) {
      setOpmlStatus(`Import failed: ${e.message || String(e)}`);
    } finally {
      setIsImporting(false);
    }
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

          <hr style={{ margin: "18px 0" }} />

          <h3>Bulk import (OPML)</h3>
          <p style={{ color: "#555" }}>
            Upload an OPML export (e.g., Feedly). We’ll import each RSS <code>xmlUrl</code> and keep the OPML feed
            title as the Source name.
          </p>

          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input
              type="file"
              accept=".opml,.xml,text/xml,application/xml"
              disabled={isImporting}
              onChange={(e) => setOpmlFile(e.target.files?.[0] || null)}
            />
            <button onClick={uploadOpml} disabled={!opmlFile || isImporting}>
              {isImporting ? "Importing…" : "Import OPML"}
            </button>
            {opmlReport && (
              <button
                onClick={() =>
                  downloadJson(
                    `opml-import-report-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.json`,
                    opmlReport
                  )
                }
              >
                Download report (JSON)
              </button>
            )}
          </div>

          {opmlStatus && <p style={{ marginTop: 8 }}>{opmlStatus}</p>}
          {opmlReport?.skipped_items?.length ? (
            <details style={{ marginTop: 10 }}>
              <summary>Skipped duplicates ({opmlReport.skipped_items.length})</summary>
              <ul>
                {opmlReport.skipped_items.slice(0, 50).map((f: any, idx: number) => (
                  <li key={idx}>
                    <b>{f.name}</b> — {f.feed_url}
                    {f.category ? <span style={{ color: "#666" }}> (Folder: {f.category})</span> : null}
                  </li>
                ))}
              </ul>
              {opmlReport.skipped_items.length > 50 ? (
                <p style={{ color: "#666" }}>Showing first 50. Download the report for the full list.</p>
              ) : null}
            </details>
          ) : null}

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
