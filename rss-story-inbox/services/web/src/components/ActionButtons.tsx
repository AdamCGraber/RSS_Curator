export default function ActionButtons({
  onKeep, onReject, onDefer
}: { onKeep: () => void; onReject: () => void; onDefer: () => void }) {
  return (
    <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
      <button onClick={onKeep}>Keep</button>
      <button onClick={onReject}>Reject</button>
      <button onClick={onDefer}>Defer</button>
    </div>
  );
}
