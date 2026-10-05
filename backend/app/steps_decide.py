"""Steps 7 to 12: review, results, follow-up requests, the answer, what-if, the conclusion. Plus sample skip-ahead."""
from __future__ import annotations

import time

from . import config, db, evidence, samples
from .core import ApiError, JobError, gate, log, now_iso, running, start_job
from .engine import privacy
from .engine import trips as trip_rules
from .engine.addup import allowed_numbers, check_summary, sample_mix, template_summary, unknown_for_weak
from .engine.numbers import fmt, with_unit
from .engine.verdict import detail_figures, headline, reason_codes, verdict_of
from .engine.whatif import OVERALL_LABELS, adding_up, build_sliders, slider_range, what_if
from .llm.interface import get_llm
from .state import done_map, require_step
from .steps_frame import add_file, refresh_line, settings_of, touch

DECISION_WORDS = {"approve": "Accepted", "keep_client_reported": "Accepted as the client's data:",
                  "keep_belief": "Kept as the client's claim:", "keep_cross_check": "Kept as a sense check only:",
                  "reject": "Rejected"}


def _hyps(cid: int, kept: bool = True) -> list[dict]:
    hs = sorted(db.rows("hypothesis", cid), key=lambda h: h["order"])
    return [h for h in hs if not h.get("removed_reason")] if kept else hs


# ------------------------------------------------------------------ step 7: review
def review_counts(case: dict) -> dict | None:
    if not done_map(case)[6]:
        return None
    items = [e for e in evidence.all_items(case["id"]) if not e.get("trip_id")]
    auto = [e for e in items if e.get("bucket") == "auto"]
    dec = [e for e in items if e.get("bucket") == "decision"]
    picks = [e for e in items if e.get("spot_check_selected")]
    app = db.kv_get("app_settings", {}) or {}
    r = {"auto_total": len(auto), "auto_seen": sum(1 for e in auto if e.get("seen_by_consultant")),
         "decision_total": len(dec), "decided": sum(1 for e in dec if e["status"] != "needs_decision"),
         "spot_total": len(picks), "spot_done": sum(1 for e in picks if e.get("spot_check_result")),
         "sources_box": bool(settings_of(case).get("sources_reviewed_at")), "double_check": app.get("double_check", True) is not False}
    m = []
    if r["decided"] < r["decision_total"]:
        n = r["decision_total"] - r["decided"]
        m.append(f"Decide {n} more item{'s' if n != 1 else ''}")
    if r["auto_seen"] < r["auto_total"]:
        n = r["auto_total"] - r["auto_seen"]
        m.append(f"Look at {n} more source{'s' if n != 1 else ''}")
    if not r["sources_box"]:
        m.append("Tick \"I've checked these sources\"")
    r["missing"], r["ready"] = m, not m
    return r


def _item(case: dict, eid: str) -> dict:
    e = evidence.get(case["id"], eid)
    if not e:
        raise ApiError(404, f"There's no item {eid} in this case.")
    return e


def _open_trip_for(case: dict, e: dict) -> dict | None:
    if not e.get("trip_id"):
        return None
    return next((t for t in db.rows("trip", case["id"]) if t["id"] == e["trip_id"] and not t.get("retested_at")), None)


def _review_open(case: dict, e: dict) -> None:
    if e.get("trip_id"):
        if not _open_trip_for(case, e):
            raise gate("This idea has been tested again, so its evidence is locked.")
        return
    require_step(case, 7)
    if done_map(case)[7]:
        raise gate("The tests have run, so the review is locked.")


def decide(case: dict, eid: str, body: dict) -> None:
    e = _item(case, eid)
    _review_open(case, e)
    action = (body or {}).get("action")
    if action not in evidence.DECISIONS:
        raise ApiError(400, "Choose what to do with this item.")
    if e["status"] in ("duplicate", "pending", "pending_clean", "pass_line_source", "unreadable"):
        raise gate(f"{eid} can't be decided: it is {evidence.STATUS_LABELS.get(e['status'], 'a copy').lower()}.")
    reason = str((body or {}).get("reason") or "").strip()
    if action == "reject" and not reason:
        raise ApiError(400, "Give a short reason for rejecting this item.")
    calc = [f for f in e["figures_json"] if f.get("kind") == "calculated" and not f["derivation"].get("formula_confirmed")]
    note, formulas = "", []
    if action in ("approve", "keep_client_reported") and calc:
        confirm = bool((body or {}).get("confirm_formula"))
        if e.get("formula_needs_you") and not confirm:
            raise gate(f'Use "Accept and confirm formula" for {eid}: its calculation combines figures from different '
                       "sources or uses an assumption.")
        note = " (formula confirmed by you)" if confirm else " (formula checked)"
        for f in calc:
            f["derivation"]["formula_confirmed"] = True
            formulas.append(f["derivation"]["formula"])
        e["formula_needs_you"] = False
    e["status"] = evidence.DECISIONS[action]
    e["decided_by"] = "consultant"
    e["decision_reason"] = reason[0].upper() + reason[1:] if reason else ""
    e["seen_by_consultant"] = True
    for lk in e["links"]:
        lk["confirmed"] = action != "reject"
        if action == "keep_cross_check" and lk["role"] == "supports_test":
            lk["role"], lk["proposed_by"] = "cross_check", "consultant"
        elif action != "keep_cross_check" and lk["role"] == "cross_check":
            lk["role"] = "supports_test"
    evidence.save(e)
    word = DECISION_WORDS[action]
    log(case["id"], "consultant", "decision", 9 if e.get("trip_id") else 7,
        f"{word} {eid}{note}{': ' + e['decision_reason'] if e['decision_reason'] else ''}",
        {"evidence_id": eid, "action": action, "formulas": formulas})


