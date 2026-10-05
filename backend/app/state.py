"""The state machine: which steps are done, which is current, and the gates every mutating endpoint checks."""
from __future__ import annotations

from . import db
from .core import gate

STEPS = [(1, "Describe the ask", 0, True), (2, "Confirm the question", 0, True), (3, "Set the targets", 0, True),
         (4, "Plan the research", 1, True), (5, "Gathering evidence", 1, False), (6, "Checking the evidence", 1, False),
         (7, "Review the evidence", 1, True), (8, "Results", 2, False), (9, "Fill the gaps", 2, True),
         (10, "The answer", 2, False), (11, "What if...", 2, False), (12, "Your conclusion", 2, True)]
TITLES = {n: t for n, t, _, _ in STEPS}
PREREQ = {1: None, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6, 8: 7, 9: 8, 10: 8, 11: 10, 12: 10}


def done_map(case: dict) -> dict[int, bool]:
    cid, s = case["id"], case.get("settings_json") or {}
    frame = db.one("frame", cid)
    overall = db.one("overall", cid)
    concl = db.one("conclusion", cid)
    tested = bool(s.get("tests_run_at"))
    added = bool(overall) and not overall.get("stale")
    return {1: bool(frame), 2: bool(frame and frame.get("confirmed_at")), 3: bool(s.get("plan_locked_at")),
            4: bool(s.get("requests_marked_sent_at")), 5: bool(s.get("collect_finished_at")),
            6: bool(s.get("clean_finished_at")), 7: tested, 8: tested, 9: added, 10: added, 11: added,
            12: bool(added and concl and concl.get("saved_at"))}


def open_trip(cid: int) -> bool:
    return any(not t.get("retested_at") for t in db.rows("trip", cid))


def reopened(cid: int) -> list[str]:
    return [h["code"] for h in db.rows("hypothesis", cid) if h.get("links_reopened_for_trip")]


def progress(case: dict) -> dict:
    done = done_map(case)
    if done[10]:
        current = 12
    elif done[8]:
        current = 9 if open_trip(case["id"]) else 10
    else:
        current = next((n for n in range(1, 13) if not done[n]), 12)
    steps = []
    for n, title, phase, signoff in STEPS:
        pre = PREREQ[n]
        if done[n]:
            state, why = "done", ""
        elif pre is None or done[pre]:
            state, why = "open", ""
        else:
            state, why = "locked", f'Finish "{TITLES[pre]}" first'
        steps.append({"n": n, "title": title, "phase": phase, "signoff": signoff, "state": state,
                      "locked_reason": why, "current": n == current})
    return {"steps": steps, "current": current, "done": {str(k): v for k, v in done.items()},
            "reopened": reopened(case["id"])}


def require_step(case: dict, n: int) -> None:
    """Refuse with 409 unless step n is open (its prerequisite is done)."""
    done = done_map(case)
    pre = PREREQ[n]
    if pre is not None and not done[pre]:
        t = TITLES[pre]
        raise gate(f'Finish "{t}" first', [t])


def require_not_done(case: dict, n: int, reason: str) -> None:
    if done_map(case)[n]:
        raise gate(reason)
