export default function ActionButtons({
  onKeep, onReject, disabled = false
}: { onKeep: () => void; onReject: () => void; disabled?: boolean }) {
  return (
    <div style={{ display: "flex", gap: 10 }}>
      <button onClick={onKeep} disabled={disabled}>Keep</button>
      <button onClick={onReject} disabled={disabled}>Reject</button>
    </div>
  );
}