def edit_links(case: dict, eid: str, rows: list[dict]) -> None:
    e = _item(case, eid)
    trip = _open_trip_for(case, e)
    if not trip:
        _review_open(case, e)
    if not isinstance(rows, list):
        raise ApiError(400, "Send the list of links for this item.")
    hyps = {h["code"]: h for h in _hyps(case["id"])}
    out = []
    for r in rows:
        code, role = r.get("hypothesis_code"), r.get("role")
        if code not in hyps:
            raise ApiError(400, f"There's no idea {code} in this case.")
        if trip and code != trip["hypothesis_code"]:
            raise gate(f"Only {trip['hypothesis_code']} is open for this reply. Everything else stays locked.")
        if role not in ("supports_test", "cross_check", "context"):
            raise ApiError(400, "Choose a role for each link.")
        idx = int(r.get("figure_index") or 0)
        if not (0 <= idx < len(e["figures_json"])):
            raise ApiError(400, "That figure isn't in this item.")
        out.append({"id": r.get("id") or evidence.next_link_id(), "hypothesis_code": code, "figure_index": idx,
                    "confirmed": True, "case_id": case["id"], "evidence_id": eid, "role": role, "proposed_by": "consultant"})
    e["links"] = out
    evidence.save(e)
    log(case["id"], "consultant", "links_edited", 9 if trip else 7,
        f"Changed what {eid} is used for: " + (", ".join(f"{x['hypothesis_code']} ({x['role'].replace('_', ' ')})" for x in out) or "nothing"))


def seen(case: dict, eid: str, body: dict) -> None:
    e = _item(case, eid)
    _review_open(case, e)
    if (body or {}).get("send_to_review"):
        e.update(status="needs_decision", bucket="decision", spot_check_selected=False)
        log(case["id"], "consultant", "sent_to_review", 7, f"Moved {eid} to Needs your call")
    else:
        e["seen_by_consultant"] = True
        log(case["id"], "consultant", "seen", 7, f"Looked at the source of {eid}")
    evidence.save(e)


def spot_check(case: dict, eid: str, body: dict) -> None:
    e = _item(case, eid)
    _review_open(case, e)
    if not e.get("spot_check_selected"):
        raise gate(f"{eid} wasn't picked for the quick double-check.")
    body = body or {}
    if body.get("skip"):
        e["spot_check_result"] = "skipped"
        log(case["id"], "consultant", "spot_check", 7, f"Quick double-check skipped by you ({eid})")
    else:
        m = bool(body.get("matches"))
        e["spot_check_result"] = "matches" if m else "does_not_match"
        e["seen_by_consultant"] = True
        if not m:
            e.update(status="needs_decision", bucket="decision")
            e["checklist_json"] = e["checklist_json"] + [{"test": "Quick double-check", "pass": False,
                                                          "threshold": "matches its source", "actual": "spot check did not match"}]
        log(case["id"], "consultant", "spot_check", 7, f"Double-checked {eid}: " +
            ("it matches its source" if m else "it doesn't match, so it moved to Needs your call"))
    evidence.save(e)


def confirm_sources(case: dict, body: dict) -> None:
    require_step(case, 7)
    if done_map(case)[7]:
        raise gate("The tests have run, so the review is locked.")
    on = bool((body or {}).get("ticked"))
    touch(case, settings={"sources_reviewed_at": now_iso() if on else None})
    log(case["id"], "consultant", "sources_reviewed", 7,
        "Confirmed the sources have been checked" if on else "Unticked \"I've checked these sources\"")


