"""Evidence items: creation, figure checking, grading, links, derivations, the quality check and the verdict inputs.
Everything here is plain code; the language model's proposals arrive as data and are checked before use."""
from __future__ import annotations

from datetime import datetime, timezone

from . import config, db
from .core import now_iso
from .engine import checklist as checklist_mod
from .engine import credibility, privacy
from .engine.convert import convert, derive, unit_key
from .engine.dedup import text_hash
from .engine.numbers import fig_text, fmt
from .files import parse

STATUS_LABELS = {"auto_approved": "Passed the quality check", "approved": "Accepted by you",
                 "needs_decision": "Needs your call", "client_reported": "From the client",
                 "belief_under_test": "Client's claim", "cross_check": "Sense check only", "rejected": "Rejected",
                 "pending": "Waiting", "pending_clean": "Not checked yet", "pass_line_source": "Target source",
                 "unreadable": "Could not read"}
DECISIONS = {"approve": "approved", "keep_client_reported": "client_reported", "keep_belief": "belief_under_test",
             "keep_cross_check": "cross_check", "reject": "rejected"}
COUNTED = ("approved", "auto_approved", "client_reported")


def next_seq(cid: int) -> int:
    return max([e["seq"] for e in db.rows("evidence", cid)] or [0]) + 1


def next_link_id() -> int:
    with db.lock():
        n = int(db.kv_get("link_seq", 0)) + 1
        db.kv_put("link_seq", n)
        return n


def create(cid: int, origin_type: str, **f) -> dict:
    with db.lock():
        seq = next_seq(cid)
        item = {"need_ref": "", "published_date": "", "duplicate_rule": "", "decided_by": "", "origin_type": origin_type,
                "data_as_of": "", "credibility_json": {}, "decision_reason": "", "found_in": "", "retrieved_at": now_iso(),
                "checklist_json": [], "seen_by_consultant": False, "source_name": "", "text": "", "figures_json": [],
                "spot_check_selected": False, "title": "", "text_hash": "", "spot_check_result": "", "script_tag": "",
                "id": f"E{seq}", "url": "", "simulated": False, "status": "pending_clean", "trip_id": None, "seq": seq,
                "domain": "", "original_group_id": "", "bucket": "", "file_id": None, "seed_id": "", "publisher": "",
                "duplicate_of": None, "links": [], "formula_needs_you": False}
        item.update(f)
        if item["text"] and not item["text_hash"] and origin_type != "benchmark":
            item["text_hash"] = text_hash(item["text"])
        if item["url"] and not item["domain"]:
            item["domain"] = credibility.domain_of(item["url"])
        return db.insert("evidence", cid, item)


def all_items(cid: int) -> list[dict]:
    return sorted(db.rows("evidence", cid), key=lambda e: e["seq"])


def get(cid: int, eid: str) -> dict | None:
    for e in db.rows("evidence", cid):
        if e["id"] == eid:
            return e
    return None


def save(e: dict) -> None:
    db.put("evidence", e)


# ------------------------------------------------------------------ figures
def clean_figures(raw: list[dict], text: str, web: bool) -> list[dict]:
    """Keep the model's figures, normalised, and check each quote word for word at its stated place."""
    segs = parse.segments(text, web=web)
    out = []
    for f in raw or []:
        fig = {"value": _num(f.get("value")), "low": _num(f.get("low")), "high": _num(f.get("high")),
               "unit": str(f.get("unit") or "").strip(), "period": str(f.get("period") or "").strip(),
               "quote_span": str(f.get("quote_span") or "").strip(), "locator": str(f.get("locator") or "").strip(),
               "kind": "reported"}
        if fig["value"] is None and fig["low"] is None:
            continue
        if fig["value"] is not None:
            fig["low"] = fig["high"] = None
        elif fig["high"] is None:
            fig["high"] = fig["low"]
        ok, note = parse.verify(fig, segs)
        fig["verified"], fig["verify_note"] = ok, note
        out.append(fig)
    return out


def _num(v):
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def lo_hi(fig: dict) -> tuple[float, float]:
    if fig.get("value") is not None:
        return float(fig["value"]), float(fig["value"])
    return float(fig["low"]), float(fig["high"] if fig.get("high") is not None else fig["low"])


def claim_of(e: dict) -> str:
    for f in e.get("figures_json") or []:
        if f.get("kind") == "reported":
            lo, hi = lo_hi(f)
            t = fig_text(lo, hi, f.get("unit", ""))
            return f"{t} ({f['period']})" if f.get("period") else t
    return e.get("title") or ""


# ------------------------------------------------------------------ grading
def recency_window(e: dict, hyps: dict, thresholds: dict) -> int:
    rm = thresholds.get("recency_months") or {}
    code = None
    for lk in e.get("links") or []:
        code = lk["hypothesis_code"]
        break
    if code is None and e.get("need_ref"):
        n = next((x for x in db.rows("need", e["case_id"]) if x["ref"] == e["need_ref"]), None)
        code = n and n["hypothesis_code"]
    cat = (hyps.get(code) or {}).get("recency_category") or "size_growth_price"
    return int(rm.get(cat, 36))


