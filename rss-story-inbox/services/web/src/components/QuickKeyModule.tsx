import { useEffect, useMemo, useRef, useState } from "react";

export type QueueAction = "keep" | "reject" | "undo";
type QuickKeyConfig = Record<QueueAction, string[]>;
type StoredQuickKeysRead = {
  quickKeys: QuickKeyConfig;
  hadConflicts: boolean;
};

const STORAGE_KEY = "queue.quickKeys.v1";
const MODIFIER_KEYS = new Set(["ctrl", "alt", "shift", "meta"]);
const ACTION_ORDER: QueueAction[] = ["keep", "reject", "undo"];

const DEFAULT_QUICK_KEYS: QuickKeyConfig = {
  keep: ["k"],
  reject: ["r"],
  undo: ["u"],
};

function normalizeKey(key: string): string {
  const lowered = key.toLowerCase();
  if (lowered === "control") return "ctrl";
  if (lowered === " ") return "space";
  if (lowered === "escape") return "esc";
  if (lowered === "arrowup") return "up";
  if (lowered === "arrowdown") return "down";
  if (lowered === "arrowleft") return "left";
  if (lowered === "arrowright") return "right";
  return lowered;
}

function formatKey(key: string): string {
  if (key.length === 1) return key.toUpperCase();
  if (key === "ctrl") return "Ctrl";
  if (key === "alt") return "Alt";
  if (key === "meta") return "Meta";
  if (key === "esc") return "Esc";
  if (key === "space") return "Space";
  return key.charAt(0).toUpperCase() + key.slice(1);
}

function comboToLabel(combo: string[]): string {
  return combo.map(formatKey).join(" + ");
}

function normalizeCombo(combo: string[]): string[] {
  const unique = Array.from(new Set(combo.map(normalizeKey)));
  return unique.sort((a, b) => {
    const modifierDelta = Number(MODIFIER_KEYS.has(b)) - Number(MODIFIER_KEYS.has(a));
    if (modifierDelta !== 0) return modifierDelta;
    return a.localeCompare(b);
  });
}

function sanitizeStoredQuickKeys(parsed: unknown): StoredQuickKeysRead {
  const parsedConfig = typeof parsed === "object" && parsed !== null ? parsed : {};
  const quickKeys = {} as QuickKeyConfig;
  const usedComboKeys = new Set<string>();
  let hadConflicts = false;

  for (const action of ACTION_ORDER) {
    const candidate = (parsedConfig as Record<string, unknown>)[action];
    const normalized = Array.isArray(candidate)
      ? normalizeCombo(candidate.filter((value): value is string => typeof value === "string")).slice(0, 3)
      : DEFAULT_QUICK_KEYS[action];
    const comboKey = normalized.join("+");
    const isConflict = normalized.length > 0 && usedComboKeys.has(comboKey);
    quickKeys[action] = isConflict ? [] : normalized;
    if (isConflict) {
      hadConflicts = true;
      continue;
    }
    usedComboKeys.add(comboKey);
  }

  return { quickKeys, hadConflicts };
}

function readStoredQuickKeys(): StoredQuickKeysRead {
  if (typeof window === "undefined") return { quickKeys: DEFAULT_QUICK_KEYS, hadConflicts: false };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { quickKeys: DEFAULT_QUICK_KEYS, hadConflicts: false };
    const parsed = JSON.parse(raw);
    return sanitizeStoredQuickKeys(parsed);
  } catch {
    return { quickKeys: DEFAULT_QUICK_KEYS, hadConflicts: false };
  }
}

function isTypingTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName;
  if (el.isContentEditable) return true;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
}

function getConflictingAction(
  quickKeys: QuickKeyConfig,
  action: QueueAction,
  combo: string[]
): QueueAction | null {
  const comboKey = combo.join("+");
  const actions = Object.keys(quickKeys) as QueueAction[];
  for (const candidate of actions) {
    if (candidate === action) continue;
    if (quickKeys[candidate].join("+") === comboKey) {
      return candidate;
    }
  }
  return null;
}