# ------------------------------------------------------------------ step 8: results
def _verdict(case: dict, h: dict, version: int, items: list[dict] | None = None) -> dict:
    th = (db.one("ruleset", case["id"]) or {}).get("thresholds_json") or config.ruleset_thresholds()
    figs = evidence.eligible_figures(case["id"], h, items)
    figs.sort(key=lambda f: int(f["evidence_id"][1:]))
    res, conf, why = verdict_of(figs, h["line"], h["comparator"], h["tolerance_pct"], h["fact_type"], h["measure_unit"],
                                th.get("minimum_sources"))
    vrow = db.insert("verdict_history", case["id"], {"hypothesis_code": h["code"], "result": res, "confidence": conf})
    return {"confidence": conf, "case_id": case["id"], "hypothesis_code": h["code"],
            "evidence_ids": [f["evidence_id"] for f in figs],
            "detail_json": {"line": h["line"], "figures": detail_figures(figs, h["line"], h["comparator"], h["tolerance_pct"],
                                                                          h["measure_unit"]),
                            "unit": h["measure_unit"], "comparator": h["comparator"], "tolerance_pct": h["tolerance_pct"]},
            "computed_at": now_iso(), "result": res, "id": vrow["id"],
            "reason_codes": reason_codes(res, conf, figs, h["line"], h["comparator"], h["tolerance_pct"], h["fact_type"]),
            "why": why, "version": version, "current": True}


def run_tests(case: dict) -> None:
    require_step(case, 7)
    if done_map(case)[7]:
        raise gate("The tests have already run.")
    if running(case["id"], "clean"):
        raise gate("The evidence is still being checked. Wait a moment.")
    r = review_counts(case)
    if not r["ready"]:
        raise gate("Finish the review first: " + "; ".join(x[0].lower() + x[1:] for x in r["missing"]) + ".", r["missing"])
    cid = case["id"]
    t = now_iso()
    touch(case, current_step=8, settings={"tests_run_at": t, "links_locked_at": t})
    log(cid, "consultant", "run_tests", 7, "Ran the tests. Links between evidence and ideas are now locked.")
    items = evidence.all_items(cid)
    for h in _hyps(cid):
        h["verdict"] = _verdict(case, h, 1, items)
        db.put("hypothesis", h)
        v = h["verdict"]
        log(cid, "rule_engine", "verdict", 8, headline(h["code"], v["result"], v["confidence"], v["why"]),
            {"code": h["code"], "result": v["result"], "confidence": v["confidence"]})


# ------------------------------------------------------------------ step 9: fill the gaps
def _trip(case: dict, tid: int) -> dict:
    t = next((x for x in db.rows("trip", case["id"]) if x["id"] == int(tid)), None)
    if not t:
        raise ApiError(404, "That request isn't in this case.")
    return t


def create_trip(case: dict, body: dict) -> dict:
    require_step(case, 9)
    if done_map(case)[10]:
        raise gate("The answer is already added up. Use What if... to change a target instead.")
    code = (body or {}).get("hypothesis") or (body or {}).get("hypothesis_id")
    h = next((x for x in _hyps(case["id"]) if x["code"] == code), None)
    if not h:
        raise ApiError(400, "Choose an idea that needs more evidence.")
    trips = [t for t in db.rows("trip", case["id"]) if t["hypothesis_code"] == code]
    if any(not t.get("retested_at") for t in trips):
        raise gate(f"There's already an open request for {code}. Finish it first.")
    th = ((db.one("ruleset", case["id"]) or {}).get("thresholds_json") or {}).get("trips") or {"free": 2, "max_with_override": 3}
    reason = str((body or {}).get("override_reason") or "").strip()
    why = trip_rules.check(len(trips), bool((body or {}).get("override")), reason, th.get("free", 2), th.get("max_with_override", 3))
    if why:
        raise gate(why, ["Reason for another request"])
    n = len(trips) + 1
    tid = len(db.rows("trip", case["id"])) + 1
    t = db.insert("trip", case["id"], {"id": tid, "n": n, "what_we_have": "", "reply_file_id": None, "sample_mix_json": {},
                                      "hypothesis_code": code, "question": "", "marked_sent_at": None,
                                      "override_reason": reason or None, "retested_at": None})
    if n > th.get("free", 2):
        log(case["id"], "consultant", "trip_override", 9, f"Asked for request {n} for {code} with a reason: {reason}")
    start_job(case["id"], f"trip_{tid}", lambda job: _draft_job(job, case["id"], tid),
              progress={"label": "Drafting a narrower question"})
    return {"trip_id": t["id"]}