def grade_tier(e: dict, case: dict, plan: list[dict]) -> None:
    t, why = credibility.tier_for(e.get("domain", ""), e["origin_type"] if e["origin_type"] != "benchmark" else
                                  (e.get("found_in") or "open_web"), config.registry(), case.get("country", ""),
                                  case.get("industry", ""), plan)
    cj = dict(e.get("credibility_json") or {})
    cj.update(tier=t, tier_reason=why)
    cj.setdefault("method_cited", False)
    cj.setdefault("original_source_name", "")
    cj.setdefault("traced", False)
    e["credibility_json"] = cj


def apply_describe(e: dict, describe: dict) -> None:
    d = {"author_type": str(describe.get("author_type") or ""), "method_cited": bool(describe.get("method_cited")),
         "original_source_named": bool(describe.get("original_source_named")),
         "original_source_name": str(describe.get("original_source_name") or ""),
         "published_date": str(describe.get("published_date") or e.get("published_date") or ""),
         "data_as_of": str(describe.get("data_as_of") or e.get("data_as_of") or "")}
    cj = dict(e.get("credibility_json") or {})
    cj["describe"] = d
    e["credibility_json"] = cj
    if not e.get("published_date") and d["published_date"]:
        e["published_date"] = d["published_date"]
    if not e.get("data_as_of") and d["data_as_of"]:
        e["data_as_of"] = d["data_as_of"]


def grade_full(e: dict, case: dict, plan: list[dict], hyps: dict, thresholds: dict, belief: str,
               now: datetime | None = None) -> None:
    grade_tier(e, case, plan)
    cj = e["credibility_json"]
    d = cj.get("describe") or {}
    cj["method_cited"] = bool(d.get("method_cited"))
    cj["original_source_name"] = d.get("original_source_name") or ""
    cj["traced"] = credibility.traced(d, cj.get("tier"))
    cj.update(credibility.recency(e.get("data_as_of", ""), e.get("published_date", ""),
                                  recency_window(e, hyps, thresholds), now or datetime.now(timezone.utc)))
    cj["matches_belief"] = matches_belief(e, belief)


def matches_belief(e: dict, belief: str) -> bool:
    if e["origin_type"] != "client_file" or not belief:
        return False
    nums = parse.numbers_in(belief)
    pct_belief = "%" in belief or "percent" in belief.lower()
    for f in e.get("figures_json") or []:
        if f.get("kind") != "reported" or not f.get("verified"):
            continue
        lo, hi = lo_hi(f)
        is_pct = unit_key(f.get("unit", ""))["base"] == "%"
        if is_pct == pct_belief and any(abs(lo - n) < 1e-9 or abs(hi - n) < 1e-9 for n in nums):
            return True
    return False


# ------------------------------------------------------------------ links and derivations
def apply_links(e: dict, proposal: dict, hyps: dict, default_idea: str | None) -> list[str]:
    """Store the model's proposed links (checked) and compute any derivation it proposed. Returns formula texts."""
    formulas = []
    figs = [f for f in e.get("figures_json") or [] if f.get("kind") == "reported"]
    e["figures_json"] = figs
    for d in proposal.get("derivations") or []:
        try:
            a = _ref(e, d.get("a_ref"))
            b = _ref(e, d.get("b_ref"))
            if a is None or b is None or not a[1].get("verified") or not b[1].get("verified"):
                continue
            calc = derive(str(d.get("op")), a[1], b[1], d.get("years"), str(d.get("result_unit") or ""))
        except (ValueError, TypeError, ZeroDivisionError):
            continue
        same_item = a[0] == e["id"] and b[0] == e["id"]
        refs = [a[2], b[2]] if same_item else [f"{a[0]}:{a[2]}", f"{b[0]}:{b[2]}"]
        period = _span_period(a[1].get("period", ""), b[1].get("period", ""))
        fig = {"value": calc["value"], "unit": calc["unit"], "period": period, "kind": "calculated", "quote_span": "",
               "locator": "", "verified": True, "verify_note": "recomputed from its stored inputs",
               "derivation": {"op": calc["inputs"]["op"], "input_figure_refs": refs, "years": calc["inputs"]["years"],
                              "result_unit": calc["unit"], "rationale": str(d.get("rationale") or ""),
                              "formula": calc["formula"], "unit_ok": calc["unit_ok"], "years_ok": calc["years_ok"],
                              "note": calc["note"], "formula_confirmed": False}}
        e["figures_json"].append(fig)
        if not same_item or not calc["unit_ok"] or not calc["years_ok"]:
            e["formula_needs_you"] = True
        db.insert("calc", e["case_id"], {"formula_text": calc["formula"], "result_value": calc["value"], "run_at": now_iso(),
                                         "inputs_json": calc["inputs"], "evidence_ids": [e["id"]], "unit": calc["unit"],
                                         "kind": "derivation"})
        formulas.append(calc["formula"])
    links = []
    for lk in proposal.get("links") or []:
        code = lk.get("idea")
        idx = lk.get("figure_index", 0)
        if code not in hyps or hyps[code].get("removed_reason"):
            continue
        if not isinstance(idx, int) or not (0 <= idx < len(e["figures_json"])):
            continue
        role = lk.get("role") if lk.get("role") in ("supports_test", "context") else "context"
        fig = e["figures_json"][idx]
        if role == "supports_test" and fig.get("kind") != "calculated":
            v, note = convert(lo_hi(fig)[0], fig.get("unit", ""), hyps[code]["measure_unit"])
            if v is None:
                role = "context"                      # an unconvertible figure never counts
        links.append(_link(e, code, idx, role, "llm"))
    if not links and default_idea and e["figures_json"]:
        links.append(_link(e, default_idea, 0, "supports_test", "rule_engine"))
    e["links"] = links
    return formulas


