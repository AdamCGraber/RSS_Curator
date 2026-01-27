def apply_action(current: str, action: str) -> str:
    action = action.lower().strip()
    if action == "keep":
        return "KEPT"
    if action == "reject":
        return "REJECTED"
    if action == "defer":
        return "DEFERRED"
    raise ValueError("Invalid action")

def promote_to_shortlist(current: str) -> str:
    if current != "KEPT":
        raise ValueError("Only KEPT can be promoted")
    return "SHORTLIST"

def mark_published(current: str) -> str:
    if current != "SHORTLIST":
        raise ValueError("Only SHORTLIST can be published")
    return "PUBLISHED"