def _draft_job(job, cid: int, tid: int) -> None:
    case = db.case_get(cid)
    t = _trip(case, tid)
    h = next(x for x in _hyps(cid) if x["code"] == t["hypothesis_code"])
    files = db.rows("client_file", cid)
    held = [{"file": f["filename"], "figures": [g["quote_span"] for g in f.get("figures") or [] if g.get("verified")]}
            for f in files]
    v = h.get("verdict") or {}
    llm = get_llm(case)
    if not llm.live and not llm.has("DRAFT_FOLLOWUP", h["code"]):
        t["question"] = (f"Can you share {h['measure_name'].lower()} ({h['measure_unit']}), with where the figure comes "
                         f"from? We need it to check whether {h['text'][0].lower() + h['text'][1:]}")
        t["what_we_have"] = "We have the files you already sent. They don't answer this point yet."
        db.put("trip", t)
        log(cid, "rule_engine", "followup_template", 9, f"Wrote a plain follow-up question for {h['code']}. Demo data "
                                                        "mode has no stored draft for this idea.")
        return
    out = llm.run("DRAFT_FOLLOWUP", h["code"], {
        "idea": h["text"], "measure": h["measure_name"], "target": f"{'at least' if h['comparator'] == '>=' else 'at most'} "
                                                                  f"{h['line_text']}", "why_open": v.get("why", ""),
        "data_held": [{"file": x["file"], "figures": [privacy.mask_for_model(q, case) for q in x["figures"]]} for x in held],
        "needs": [n["text"] for n in db.rows("need", cid) if n["hypothesis_code"] == h["code"]]})
    q = str(out.get("question") or "").strip()
    if not q:
        raise JobError("We couldn't draft a follow-up question. Write your own in the box.")
    log(cid, "llm", "followup_drafted", 9, f"Drafted a follow-up question for {h['code']}")
    chk = privacy.check_outbound(q, case, files)
    q = chk["original"]
    for term in chk["blocked"]:
        q = q.replace(term, "[private figure removed]")
    t["question"], t["what_we_have"] = q, str(out.get("what_we_have") or "")
    db.put("trip", t)
    log(cid, "rule_engine", "followup_checked", 9, "Checked the follow-up question for private numbers" +
        (f". Removed {len(chk['blocked'])} private figure(s)." if chk["blocked"] else ""))


def edit_trip(case: dict, tid: int, body: dict) -> None:
    t = _trip(case, tid)
    if t.get("reply_file_id"):
        raise gate("The reply has arrived, so the question can't change now.")
    q = str((body or {}).get("question") or "").strip()
    if not q:
        raise ApiError(400, "Write the question first.")
    chk = privacy.check_outbound(q, case, db.rows("client_file", case["id"]))
    if chk["blocked"]:
        raise gate(f"The question contains a private term: {', '.join(chk['blocked'])}. Remove it and save again.", chk["blocked"])
    if q != t["question"]:
        t["question"] = q
        db.put("trip", t)
        log(case["id"], "consultant", "followup_edited", 9, f"Edited the follow-up question for {t['hypothesis_code']}")


def trip_mark_sent(case: dict, tid: int) -> None:
    t = _trip(case, tid)
    if not t.get("question"):
        raise gate("The question isn't ready yet.")
    if t.get("marked_sent_at"):
        return
    t["marked_sent_at"] = now_iso()
    db.put("trip", t)
    log(case["id"], "consultant", "trip_sent", 9,
        f"Marked request {t['n']} for {t['hypothesis_code']} as sent. The tool sent nothing itself.")


def trip_reply(case: dict, tid: int, filename: str, data: bytes | None, text: str | None) -> dict:
    t = _trip(case, tid)
    if not t.get("marked_sent_at"):
        raise gate("Mark the request as sent first.", ["Mark as sent"])
    if t.get("reply_file_id"):
        raise gate("The reply for this request has already been added.")
    f = add_file(case, filename or f"reply-{t['hypothesis_code']}.txt", data, "followup", text=text, trip_id=t["id"], step=9)
    t["reply_file_id"] = f["id"]
    db.put("trip", t)
    return start_job(case["id"], f"trip_reply_{tid}", lambda job: _reply_job(job, case["id"], tid, f["id"]),
                     progress={"label": "Linking and checking the reply"})


def _reply_job(job, cid: int, tid: int, fid: int) -> None:
    from .steps_gather import ingest_file_now
    case = db.case_get(cid)
    t = _trip(case, tid)
    f = db.get("client_file", fid)
    ingest_file_now(case, f, t)
    for h in db.rows("hypothesis", cid):
        if h["code"] == t["hypothesis_code"]:
            h["links_reopened_for_trip"] = True
            db.put("hypothesis", h)
    log(cid, "rule_engine", "trip_links_reopened", 9,
        f"Reopened {t['hypothesis_code']} for the reply. Everything else stays locked.")
    f = db.get("client_file", fid)
    mix = f.get("sample_mix") or {}
    if mix.get("sample") and mix.get("target"):
        _store_mix(case, t, mix["sample"], mix["target"], mix.get("target_note", ""))


