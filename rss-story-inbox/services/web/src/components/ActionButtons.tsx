export default function ActionButtons({
  onKeep, onReject, onDefer, disabled = false
}: { onKeep: () => void; onReject: () => void; onDefer: () => void; disabled?: boolean }) {
  return (
    <div style={{ display: "flex", gap: 10 }}>
      <button onClick={onKeep} disabled={disabled}>Keep</button>
      <button onClick={onReject} disabled={disabled}>Reject</button>
      <button onClick={onDefer} disabled={disabled}>Defer</button>
    </div>
  );
}
