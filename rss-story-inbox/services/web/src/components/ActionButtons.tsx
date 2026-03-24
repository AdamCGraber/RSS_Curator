export default function ActionButtons({
  onKeep, onReject, onUndo, disabled = false, undoDisabled = false
}: {
  onKeep: () => void;
  onReject: () => void;
  onUndo: () => void;
  disabled?: boolean;
  undoDisabled?: boolean;
}) {
  return (
    <div style={{ display: "flex", gap: 10 }}>
      <button onClick={onKeep} disabled={disabled}>Keep</button>
      <button onClick={onReject} disabled={disabled}>Reject</button>
      <button onClick={onUndo} disabled={undoDisabled}>Undo</button>
    </div>
  );
}