def _store_mix(case: dict, t: dict, sample: dict, target: dict, note: str = "") -> dict:
    thr = float(config.rules()["sample_mix"]["max_difference_pct_points"])
    res = sample_mix(sample, target, thr, note)
    if not res["rows"]:
        raise ApiError(400, "Give the same groups for the reply's sample and the target group.")
    t = _trip(case, t["id"])
    t["sample_mix_json"] = res
    db.put("trip", t)
    if res["passes"]:
        msg = "Compared the reply's sample with the target group: the mix matches"
    else:
        flagged = ", ".join(r["dimension"] for r in res["rows"] if r["flag"])
        msg = f"Compared the reply's sample with the target group: it differs by more than {fmt(thr)} points on {flagged}"
    log(case["id"], "rule_engine", "sample_mix", 9, msg)
    return res


def trip_sample_mix(case: dict, tid: int, body: dict) -> dict:
    t = _trip(case, tid)
    if not t.get("reply_file_id"):
        raise gate("Add the reply first.")
    if t.get("retested_at"):
        raise gate("This idea has been tested again, so the check is locked.")
    body = body or {}
    if body.get("not_applicable"):
        t["sample_mix_json"] = {"not_applicable": True}
        db.put("trip", t)
        log(case["id"], "consultant", "sample_mix", 9, "Marked the sample check as not needed for this reply")
        return t["sample_mix_json"]
    try:
        sample = {str(k): float(v) for k, v in (body.get("sample") or {}).items()}
        target = {str(k): float(v) for k, v in (body.get("target") or {}).items()}
    except (TypeError, ValueError):
        raise ApiError(400, "Type each share as a number.")
    return _store_mix(case, t, sample, target, "Entered by you")


def retest(case: dict, body: dict) -> None:
    code = (body or {}).get("hypothesis")
    trips = [t for t in db.rows("trip", case["id"]) if t["hypothesis_code"] == code and not t.get("retested_at")]
    if not trips:
        raise gate(f"There's no open request for {code}.")
    t = trips[-1]
    if not t.get("reply_file_id"):
        raise gate("Add the reply first.", ["Add the reply"])
    if running(case["id"], f"trip_reply_{t['id']}"):
        raise gate("The reply is still being checked. Wait a moment.")
    items = evidence.all_items(case["id"])
    open_ids = [e["id"] for e in items if e.get("trip_id") == t["id"] and e["status"] == "needs_decision"]
    if open_ids:
        raise gate("Make a call on the new evidence first: " + ", ".join(open_ids) + ".", open_ids)
    if not t.get("sample_mix_json"):
        raise gate("Compare the reply's sample with the target group, or mark the check as not needed.", ["Sample check"])
    h = next(x for x in _hyps(case["id"]) if x["code"] == code)
    h["verdict"] = _verdict(case, h, int((h.get("verdict") or {}).get("version") or 1) + 1, items)
    h["links_reopened_for_trip"] = False
    db.put("hypothesis", h)
    t["retested_at"] = now_iso()
    db.put("trip", t)
    v = h["verdict"]
    log(case["id"], "consultant", "test_again", 9, f"Tested {code} again with the new evidence")
    log(case["id"], "rule_engine", "verdict", 8, headline(code, v["result"], v["confidence"], v["why"]),
        {"code": code, "result": v["result"], "confidence": v["confidence"]})


# ------------------------------------------------------------------ step 10: the answer
def run_addup(case: dict) -> dict:
    require_step(case, 10)
    j = running(case["id"], "addup")
    if j:
        return j[0]
    if done_map(case)[10]:
        raise gate("The answer is already added up.")
    log(case["id"], "consultant", "addup_requested", 10, "Asked for the answer to be added up")
    return start_job(case["id"], "addup", lambda job: _addup_job(job, case["id"]), progress={"label": "Writing the summary"})


def _overall_rows(cid: int) -> list[dict]:
    return [{"code": h["code"], "must_have": h["must_have"], "result": (h.get("verdict") or {}).get("result", "not_enough")}
            for h in _hyps(cid)]


