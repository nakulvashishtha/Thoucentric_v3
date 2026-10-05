"""GET /api/cases/{id}: the one object the front end draws every screen from (shape: prompts/04_CASE_BUNDLE_SCHEMA.md)."""
from __future__ import annotations

from . import budget, config, db, evidence, modes, samples
from .core import latest_jobs
from .engine.credibility import TIER_LABELS
from .state import progress
from .steps_decide import review_counts, sliders


def _job(j: dict) -> dict:
    return {k: j.get(k) for k in ("id", "kind", "status", "error", "progress", "started_at", "finished_at")}


def present(e: dict, copies: dict[str, list[str]]) -> dict:
    out = dict(e)
    cj = e.get("credibility_json") or {}
    tier = cj.get("tier")
    st = e["status"]
    out["status_label"] = f"Duplicate of {e['duplicate_of']}" if st == "duplicate" else evidence.STATUS_LABELS.get(st, st)
    out["tier"] = tier
    out["tier_label"] = "" if st == "pending" else (TIER_LABELS.get(tier, "Your call") if tier else "Your call")
    out["date"] = e.get("data_as_of") or e.get("published_date") or ""
    out["claim"] = evidence.claim_of(e)
    out["copies"] = copies.get(e["id"], [])
    out.setdefault("formula_needs_you", False)
    return out


def counts(items: list[dict]) -> dict:
    coll = [e for e in items if e["origin_type"] != "benchmark" and e["status"] != "pending" and not e.get("trip_id")]
    by = {k: 0 for k in ("open_web", "firm_archive", "paid_db", "client_file", "expert_note")}
    for e in coll:
        by[e["origin_type"]] = by.get(e["origin_type"], 0) + 1
    dups = sum(1 for e in coll if e["status"] == "duplicate")
    return {"collected": len(coll), "unique": len(coll) - dups, "duplicates": dups,
            "auto_approved": sum(1 for e in items if e["status"] == "auto_approved"),
            "decided_by_person": sum(1 for e in items if e.get("decided_by") == "consultant"),
            "rejected": sum(1 for e in items if e["status"] == "rejected"),
            "pending": sum(1 for e in items if e["status"] == "pending"),
            "unreadable": sum(1 for e in items if e["status"] == "unreadable"),
            "benchmarks": sum(1 for e in items if e["origin_type"] == "benchmark"), "by_origin": by}


def duplicate_groups(items: list[dict]) -> list[dict]:
    byid = {e["id"]: e for e in items}
    groups: dict[str, list[dict]] = {}
    for e in items:
        if e["status"] == "duplicate" and e.get("duplicate_of"):
            groups.setdefault(e["duplicate_of"], []).append(e)
    out = []
    for oid, cs in groups.items():
        cs.sort(key=lambda x: x["seq"])
        o = byid.get(oid, {})
        out.append({"original": oid, "copies": [c["id"] for c in cs], "original_title": o.get("title", ""),
                    "rule": cs[0].get("duplicate_rule", "")})
    out.sort(key=lambda g: int(g["copies"][0][1:]))
    return out


def build(case: dict) -> dict:
    cid = case["id"]
    items = evidence.all_items(cid)
    copies: dict[str, list[str]] = {}
    for e in items:
        if e["status"] == "duplicate" and e.get("duplicate_of"):
            copies.setdefault(e["duplicate_of"], []).append(e["id"])
    jobs = latest_jobs(cid)
    hyps = sorted(db.rows("hypothesis", cid), key=lambda h: h["order"])
    files = [{k: f.get(k) for k in ("id", "filename", "kind", "uploaded_at", "figures", "trip_id")} | {"preview": f.get("preview", "")}
             for f in db.rows("client_file", cid)]
    case_out = {k: case.get(k) for k in ("updated_at", "client_name", "private_numbers", "function", "mode", "sample",
                                         "current_step", "created_at", "id", "title", "client_aliases", "country",
                                         "industry", "raw_ask", "status", "settings_json")}
    r = config.rules()
    rules = {"thresholds": {k: v for k, v in r.items()}, "adding_up_rule": r["adding_up_rule"]}
    rs = db.one("ruleset", cid)
    trips = [{k: v for k, v in t.items() if k != "pk"} for t in sorted(db.rows("trip", cid), key=lambda t: t["id"])]
    p = samples.pack(case["sample"]) if case.get("sample") else {}
    return {
        "case": case_out,
        "mode": modes.case_mode(case),
        "frame": db.one("frame", cid),
        "ruleset": rs,
        "hypotheses": hyps,
        "needs": db.rows("need", cid),
        "files": files,
        "plan": db.rows("plan_item", cid),
        "evidence": [present(e, copies) for e in items],
        "duplicate_groups": duplicate_groups(items),
        "calcs": db.rows("calc", cid),
        "trips": trips,
        "overall": _overall(cid),
        "summary": _summary(cid),
        "conclusion": db.one("conclusion", cid),
        "progress": progress(case),
        "review": review_counts(case),
        "counts": counts(items),
        "jobs": {k: _job(j) for k, j in jobs.items()},
        "running_jobs": [k for k, j in jobs.items() if j["status"] in ("running", "queued")],
        "sliders": sliders(case),
        "sample_replies": dict((p.get("case") or {}).get("replies") or {}),
        "rules": rules,
        "spend": budget.spend(cid),
    }


def _overall(cid: int) -> dict | None:
    o = db.one("overall", cid)
    return o if o and not o.get("stale") else None


def _summary(cid: int) -> dict | None:
    s = db.one("summary", cid)
    if s:
        s = dict(s)
        s.pop("id", None)
    return s
