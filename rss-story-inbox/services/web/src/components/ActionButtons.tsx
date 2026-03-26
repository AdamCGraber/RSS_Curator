export default function ActionButtons({
  onKeep, onReject, onUndo, disabled = false, undoDisabled = false, articlesToReview
}: {
  onKeep: () => void;
  onReject: () => void;
  onUndo: () => void;
  disabled?: boolean;
  undoDisabled?: boolean;
  articlesToReview?: number | null;
}) {
  return (
    <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
      <button onClick={onKeep} disabled={disabled}>Keep</button>
      <button onClick={onReject} disabled={disabled}>Reject</button>
      <button onClick={onUndo} disabled={undoDisabled}>Undo</button>
      {articlesToReview !== null && articlesToReview !== undefined && (
        <span style={{ color: "#374151", marginLeft: 8 }}>
          Articles To Review: {articlesToReview}
        </span>
      )}
    </div>
  );
}