def _addup_job(job, cid: int) -> None:
    case = db.case_get(cid)
    llm = get_llm(case)
    hyps = _hyps(cid)
    overall, text = adding_up(_overall_rows(cid))
    db.delete_all("overall", cid)
    db.insert("overall", cid, {"result": overall, "rule_applied": text, "stale": True, "computed_at": now_iso(),
                               "label": OVERALL_LABELS[overall]})
    log(cid, "rule_engine", "added_up", 10, f"Added up the results using the locked rule: {OVERALL_LABELS[overall]}. {text}")
    items = evidence.all_items(cid)
    calcs = db.rows("calc", cid)
    payload = {"overall": OVERALL_LABELS[overall], "rule": text, "ideas": [
        {"code": h["code"], "text": h["text"], "critical": h["must_have"], "target": h["line_text"],
         "comparator": h["comparator"], "result": h["verdict"]["result"], "confidence": h["verdict"]["confidence"],
         "why": h["verdict"]["why"], "evidence": [{"id": f["evidence_id"], "figure": f["text"]}
                                                  for f in h["verdict"]["detail_json"]["figures"]]} for h in hyps]}
    ids = {e["id"] for e in items}
    allowed = allowed_numbers(hyps, items, calcs)
    verdicts = {h["code"]: h["verdict"] for h in hyps}
    cited = {}
    for e in items:
        for lk in e.get("links") or []:
            cited.setdefault(e["id"], set()).add(lk["hypothesis_code"])
    sentences, source = None, "llm"
    for attempt in range(2 if llm.live else 1):
        try:
            out = llm.run("SUMMARISE", "", payload if attempt == 0 else dict(payload, problems=problems))
        except JobError:
            raise
        except Exception:
            break
        cand = [{"text": str(s.get("text") or "").strip(), "evidence_ids": [str(x) for x in s.get("evidence_ids") or []]}
                for s in out.get("sentences") or []]
        problems = check_summary(cand, ids, allowed, verdicts, cited)
        if not problems:
            sentences = cand
            break
    if sentences is None:
        sentences, source = template_summary(hyps), "template"
        log(cid, "rule_engine", "summary_template", 10, "Built a plain summary from the results")
    else:
        log(cid, "llm", "summary_written", 10, "Drafted the summary. Every sentence cites its evidence and passed the checks.")
    job.progress(label="Listing what is still unknown")
    unknowns = _unknowns(case, llm, hyps)
    db.delete_all("summary", cid)
    prev = db.rows("summary", cid)
    db.insert("summary", cid, {"source": source, "unknowns": unknowns, "sentences": sentences, "version": len(prev) + 1})
    log(cid, "llm", "unknowns_listed", 11, f"Listed {len(unknowns)} thing{'s' if len(unknowns) != 1 else ''} that "
                                           f"{'are' if len(unknowns) != 1 else 'is'} still unknown")
    ov = db.one("overall", cid)
    ov["stale"] = False
    db.put("overall", ov)
    touch(case, current_step=11)


def _unknowns(case: dict, llm, hyps: list[dict]) -> list[dict]:
    codes = {h["code"] for h in hyps}
    weak = [h for h in hyps if h["verdict"]["result"] in ("not_enough", "conflicting") or h["verdict"]["confidence"] == "low"]
    try:
        out = llm.run("UNKNOWNS", "", {"ideas": [{"code": h["code"], "text": h["text"], "result": h["verdict"]["result"],
                                                  "confidence": h["verdict"]["confidence"], "why": h["verdict"]["why"]}
                                                 for h in hyps]})
        items = [{"idea": str(u.get("idea")), "text": str(u.get("text") or "").strip()} for u in out.get("unknowns") or []
                 if u.get("idea") in codes and str(u.get("text") or "").strip()]
    except JobError:
        items = []
    covered = {u["idea"] for u in items}
    for h in weak:
        if h["code"] not in covered:
            items.append({"idea": h["code"], "text": unknown_for_weak(h["code"], h["verdict"]["result"], h["verdict"]["confidence"])})
    order = {h["code"]: i for i, h in enumerate(hyps)}
    return sorted(items, key=lambda u: order.get(u["idea"], 99))


# ------------------------------------------------------------------ step 11: what if
def _require_tested(case: dict) -> None:
    if not done_map(case)[8]:
        raise gate("Run the tests first.", ["Run tests"])


def whatif(case: dict, body: dict) -> dict:
    _require_tested(case)
    hyps = _hyps(case["id"])
    ev = {e["id"]: e for e in evidence.all_items(case["id"])}
    th = (db.one("ruleset", case["id"]) or {}).get("thresholds_json") or {}
    ov = db.one("overall", case["id"])
    try:
        return what_if(hyps, ev, th.get("minimum_sources") or {}, body or {}, ov and ov["result"])
    except (ValueError, TypeError, ZeroDivisionError):
        raise ApiError(400, "Keep the value inside the slider's range.")


def sliders(case: dict) -> list[dict]:
    return build_sliders(_hyps(case["id"])) if done_map(case)[8] else []


