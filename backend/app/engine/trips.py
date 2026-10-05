"""Return-trip limits: two free follow-up requests per idea, a third needs a written reason, never a fourth."""
from __future__ import annotations


def check(existing: int, override: bool, reason: str, free: int = 2, max_with_override: int = 3) -> str | None:
    """Return None if a new request is allowed, else the plain sentence explaining why not."""
    n = existing + 1
    if n <= free:
        return None
    if n > max_with_override:
        return f"This idea has had {existing} follow-up requests, which is the most allowed."
    if not override or not (reason or "").strip():
        return (f"This would be request {n} for this idea. Tick the box and write a reason to send "
                f"more than {free}.")
    return None
