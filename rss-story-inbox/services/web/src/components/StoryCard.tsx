import { Cluster } from "../lib/types";

export default function StoryCard({ c }: { c: Cluster }) {
  return (
    <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
        <h3 style={{ margin: 0 }}>{c.cluster_title}</h3>
        <div style={{ textAlign: "right", minWidth: 180 }}>
          <div><b>Coverage:</b> {c.coverage_count}</div>
          <div><b>Score:</b> {c.score.toFixed(1)}</div>
        </div>
      </div>
      <p style={{ marginTop: 8, color: "#444" }}>{c.why}</p>

      {c.canonical && (
        <p style={{ marginTop: 8 }}>
          <b>Canonical:</b>{" "}
          <a href={c.canonical.url} target="_blank">{c.canonical.title}</a>{" "}
          <span style={{ color: "#666" }}>— {c.canonical.source_name}</span>
        </p>
      )}

      <div style={{ marginTop: 8 }}>
        <b>More coverage</b>
        <ul>
          {c.coverage.slice(0, 10).map(a => (
            <li key={a.id}>
              <a href={a.url} target="_blank">{a.title}</a>{" "}
              <span style={{ color: "#666" }}>— {a.source_name}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