def retarget(case: dict, body: dict) -> dict:
    """Make a stress-test value the real target: reopen, change, lock again, re-test in code, add up again."""
    _require_tested(case)
    cid = case["id"]
    body = body or {}
    rows = sliders(case)
    row = next((s for s in rows if s["kind"] == body.get("kind") and s["key"] == body.get("key")), None)
    try:
        value = float(body.get("value"))
    except (TypeError, ValueError):
        value = None
    if not row:
        raise ApiError(400, "That slider isn't available. Refresh the page and try again.")
    if value is None or not (row["min"] - 1e-9 <= value <= row["max"] + 1e-9):
        raise ApiError(400, "Keep the value inside the slider's range.")
    if abs(value - row["value"]) < 1e-9:
        raise ApiError(400, "Move the slider first. This value is already your target.")
    if running(cid, "addup"):
        raise gate("The answer is still being added up. Wait a moment.")
    w = whatif(case, {"assumptions": {body["key"]: value}} if body["kind"] == "assumption" else {"pass_lines": {body["key"]: value}})
    extra = f" ({row['label']}: {fmt(row['value'])} to {fmt(value)} {row['unit']})" if body["kind"] == "assumption" else ""
    log(cid, "consultant", "plan_reopened", 3, "Reopened the targets at step 3 to use a stress-test value")
    for h in _hyps(cid):
        r = next(x for x in w["ideas"] if x["code"] == h["code"])
        if body["kind"] == "pass_line" and h["code"] == body["key"]:
            h["pass_line_formula"], h["pass_line_value"] = None, value
        if body["kind"] == "assumption":
            h["assumptions_json"] = [dict(a, value=value) if a["name"] == body["key"] else a for a in h.get("assumptions_json") or []]
        if abs(r["line"] - h["line"]) > 1e-9:
            log(cid, "consultant", "target_changed", 3, f"Changed {h['code']} target from {fmt(h['line'])} to {fmt(r['line'])} "
                                                        f"{h['measure_unit']} after the stress test{extra}")
            h["pass_line_source_note"] = ((h.get("pass_line_source_note") or "") + " " if h.get("pass_line_source_note") else "") + \
                f"Changed from {fmt(h['line'])} to {fmt(r['line'])} after the stress test."
        refresh_line(h)
        h["line"] = r["line"]
        h["line_text"] = with_unit(r["line"], h["measure_unit"])
        h["locked_at"] = now_iso()
        db.put("hypothesis", h)
    log(cid, "consultant", "plan_locked", 3, "Locked the targets again. Evidence you reviewed is kept.")
    log(cid, "rule_engine", "results_cleared", 8, "Cleared the results from step 8 onwards to run them again")
    items = evidence.all_items(cid)
    for h in _hyps(cid):
        v = _verdict(case, h, int((h.get("verdict") or {}).get("version") or 1) + 1, items)
        h["verdict"] = v
        db.put("hypothesis", h)
        log(cid, "rule_engine", "verdict", 8, headline(h["code"], v["result"], v["confidence"], v["why"]),
            {"code": h["code"], "result": v["result"], "confidence": v["confidence"]})
    db.delete_all("overall", cid)
    db.delete_all("summary", cid)
    c = db.one("conclusion", cid)
    if c:
        c["saved_at"] = None
        db.put("conclusion", c)
    touch(case, current_step=8)
    log(cid, "consultant", "addup_requested", 10, "Asked for the answer to be added up")
    return {"job": start_job(cid, "addup", lambda job: _addup_job(job, cid), progress={"label": "Writing the summary"})}


# ------------------------------------------------------------------ step 12: your conclusion
def save_conclusion(case: dict, body: dict) -> None:
    text = str((body or {}).get("text") or "")
    if not text.strip():
        raise ApiError(400, "Write your conclusion in the box first.")
    require_step(case, 12)
    db.delete_all("conclusion", case["id"])
    db.insert("conclusion", case["id"], {"text": text, "saved_at": now_iso()})
    touch(case, current_step=12)
    log(case["id"], "consultant", "conclusion_saved", 12, "Saved your conclusion")


# ------------------------------------------------------------------ sample skip-ahead (never bypasses a gate)
def _wait(cid: int, kinds: tuple, timeout: float = 120) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        jobs = {j["kind"]: j for j in db.rows("job", cid)}
        if any(k in jobs and jobs[k]["status"] == "failed" for k in kinds):
            failed = next(jobs[k] for k in kinds if k in jobs and jobs[k]["status"] == "failed")
            raise JobError(failed["error"] or "A step didn't finish.")
        if not any(j["status"] == "running" for j in jobs.values() if j["kind"] != "advance"):
            if all(k in jobs for k in kinds):
                return
        time.sleep(0.1)
    raise JobError("Skipping ahead took too long. Try again.")


