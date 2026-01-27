import { useMemo } from "react";

export default function SummaryEditor({
  text, onChange
}: { text: string; onChange: (t: string) => void }) {

  const words = useMemo(() => (text.trim() ? text.trim().split(/\s+/).length : 0), [text]);

  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <b>Summary</b>
        <span style={{ color: words > 300 ? "crimson" : "#666" }}>
          {words} words
        </span>
      </div>
      <textarea
        value={text}
        onChange={(e) => onChange(e.target.value)}
        style={{ width: "100%", minHeight: 220, marginTop: 8 }}
      />
    </div>
  );
}