export default function QuickKeyModule({
  onAction,
  disabled,
  captureEnabled = true,
}: {
  onAction: (action: QueueAction) => void;
  disabled: boolean;
  captureEnabled?: boolean;
}) {
  const [quickKeys, setQuickKeys] = useState<QuickKeyConfig>(DEFAULT_QUICK_KEYS);
  const [captureAction, setCaptureAction] = useState<QueueAction | null>(null);
  const [capturePreview, setCapturePreview] = useState<string[]>([]);
  const [captureError, setCaptureError] = useState<string>("");
  const [captureWarning, setCaptureWarning] = useState<string>("");
  const [storedConflictWarning, setStoredConflictWarning] = useState<string>("");

  const pressedRef = useRef<Set<string>>(new Set());
  const capturePressedRef = useRef<Set<string>>(new Set());
  const captureCandidateRef = useRef<string[]>([]);
  const actionLockRef = useRef<boolean>(false);

  useEffect(() => {
    const { quickKeys: storedQuickKeys, hadConflicts } = readStoredQuickKeys();
    setQuickKeys(storedQuickKeys);
    if (hadConflicts) {
      setStoredConflictWarning("Some conflicting saved shortcuts were unassigned.");
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(quickKeys));
    } catch {
      // ignore localStorage write failures (private mode, blocked storage, quota, etc.)
    }
  }, [quickKeys]);

  useEffect(() => {
    if (!disabled) return;
    pressedRef.current.clear();
    actionLockRef.current = false;
  }, [disabled]);

  useEffect(() => {
    if (captureEnabled) return;
    capturePressedRef.current.clear();
    captureCandidateRef.current = [];
    setCapturePreview([]);
    setCaptureError("");
    setCaptureWarning("");
    setCaptureAction(null);
  }, [captureEnabled]);

  function handleResetDefaults() {
    setQuickKeys(DEFAULT_QUICK_KEYS);
    setCaptureError("");
    setCaptureWarning("");
  }

  function handleClearAction(action: QueueAction) {
    setQuickKeys((prev) => ({
      ...prev,
      [action]: [],
    }));
    setCaptureError("");
    setCaptureWarning("");

    if (captureAction === action) {
      capturePressedRef.current.clear();
      captureCandidateRef.current = [];
      setCapturePreview([]);
      setCaptureAction(null);
    }
  }

  const actionByComboKey = useMemo(() => {
    const map = new Map<string, QueueAction>();
    (Object.keys(quickKeys) as QueueAction[]).forEach((action) => {
      const combo = quickKeys[action];
      if (!combo.length) return;

      const comboKey = combo.join("+");
      if (!map.has(comboKey)) {
        map.set(comboKey, action);
      }
    });
    return map;
  }, [quickKeys]);

  useEffect(() => {
    const resetCaptureState = () => {
      capturePressedRef.current.clear();
      captureCandidateRef.current = [];
      setCapturePreview([]);
      setCaptureWarning("");
      setCaptureAction(null);
    };

    const resetShortcutState = () => {
      pressedRef.current.clear();
      actionLockRef.current = false;
      resetCaptureState();
    };

    const onKeyDown = (event: KeyboardEvent) => {
      const key = normalizeKey(event.key);

      if (captureEnabled && captureAction) {
        if (key === "esc") {
          resetCaptureState();
          setCaptureError("");
          return;
        }

        capturePressedRef.current.add(key);
        if (capturePressedRef.current.size > 3) {
          setCaptureWarning("Only up to 3 keys are supported; extra keys are ignored.");
        } else {
          setCaptureWarning("");
        }
        const combo = normalizeCombo(Array.from(capturePressedRef.current)).slice(0, 3);
        captureCandidateRef.current = combo;
        setCapturePreview(combo);
        event.preventDefault();
        return;
      }

      if (disabled) {
        return;
      }

      if (isTypingTarget(event.target)) return;

      pressedRef.current.add(key);
      if (actionLockRef.current) {
        event.preventDefault();
        return;
      }

      const combo = normalizeCombo(Array.from(pressedRef.current));
      const action = actionByComboKey.get(combo.join("+"));
      if (!action) return;

      event.preventDefault();
      actionLockRef.current = true;
      onAction(action);
    };

    const onKeyUp = (event: KeyboardEvent) => {
      const key = normalizeKey(event.key);

      if (captureEnabled && captureAction) {
        capturePressedRef.current.delete(key);
        if (capturePressedRef.current.size <= 3) {
          setCaptureWarning("");
        }
        if (capturePressedRef.current.size === 0) {
          if (captureCandidateRef.current.length > 0) {
            const conflict = getConflictingAction(quickKeys, captureAction, captureCandidateRef.current);
            if (conflict) {
              setCaptureError(
                `Cannot assign ${comboToLabel(captureCandidateRef.current)} to ${captureAction}: already used by ${conflict}.`
              );
            } else {
              setQuickKeys((prev) => ({
                ...prev,
                [captureAction]: captureCandidateRef.current,
              }));
              setCaptureError("");
            }
          }
          setCapturePreview([]);
          captureCandidateRef.current = [];
          setCaptureAction(null);
        }
        return;
      }

      pressedRef.current.delete(key);
      if (pressedRef.current.size === 0) {
        actionLockRef.current = false;
      }
    };

    const onWindowBlur = () => {
      resetShortcutState();
    };

    const onVisibilityChange = () => {
      if (document.visibilityState !== "visible") {
        resetShortcutState();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    window.addEventListener("blur", onWindowBlur);
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      window.removeEventListener("blur", onWindowBlur);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [actionByComboKey, captureAction, captureEnabled, disabled, onAction, quickKeys]);

  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12, marginBottom: 12 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <b>Quick keys</b>
        <button onClick={handleResetDefaults} type="button">
          Reset defaults
        </button>
      </div>
      <p style={{ margin: "8px 0 10px", color: "#555" }}>
        Assign 1–3 keys per action. Press keys together when recording.
      </p>
      {storedConflictWarning && <p style={{ margin: "0 0 10px", color: "#8a6d3b" }}>{storedConflictWarning}</p>}
      {captureWarning && <p style={{ margin: "0 0 10px", color: "#8a6d3b" }}>{captureWarning}</p>}
      {captureError && <p style={{ margin: "0 0 10px", color: "crimson" }}>{captureError}</p>}
      {(Object.keys(quickKeys) as QueueAction[]).map((action) => {
        const isCapturing = captureAction === action;
        const shownCombo = isCapturing && capturePreview.length > 0 ? capturePreview : quickKeys[action];
        return (
          <div key={action} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
            <span style={{ width: 70, textTransform: "capitalize" }}>{action}</span>
            <code style={{ minWidth: 140 }}>{shownCombo.length ? comboToLabel(shownCombo) : "Unassigned"}</code>
            <button
              type="button"
              onClick={() => {
                capturePressedRef.current.clear();
                captureCandidateRef.current = [];
                setCapturePreview([]);
                setCaptureError("");
                setCaptureWarning("");
                setCaptureAction(isCapturing ? null : action);
              }}
            >
              {isCapturing ? "Cancel" : "Set"}
            </button>
            <button
              type="button"
              onClick={() => handleClearAction(action)}
              disabled={quickKeys[action].length === 0}
            >
              Clear
            </button>
          </div>
        );
      })}
    </div>
  );
}