def advance(case: dict, to: int) -> dict:
    if not case.get("sample"):
        raise ApiError(400, "Skip to step only works on sample cases.")
    if not 1 <= to <= 12:
        raise ApiError(400, "Choose a step from 1 to 12.")
    if running(case["id"]):
        raise gate("Wait for the current step to finish first.")
    cur = (db.case_get(case["id"]) or case)["current_step"]
    log(case["id"], "system", "sample_advance", cur, f"Skipped ahead to step {to} using the sample's recorded answers (sample data)")
    return start_job(case["id"], "advance", lambda job: _advance_job(job, case["id"], to), progress={"label": f"Skipping to step {to}"})


def _advance_job(job, cid: int, to: int) -> None:
    from .steps_frame import confirm_frame, edit_hypotheses, lock_plan, mark_requests_sent, read_ask
    script = samples.pack(db.case_get(cid)["sample"]).get("script") or {}

    def c():
        return db.case_get(cid)

    def d():
        return done_map(c())

    if not d()[1]:
        read_ask(c())
        _wait(cid, ("frame",))
    if to >= 3 and not d()[2]:
        confirm_frame(c())
        _wait(cid, ("plan",))
    if to >= 4 and not d()[3]:
        rem = [{"code": r["code"], "removed_reason": r["reason"]} for r in script.get("remove_ideas") or []
               if any(h["code"] == r["code"] and not h.get("removed_reason") for h in db.rows("hypothesis", cid))]
        if rem:
            edit_hypotheses(c(), rem)
        lock_plan(c(), {"ticked": True})
        _wait(cid, ("route",))
    if to >= 5 and not d()[4]:
        mark_requests_sent(c(), {"reviewed": True})
        _wait(cid, ("collect", "clean"))
    if to >= 8 and not d()[7]:
        _script_review(c(), script)
        run_tests(c())
    if to >= 10 and not d()[10]:
        for tr in script.get("trips") or []:
            if any(t["hypothesis_code"] == tr["idea"] for t in db.rows("trip", cid)):
                continue
            r = create_trip(c(), {"hypothesis": tr["idea"], "override": False})
            _wait(cid, (f"trip_{r['trip_id']}",))
            trip_mark_sent(c(), r["trip_id"])
            fn, data = samples.reply_file(c()["sample"], tr["idea"])
            trip_reply(c(), r["trip_id"], fn, data, None)
            _wait(cid, (f"trip_reply_{r['trip_id']}",))
            for e in evidence.all_items(cid):
                if e.get("trip_id") == r["trip_id"] and e["status"] == "needs_decision":
                    decide(c(), e["id"], _script_action(e, script))
            t = _trip(c(), r["trip_id"])
            if not t.get("sample_mix_json"):
                trip_sample_mix(c(), t["id"], {"not_applicable": True})
            retest(c(), {"hypothesis": tr["idea"]})
    if to >= 11 and not d()[10]:
        run_addup(c())
        _wait(cid, ("addup",))


def _script_action(e: dict, script: dict) -> dict:
    rules = (script.get("decide") or {})
    tag = e.get("script_tag") or ""
    if tag and tag in (rules.get("by_script_tag") or {}):
        act = dict(rules["by_script_tag"][tag])
    elif e["origin_type"] == "client_file" and (e.get("credibility_json") or {}).get("matches_belief"):
        act = dict(rules.get("client_belief") or {"action": "keep_belief"})
    elif e["origin_type"] == "client_file":
        act = dict(rules.get("client_file") or {"action": "keep_client_reported"})
    else:
        act = dict(rules.get("default") or {"action": "approve"})
    if e.get("formula_needs_you") and act["action"] in ("approve", "keep_client_reported"):
        act["confirm_formula"] = True
    return act


def _script_review(case: dict, script: dict) -> None:
    for e in evidence.all_items(case["id"]):
        if e.get("trip_id"):
            continue
        if e.get("spot_check_selected") and not e.get("spot_check_result"):
            spot_check(case, e["id"], {"matches": script.get("spot_check", "matches") == "matches"})
    for e in evidence.all_items(case["id"]):
        if e.get("trip_id"):
            continue
        if e.get("bucket") == "auto":
            seen(case, e["id"], {})
    for e in evidence.all_items(case["id"]):
        if e.get("trip_id"):
            continue
        if e.get("bucket") == "decision" and e["status"] == "needs_decision":
            decide(case, e["id"], _script_action(e, script))
    if not settings_of(case).get("sources_reviewed_at"):
        confirm_sources(case, {"ticked": True})