def _link(e: dict, code: str, idx: int, role: str, by: str) -> dict:
    return {"id": next_link_id(), "hypothesis_code": code, "figure_index": idx, "confirmed": False,
            "case_id": e["case_id"], "evidence_id": e["id"], "role": role, "proposed_by": by}


def _ref(e: dict, ref):
    """A figure reference: an index into this item's figures, or 'E7:1' for another item's figure."""
    if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
        i = int(ref)
        figs = e["figures_json"]
        return (e["id"], figs[i], i) if 0 <= i < len(figs) else None
    if isinstance(ref, str) and ":" in ref:
        eid, i = ref.split(":", 1)
        other = get(e["case_id"], eid)
        if other and i.isdigit() and int(i) < len(other["figures_json"]):
            return (eid, other["figures_json"][int(i)], int(i))
    return None


def _span_period(a: str, b: str) -> str:
    if a and b and a != b:
        return f"{a} to {b}"
    return a or b


# ------------------------------------------------------------------ quality check
def figure_for_link(e: dict, lk: dict) -> dict | None:
    figs = e.get("figures_json") or []
    i = lk.get("figure_index", 0)
    return figs[i] if 0 <= i < len(figs) else None


def corroborated(e: dict, items: list[dict], hyps: dict) -> bool:
    lk = checklist_mod.main_link(e)
    if not lk:
        return False
    h = hyps.get(lk["hypothesis_code"])
    f = figure_for_link(e, lk)
    if not h or not f:
        return False
    mine = convert(lo_hi(f)[0], f.get("unit", ""), h["measure_unit"])[0]
    if mine is None:
        return False
    for o in items:
        if o is e or o.get("duplicate_of") or (o.get("original_group_id") or o["id"]) == (e.get("original_group_id") or e["id"]):
            continue
        for ol in o.get("links") or []:
            if ol["hypothesis_code"] != h["code"]:
                continue
            of = figure_for_link(o, ol)
            if not of or not of.get("verified"):
                continue
            ov = convert(lo_hi(of)[0], of.get("unit", ""), h["measure_unit"])[0]
            if ov is not None and abs(ov - mine) <= abs(mine) * float(h.get("tolerance_pct") or 5) / 100.0:
                return True
    return False


def run_checklist(e: dict, items: list[dict], hyps: dict, thresholds: dict, case: dict, files: list[dict]) -> bool:
    lk = checklist_mod.main_link(e)
    idea = hyps.get(lk["hypothesis_code"]) if lk else None
    private = [] if e["origin_type"] in ("client_file", "expert_note") else privacy.find_private(e.get("text", ""), case, files)
    tests = checklist_mod.run(e, lk, idea, hyps, corroborated(e, items, hyps), thresholds, private)
    e["checklist_json"] = tests
    return checklist_mod.passes(tests)


# ------------------------------------------------------------------ verdict inputs
def eligible_figures(cid: int, h: dict, items: list[dict] | None = None) -> list[dict]:
    items = items if items is not None else all_items(cid)
    out = []
    for e in items:
        if e.get("duplicate_of") or e["status"] not in COUNTED:
            continue
        if (e.get("credibility_json") or {}).get("matches_belief"):
            continue                                   # the client's belief is a claim to test, never evidence
        for lk in e.get("links") or []:
            if lk["hypothesis_code"] != h["code"] or lk["role"] != "supports_test":
                continue
            f = figure_for_link(e, lk)
            if not f or not f.get("verified"):
                continue
            if f.get("kind") == "calculated" and not (f.get("derivation") or {}).get("formula_confirmed"):
                continue
            lo, hi = lo_hi(f)
            clo, n1 = convert(lo, f.get("unit", ""), h["measure_unit"])
            chi, _ = convert(hi, f.get("unit", ""), h["measure_unit"])
            if clo is None or chi is None:
                continue
            out.append({"evidence_id": e["id"], "low": clo, "high": chi, "origin": e.get("original_group_id") or e["id"],
                        "client_reported": e["status"] == "client_reported", "calculated": f.get("kind") == "calculated"})
    return out


__all__ = ["fmt"]
