"""Steps 1 to 4: describe the ask, confirm the question, set the targets, plan the research."""
from __future__ import annotations

from . import config, db, evidence, samples
from .core import ApiError, JobError, gate, log, now_iso, running, start_job
from .engine import privacy
from .engine.whatif import FormulaError, check_formula, line_of
from .engine.numbers import with_unit
from .files import parse
from .llm.interface import get_llm
from .search import get_search
from .state import done_map, require_step

BLANK_FAIL = ("A new case needs the live AI and search services, but this app is in demo data mode. Try a sample case "
              "instead, or add the live keys and switch to live mode in Settings.")


# ------------------------------------------------------------------ cases and files
def new_case(fields: dict, mode: str) -> dict:
    case = {"updated_at": now_iso(), "client_name": "", "private_numbers": [], "function": "", "mode": mode, "sample": "",
            "current_step": 1, "created_at": now_iso(), "title": "New case", "client_aliases": [], "country": "",
            "industry": "", "raw_ask": "", "status": "open", "settings_json": {"ai_reads_client_files": True}}
    case.update(fields)
    cid = db.case_insert(case)
    return db.case_get(cid)


def touch(case: dict, **kw) -> dict:
    with db.lock():
        cur = db.case_get(case["id"]) or case
        for k, v in kw.items():
            if k == "settings":
                cur["settings_json"] = dict(cur.get("settings_json") or {}, **v)
            else:
                cur[k] = v
        cur["updated_at"] = now_iso()
        db.case_put(cur)
        case.clear()
        case.update(cur)
        return cur


def settings_of(case: dict) -> dict:
    return (db.case_get(case["id"]) or case).get("settings_json") or {}


def add_file(case: dict, filename: str, data: bytes | None, kind: str, text: str | None = None,
             trip_id: int | None = None, step: int = 1) -> dict:
    if data is not None:
        low = (filename or "").lower()
        if not low.endswith(parse.ALLOWED):
            raise ApiError(400, "This file type isn't supported. Upload a csv, xlsx, txt or pdf file.")
        if len(data) > config.rules()["limits"]["max_upload_mb"] * 1024 * 1024:
            raise ApiError(400, "This file is larger than 20 MB. Upload a smaller file or split it.")
        try:
            extract = parse.parse(filename, data)
        except parse.ParseError as e:
            raise ApiError(400, str(e))
    else:
        extract = parse.pasted(text or "")
        if not extract.strip():
            raise ApiError(400, "Paste the text first.")
    row = db.insert("client_file", case["id"], {"filename": filename, "kind": kind, "uploaded_at": now_iso(),
                                               "figures": [], "trip_id": trip_id, "preview": extract, "describe": {},
                                               "read": False})
    log(case["id"], "client" if kind != "expert_note" else "expert", "file_uploaded", step,
        f"Added the file {filename}", {"file_id": row["id"]})
    return row


def load_sample(name: str, mode: str) -> dict:
    p = samples.pack(name)
    if not p:
        raise ApiError(404, "That sample isn't available. Choose one from the list.")
    c = p["case"]
    case = new_case({k: c[k] for k in ("title", "client_name", "client_aliases", "private_numbers", "country",
                                       "industry", "function", "raw_ask")} | {"sample": name}, mode)
    log(case["id"], "consultant", "case_created", 1, "Started a case from a sample",
        {k: True for k in ("client_name", "country", "industry", "function", "raw_ask")})
    _sample_files(case, p)
    log(case["id"], "system", "sample_loaded", 1, "Loaded a sample case. Its data is simulated.")
    return case


def _sample_files(case: dict, p: dict) -> None:
    for fn in p["case"].get("client_files") or []:
        add_file(case, fn, (p["dir"] / "client_files" / fn).read_bytes(), "initial")


def reset(case: dict) -> None:
    cid = case["id"]
    db.case_clear(cid)
    fresh = {"current_step": 1, "status": "open", "settings_json": {"ai_reads_client_files":
                                                                    settings_of(case).get("ai_reads_client_files", True)}}
    if case.get("sample"):
        c = samples.pack(case["sample"])["case"]
        fresh.update({k: c[k] for k in ("title", "client_name", "client_aliases", "private_numbers", "country",
                                        "industry", "function", "raw_ask")})
    touch(case, **fresh)
    if case.get("sample"):
        _sample_files(case, samples.pack(case["sample"]))
    log(cid, "consultant", "case_reset", 1, "Reset the case to step 1")


# ------------------------------------------------------------------ step 1: read the ask
REQUIRED_FIELDS = (("client_name", "Client"), ("country", "Country"), ("industry", "Industry"),
                   ("function", "Function"), ("raw_ask", "The ask"))


def read_ask(case: dict) -> dict:
    if done_map(case)[2]:
        raise gate("The question is already confirmed. Reset the case to start again.")
    missing = [label for k, label in REQUIRED_FIELDS if not str(case.get(k) or "").strip()]
    if missing:
        raise gate("Fill in " + ", ".join(m.lower() if i else m for i, m in enumerate(missing)) + " first.", missing)
    log(case["id"], "consultant", "read_ask", 1, "Asked for the ask to be checked")
    return start_job(case["id"], "frame", lambda job: _frame_job(job, case["id"]),
                     progress={"label": "Framing the question", "done": 0, "total": 3})


def _frame_job(job, cid: int) -> None:
    case = db.case_get(cid)
    if case.get("mode") != "live" and not case.get("sample"):
        job.progress(total=0)
        raise JobError(BLANK_FAIL)
    llm = get_llm(case)
    files = [f for f in db.rows("client_file", cid) if f["kind"] == "initial"]
    job.progress(done=1)                                            # privacy filter ready (names masked below)
    if (case.get("settings_json") or {}).get("ai_reads_client_files", True):
        for f in files:
            read_file(case, f, llm, step=1)
    job.progress(done=2)
    figs = []
    for f in db.rows("client_file", cid):
        for g in f.get("figures") or []:
            if g.get("verified"):
                figs.append({"file": f["filename"], "quote": g["quote_span"], "unit": g["unit"]})
    out = llm.run("FRAME", "", {"ask": privacy.mask_for_model(case["raw_ask"], case), "country": case["country"],
                                "industry": case["industry"], "function": case["function"], "file_figures": figs})
    fr = {k: str(out.get(k) or "").strip() for k in ("client_belief", "decision", "case_measure_name",
                                                     "case_measure_definition")}
    if not fr["client_belief"] or not fr["decision"]:
        raise JobError("We couldn't draft the question from this ask. Add a little more detail and try again.")
    db.delete_all("frame", cid)
    db.insert("frame", cid, dict(fr, confirmed_at=None, proposed=dict(fr)))
    log(cid, "llm", "frame_proposed", 2, "Drafted the question: what the client believes, the decision they face, "
                                         "and how to compare numbers")
    job.progress(done=3)
    touch(case, current_step=2)


def read_file(case: dict, f: dict, llm, step: int) -> dict:
    """The fast model pulls out each figure with its quote; code checks every quote word for word."""
    key = f["filename"]
    if not llm.live and not llm.has("READ_FILE", key):
        f.update(figures=[], describe={}, sample_mix=None, read=True)
        db.put("client_file", f)
        log(case["id"], "system", "file_not_read", step, f"Demo data mode has no stored reading for {f['filename']}, so "
                                                          "no figures were taken from it. Switch to live mode to read new files.")
        return f
    payload = {"filename": f["filename"], "text": privacy.mask_for_model(f["preview"][:config.rules()["limits"]["max_page_chars"] * 2], case),
               "ask": privacy.mask_for_model(case.get("raw_ask", ""), case), "country": case.get("country", "")}
    out = llm.run("READ_FILE", key, payload)
    figs = evidence.clean_figures(out.get("figures") or [], f["preview"], web=False)
    f["figures"] = figs
    f["describe"] = out.get("describe") or {}
    f["sample_mix"] = out.get("sample_mix") or None
    f["read"] = True
    db.put("client_file", f)
    n = len(figs)
    ok = sum(1 for g in figs if g["verified"])
    log(case["id"], "llm", "file_read", step, f"Read {f['filename']} and found {n} figures")
    log(case["id"], "rule_engine", "quotes_verified", step,
        f"Found {ok} of {n} figures word for word in {f['filename']}")
    return f


def set_file_figures(case: dict, fid: int, figures: list[dict]) -> None:
    f = db.get("client_file", fid)
    if not f or f["case_id"] != case["id"]:
        raise ApiError(404, "That file isn't in this case.")
    out = []
    for g in figures or []:
        try:
            v = float(g.get("value"))
        except (TypeError, ValueError):
            raise ApiError(400, "Type each figure as a number.")
        out.append({"value": v, "low": None, "high": None, "unit": str(g.get("unit") or ""), "period": "",
                    "quote_span": "", "locator": str(g.get("locator") or ""), "kind": "reported", "verified": True,
                    "verify_note": "typed in by you" + (f" ({g.get('locator')})" if g.get("locator") else "")})
    f["figures"], f["read"] = out, True
    db.put("client_file", f)
    log(case["id"], "consultant", "figures_typed", case.get("current_step", 1),
        f"Typed in {len(out)} figure(s) from {f['filename']}")


# ------------------------------------------------------------------ step 2: confirm the question
def edit_frame(case: dict, body: dict) -> None:
    fr = db.one("frame", case["id"])
    if not fr:
        raise gate('Finish "Describe the ask" first', ["Describe the ask"])
    if fr.get("confirmed_at"):
        raise gate("The question is confirmed, so it can't be edited now.")
    changed = False
    for k in ("client_belief", "decision", "case_measure_name", "case_measure_definition"):
        if k in body and str(body[k]) != fr.get(k):
            fr[k] = str(body[k])
            changed = True
    if changed:
        db.put("frame", fr)
        log(case["id"], "consultant", "frame_edited", 2, "Edited the question")


def confirm_frame(case: dict) -> dict:
    require_step(case, 2)
    fr = db.one("frame", case["id"])
    if running(case["id"], "frame"):
        raise gate("The question is still being drafted. Wait a moment.")
    if fr.get("confirmed_at"):
        j = [x for x in running(case["id"], "plan")]
        if j:
            return j[0]
        raise gate("The question is already confirmed.")
    fr["confirmed_at"] = now_iso()
    db.put("frame", fr)
    log(case["id"], "consultant", "frame_confirmed", 2,
        "Confirmed the question. The client's belief is now a claim to test, not a fact.")
    return start_plan(case)


def start_plan(case: dict) -> dict:
    return start_job(case["id"], "plan", lambda job: _plan_job(job, case["id"]),
                     progress={"label": "Fetching pass-line benchmarks", "done": 0, "total": 0})


def _plan_job(job, cid: int) -> None:
    case = db.case_get(cid)
    llm = get_llm(case)
    fr = db.one("frame", cid)
    files = db.rows("client_file", cid)
    out = llm.run("PLAN_HYPOTHESES", "", {
        "frame": {k: fr[k] for k in ("client_belief", "decision", "case_measure_name", "case_measure_definition")},
        "ask": privacy.mask_for_model(case["raw_ask"], case), "country": case["country"], "industry": case["industry"],
        "function": case["function"], "max_ideas": config.rules()["limits"]["max_ideas"],
        "file_figures": [{"file": f["filename"], "quote": g["quote_span"], "unit": g["unit"]}
                         for f in files for g in f.get("figures") or [] if g.get("verified")]})
    ideas = (out.get("ideas") or [])[: config.rules()["limits"]["max_ideas"]]
    if not ideas:
        raise JobError("We couldn't draft ideas to test from this question. Edit the question and try again.")
    db.delete_all("hypothesis", cid)
    th = config.ruleset_thresholds()
    for i, idea in enumerate(ideas):
        h = _idea_row(idea, i, th)
        db.insert("hypothesis", cid, h)
    db.delete_all("ruleset", cid)
    db.insert("ruleset", cid, {"thresholds_json": th, "locked_at": None, "adding_up_rule": config.rules()["adding_up_rule"]})
    log(cid, "llm", "ideas_drafted", 3, f"Drafted {len(ideas)} ideas to test, each with a target")
    bench = [(h, idea) for h, idea in zip(sorted(db.rows("hypothesis", cid), key=lambda x: x["order"]), ideas)
             if h["pass_line_source_type"] == "benchmark"]
    job.progress(total=len(bench))
    search = get_search(case)
    for n, (h, idea) in enumerate(bench, 1):
        fetch_benchmark(case, h, idea.get("benchmark_query") or h["measure_name"], search, llm)
        job.progress(done=n)
    touch(case, current_step=3, settings={"plan_ready_at": now_iso()})


def _idea_row(idea: dict, order: int, th: dict) -> dict:
    assumptions = []
    for a in idea.get("assumptions") or []:
        try:
            assumptions.append({"name": str(a["name"]), "label": str(a.get("label") or a["name"]), "value": float(a["value"]),
                                "unit": str(a.get("unit") or ""), "min": _f(a.get("min")), "max": _f(a.get("max"))})
        except (KeyError, TypeError, ValueError):
            continue
    formula = (idea.get("pass_line_formula") or None)
    if formula:
        try:
            check_formula(formula, [a["name"] for a in assumptions])
        except FormulaError:
            formula = None
    h = {"measure_definition": str(idea.get("measure_definition") or ""), "tolerance_pct": float(idea.get("tolerance_pct") or th.get("tolerance_pct_default", 5)),
         "comparator": ">=" if idea.get("comparator") not in (">=", "<=") else idea["comparator"],
         "recency_category": idea.get("recency_category") if idea.get("recency_category") in ("size_growth_price", "structural_timing") else "size_growth_price",
         "code": f"H{order + 1}", "pass_line_value": _f(idea.get("pass_line_value")),
         "pass_line_source_type": idea.get("pass_line_source_type") if idea.get("pass_line_source_type") in ("client_goal", "benchmark", "estimate") else "estimate",
         "text": str(idea.get("text") or ""), "pass_line_formula": formula,
         "pass_line_source_note": str(idea.get("pass_line_source_note") or ""),
         "fact_type": "client_operational" if idea.get("fact_type") == "client_operational" else "market",
         "assumptions_json": assumptions, "must_have": bool(idea.get("must_have")),
         "measure_name": str(idea.get("measure_name") or ""), "slider_min": _f(idea.get("slider_min")), "removed_reason": None,
         "measure_unit": str(idea.get("measure_unit") or ""), "slider_max": _f(idea.get("slider_max")), "locked_at": None,
         "links_reopened_for_trip": False, "order": order, "verdict": None, "benchmarks": []}
    refresh_line(h)
    return h


def _f(v):
    try:
        return None if v is None or v == "" else float(v)
    except (TypeError, ValueError):
        return None


def refresh_line(h: dict) -> None:
    try:
        h["line"] = float(line_of(h))
    except (FormulaError, ZeroDivisionError):
        h["line"] = float(h.get("pass_line_value") or 0.0)
    h["line_text"] = with_unit(h["line"], h["measure_unit"])


def fetch_benchmark(case: dict, h: dict, query: str, search, llm) -> None:
    cid = case["id"]
    files = db.rows("client_file", cid)
    chk = privacy.check_outbound(query, case, files)
    db.insert("outbound_query", cid, {"kind": "benchmark", "original": query, "sanitised": chk["sanitised"],
                                      "removed_terms_json": chk["removed"], "blocked": bool(chk["blocked"]),
                                      "edited_by_consultant": False, "idea": h["code"]})
    if chk["blocked"]:
        log(cid, "rule_engine", "query_blocked", 3, f"Blocked a search that contained a private term: "
                                                     f"{', '.join(chk['blocked'])}", {"query": chk["sanitised"], "removed": chk["removed"]})
        return
    log(cid, "rule_engine", "query_checked", 3,
        f"Checked the benchmark search for {h['code']}. It contains no private terms.",
        {"query": chk["sanitised"], "removed": chk["removed"]})
    results = search.benchmark(h["code"], chk["sanitised"])
    for r in results[:1]:
        e = evidence.create(cid, "benchmark", need_ref=f"bench:{h['code']}", found_in=r.get("group") or "open_web",
                            **_src_fields(r))
        out = llm.run("READ_SOURCE", r.get("seed_id") or r.get("url", ""), read_payload(case, e, [h]))
        e["figures_json"] = evidence.clean_figures(out.get("figures") or [], e["text"], web=True)
        evidence.apply_describe(e, out.get("describe") or {})
        evidence.grade_tier(e, case, db.rows("plan_item", cid))
        cj = e["credibility_json"]
        d = cj.get("describe") or {}
        cj["traced"] = bool(d.get("method_cited") or d.get("original_source_named") or cj.get("tier") == 1)
        cj["method_cited"] = bool(d.get("method_cited"))
        cj["original_source_name"] = d.get("original_source_name") or ""
        rm = config.ruleset_thresholds()["recency_months"]
        from .engine.credibility import recency
        rec = recency(e.get("data_as_of", ""), e.get("published_date", ""), int(rm.get(h["recency_category"], 36)))
        cj["recency_ok"], cj["recency_actual"] = rec["recency_ok"], rec["recency_actual"]
        e.update(status="pass_line_source", bucket="reference", original_group_id=e["id"])
        best = next((i for i, f in enumerate(e["figures_json"]) if f.get("verified")), 0)
        e["links"] = [{"id": evidence.next_link_id(), "hypothesis_code": h["code"], "figure_index": best,
                       "confirmed": True, "case_id": cid, "evidence_id": e["id"], "role": "sets_pass_line",
                       "proposed_by": "rule_engine"}]
        evidence.save(e)
        hh = next(x for x in db.rows("hypothesis", cid) if x["code"] == h["code"])
        hh["benchmarks"] = hh.get("benchmarks", []) + [e["id"]]
        db.put("hypothesis", hh)
        from .engine.credibility import TIER_LABELS
        log(cid, "rule_engine", "benchmark_graded", 3,
            f"Found a benchmark for the {h['code']} target. Source quality: "
            f"{TIER_LABELS.get(cj.get('tier'), 'Unverified')}; date: {cj['recency_actual']}", {"evidence_id": e["id"]})
        return
    log(cid, "rule_engine", "benchmark_missing", 3,
        f"Couldn't find a benchmark for the {h['code']} target. Check the target yourself before you lock it.")


def _src_fields(r: dict) -> dict:
    return {k: r.get(k, "") for k in ("title", "url", "domain", "publisher", "source_name", "published_date",
                                      "data_as_of", "text", "seed_id", "script_tag")} | {"simulated": bool(r.get("simulated", True))}


def read_payload(case: dict, e: dict, ideas: list[dict]) -> dict:
    from .search.text_window import window
    return {"title": e.get("title", ""), "url": e.get("url", ""), "publisher": e.get("publisher", ""),
            "published_date": e.get("published_date", ""),
            "text": privacy.mask_for_model(window(e.get("text", ""), config.rules()["limits"]["max_page_chars"]), case),
            "ideas": [{"code": h["code"], "measure": h["measure_name"], "unit": h["measure_unit"]} for h in ideas]}


# ------------------------------------------------------------------ step 3: set the targets
EDITABLE = ("text", "pass_line_value", "pass_line_formula", "must_have", "tolerance_pct", "measure_name",
            "measure_unit", "measure_definition", "fact_type", "comparator", "assumptions_json", "slider_min",
            "slider_max", "pass_line_source_note", "pass_line_source_type", "recency_category")


def edit_hypotheses(case: dict, rows: list[dict]) -> None:
    if done_map(case)[3]:
        raise gate("The targets are locked, so they can't be changed now.")
    require_step(case, 3)
    if not isinstance(rows, list):
        raise ApiError(400, "Send a list of the ideas to change.")
    hyps = {h["code"]: h for h in db.rows("hypothesis", case["id"])}
    changes = []
    for row in rows:
        h = hyps.get(row.get("code"))
        if not h:
            raise ApiError(400, f"There's no idea {row.get('code')} in this case.")
        if "removed_reason" in row:
            reason = (row.get("removed_reason") or "").strip()
            if row.get("removed_reason") is None:
                if h.get("removed_reason"):
                    h["removed_reason"] = None
                    changes.append(f"put back {h['code']}")
            elif not reason:
                raise ApiError(400, "Give a short reason for removing this idea.")
            else:
                reason = reason[0].upper() + reason[1:]
                h["removed_reason"] = reason
                changes.append(f"removed {h['code']} ({reason})")
        for k in EDITABLE:
            if k not in row or row[k] == h.get(k):
                continue
            v = row[k]
            if k == "pass_line_formula" and v:
                try:
                    check_formula(v, [a["name"] for a in (row.get("assumptions_json") or h.get("assumptions_json") or [])])
                except FormulaError as e:
                    raise ApiError(400, f"{e}. Use numbers, the named assumptions, + - * / and brackets.")
            if k in ("pass_line_value", "tolerance_pct", "slider_min", "slider_max") and v is not None and v != "":
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    raise ApiError(400, "Type the target as a number.")
            h[k] = v
            if k == "pass_line_value":
                h["pass_line_formula"] = None if "pass_line_formula" not in row else h.get("pass_line_formula")
            changes.append(_change_text(h, k))
        refresh_line(h)
        db.put("hypothesis", h)
    if changes:
        log(case["id"], "consultant", "plan_edited", 3, "Edited the ideas: " + "; ".join(changes), {"changes": changes})


def _change_text(h: dict, k: str) -> str:
    if k in ("pass_line_value", "pass_line_formula"):
        refresh_line(h)
        return f"changed the {h['code']} target to {h['line_text']}"
    if k == "must_have":
        return f"marked {h['code']} as {'critical' if h['must_have'] else 'not critical'}"
    if k == "tolerance_pct":
        return f"set the {h['code']} close-call margin to {h['tolerance_pct']:g}%"
    return f"edited {h['code']} ({k.replace('_', ' ')})"


def lock_plan(case: dict, body: dict) -> dict:
    require_step(case, 3)
    if done_map(case)[3]:
        j = running(case["id"], "route")
        if j:
            return j[0]
        raise gate("The targets are already locked.")
    if running(case["id"], "plan"):
        raise gate("The ideas are still being drafted. Wait a moment.")
    if not (body or {}).get("ticked"):
        raise gate("Tick the box to confirm the targets first.")
    kept = [h for h in db.rows("hypothesis", case["id"]) if not h.get("removed_reason")]
    if not kept:
        raise gate("Keep at least one idea to test.", ["Keep an idea"])
    if not any(h["must_have"] for h in kept):
        raise gate("Mark at least one idea as critical first.", ["Mark a critical idea"])
    missing = []
    for h in kept:
        if h.get("line") is None or not h.get("measure_unit") or not h.get("measure_name") or not h.get("fact_type") \
                or not h.get("pass_line_source_type"):
            missing.append(h["code"])
    if missing:
        raise gate("Give every idea a target, a unit, a measure and where the target came from: " + ", ".join(missing) + ".",
                   missing)
    t = now_iso()
    for h in db.rows("hypothesis", case["id"]):
        h["locked_at"] = t
        db.put("hypothesis", h)
    rs = db.one("ruleset", case["id"])
    rs["locked_at"] = t
    db.put("ruleset", rs)
    touch(case, settings={"plan_locked_at": t})
    log(case["id"], "consultant", "plan_locked", 3, f"Locked the targets for {len(kept)} ideas. Targets, critical ideas "
                                                    "and the quality check can no longer change.")
    return start_route(case)


def start_route(case: dict) -> dict:
    return start_job(case["id"], "route", lambda job: _route_job(job, case["id"]),
                     progress={"label": "Writing search queries", "done": 0, "total": 0})


def _route_job(job, cid: int) -> None:
    case = db.case_get(cid)
    llm = get_llm(case)
    hyps = sorted([h for h in db.rows("hypothesis", cid) if not h.get("removed_reason")], key=lambda h: h["order"])
    files = [f for f in db.rows("client_file", cid) if f["kind"] == "initial"]
    out = llm.run("ROUTE_NEEDS", "", {
        "ideas": [{"code": h["code"], "text": h["text"], "measure": h["measure_name"], "unit": h["measure_unit"],
                   "fact_type": h["fact_type"]} for h in hyps],
        "files": [{"filename": f["filename"], "text": privacy.mask_for_model(f["preview"][:4000], case)} for f in files],
        "country": case["country"], "industry": case["industry"]})
    db.delete_all("need", cid)
    codes = {h["code"] for h in hyps}
    fid = {f["filename"]: f for f in files}
    n = 0
    for nd in out.get("needs") or []:
        if nd.get("idea") not in codes or not str(nd.get("text") or "").strip():
            continue
        n += 1
        route = nd.get("route") if nd.get("route") in ("desk", "client", "expert") else "desk"
        cov = nd.get("coverage") if nd.get("coverage") in ("answered_by_client_file", "partly", "not_covered") else "not_covered"
        f = fid.get(nd.get("covered_by_file") or "")
        loc = str(nd.get("covered_locator") or "")
        if cov != "not_covered" and (not f or loc not in parse.segments(f["preview"])):
            cov, f, loc = "not_covered", None, ""              # the cited place doesn't exist: not covered
        if route == "desk" and cov != "not_covered":
            route = "client"
        status = "answered" if cov == "answered_by_client_file" else "open"
        db.insert("need", cid, {"hypothesis_code": nd["idea"], "route": route, "covered_by_file_id": f["id"] if f else None,
                                "coverage_note": str(nd.get("coverage_note") or "") if cov == "partly" else "",
                                "queries_json": [], "text": str(nd["text"]).strip(), "ref": f"N{n}", "coverage": cov,
                                "covered_locator": loc if f else "", "status": status})
    needs = db.rows("need", cid)
    if not needs:
        raise JobError("We couldn't work out where the answers will come from. Try again.")
    log(cid, "llm", "needs_routed", 4, f"Listed {len(needs)} things to find out and checked which ones the client's "
                                       "files already answer")
    log(cid, "rule_engine", "locators_checked", 4, "Checked that every cited place in the client's files exists")
    desk = [nd for nd in needs if nd["route"] == "desk"]
    job.progress(total=len(desk))
    all_files = db.rows("client_file", cid)
    for i, nd in enumerate(desk, 1):
        h = next(x for x in hyps if x["code"] == nd["hypothesis_code"])
        chk_need = privacy.check_outbound(nd["text"], case, all_files)
        q = llm.run("GENERATE_QUERIES", nd["ref"], {"need": chk_need["sanitised"], "idea": h["text"],
                                                    "measure": h["measure_name"], "country": case["country"]})
        query = str(((q.get("queries") or [""])[0]) or chk_need["sanitised"])[:300]
        chk = privacy.check_outbound(query, case, all_files)
        nd["queries_json"] = [{"original": nd["text"], "sanitised": chk_need["sanitised"], "removed": chk_need["removed"] + chk["removed"],
                               "query": chk["sanitised"], "blocked": chk["blocked"]}]
        db.put("need", nd)
        db.insert("outbound_query", cid, {"kind": "search", "original": query, "sanitised": chk["sanitised"],
                                          "removed_terms_json": chk["removed"], "blocked": bool(chk["blocked"]),
                                          "edited_by_consultant": False, "need": nd["ref"]})
        if chk["blocked"]:
            log(cid, "rule_engine", "query_blocked", 4, f"Blocked a search that contained a private term: "
                                                         f"{', '.join(chk['blocked'])}. Edit the search for {nd['ref']}.")
        job.progress(done=i)
    if not db.rows("plan_item", cid):
        build_source_plan(case, out.get("sources") or [])
    build_requests(case)
    log(cid, "rule_engine", "outbound_sanitised", 4, "Removed the client's name and private numbers from every search "
                                                     "and request")
    touch(case, current_step=4, settings={"route_done": now_iso()})


def build_source_plan(case: dict, suggested: list[dict]) -> None:
    from .engine.credibility import tier_for
    cid = case["id"]
    if case.get("sample"):
        rows = samples.pack(case["sample"])["case"].get("source_plan") or []
    else:
        rows = [{"source_name": s.get("source_name") or s.get("domain"), "domain": str(s.get("domain") or "").lower(),
                 "origin_type": "open_web", "included": True, "removed_reason": None, "stated_by_consultant": False}
                for s in suggested[:6] if s.get("domain")]
        rows += [{"source_name": "Firm research archive", "domain": "", "origin_type": "firm_archive", "included": True,
                  "removed_reason": None, "stated_by_consultant": False},
                 {"source_name": "Open web search", "domain": "", "origin_type": "open_web", "included": True,
                  "removed_reason": None, "stated_by_consultant": False,
                  "tier_reason": "Each result is graded by its own domain"},
                 {"source_name": "Social media and forums", "domain": "reddit.com", "origin_type": "open_web",
                  "included": False, "removed_reason": "Not credible enough for a client decision",
                  "stated_by_consultant": False}]
    for r in rows:
        r = dict(r)
        if r.get("stated_by_consultant"):
            r["tier_reason"] = f"Added to the source plan by the consultant as Tier {r['tier']}: {r.get('tier_reason', '')}"
        elif r.get("source_name") == "Open web search" or (r["origin_type"] == "open_web" and not r.get("domain")):
            r["tier"], r["tier_reason"] = None, r.get("tier_reason") or "Each result is graded by its own domain"
        else:
            r["tier"], r["tier_reason"] = tier_for(r.get("domain", ""), r["origin_type"], config.registry(),
                                                   case.get("country", ""), case.get("industry", ""))
        db.insert("plan_item", cid, {k: r.get(k) for k in ("origin_type", "source_name", "tier_reason", "included", "domain",
                                                           "tier", "stated_by_consultant", "removed_reason")})


def build_requests(case: dict) -> None:
    cid = case["id"]
    needs = db.rows("need", cid)
    files = {f["id"]: f for f in db.rows("client_file", cid)}
    have, gaps = [], []
    for nd in needs:
        if nd["coverage"] in ("answered_by_client_file", "partly") and nd.get("covered_by_file_id") in files:
            f = files[nd["covered_by_file_id"]]
            have.append(f"- {f['filename']} ({nd['covered_locator']}): {nd['text']}" + (" (partly)" if nd["coverage"] == "partly" else ""))
    for nd in needs:
        if nd["route"] == "client" and nd["coverage"] != "answered_by_client_file":
            gaps.append(nd["text"] + (f" Missing: {nd['coverage_note']}" if nd.get("coverage_note") else ""))
    all_files = list(files.values())
    client = "What we already have from you\n" + ("\n".join(have) if have else "- Nothing yet.") + "\n\nWhat we still need\n"
    client += "\n".join(f"{i}. {g}" for i, g in enumerate(gaps, 1)) if gaps else "Nothing: your files already answer our questions."
    removed, blocked, qs = [], [], []
    for nd in needs:
        if nd["route"] != "expert":
            continue
        chk = privacy.check_outbound(nd["text"], case, all_files)
        removed += chk["removed"]
        blocked += chk["blocked"]
        qs.append(chk["sanitised"])
    expert = "Questions for experts\n" + ("\n".join(f"{i}. {q}" for i, q in enumerate(qs, 1)) if qs else "None needed.")
    touch(case, settings={"requests": {"client": client, "client_gaps": len(gaps), "client_have": len(have),
                                       "expert": expert, "expert_removed": sorted(set(removed)),
                                       "expert_blocked": sorted(set(blocked))}})


# ------------------------------------------------------------------ step 4: plan the research
def edit_query(case: dict, ref: str, query: str) -> None:
    if done_map(case)[4]:
        raise gate("The requests are marked as sent, so the searches can't change now.")
    require_step(case, 4)
    nd = next((n for n in db.rows("need", case["id"]) if n["ref"] == ref), None)
    if not nd:
        raise ApiError(404, "That search isn't in this case.")
    query = str(query or "").strip()
    if not query:
        raise ApiError(400, "Type the search first.")
    chk = privacy.check_outbound(query, case, db.rows("client_file", case["id"]))
    if chk["blocked"]:
        raise gate(f"This search still contains a private term: {', '.join(chk['blocked'])}. Remove it and save again.",
                   chk["blocked"])
    q = (nd.get("queries_json") or [{}])[0]
    q.update(query=chk["sanitised"], blocked=[], removed=sorted(set((q.get("removed") or []) + chk["removed"])))
    q.setdefault("original", nd["text"])
    q.setdefault("sanitised", nd["text"])
    nd["queries_json"] = [q]
    db.put("need", nd)
    db.insert("outbound_query", case["id"], {"kind": "search", "original": query, "sanitised": chk["sanitised"],
                                             "removed_terms_json": chk["removed"], "blocked": False,
                                             "edited_by_consultant": True, "need": ref})
    log(case["id"], "consultant", "query_edited", 4, f"Edited the search for {ref}. It contains no private terms.")


def edit_source_plan(case: dict, rows: list[dict]) -> None:
    if done_map(case)[4]:
        raise gate("The requests are marked as sent, so the sources can't change now.")
    require_step(case, 4)
    from .engine.credibility import tier_for
    items = {p["id"]: p for p in db.rows("plan_item", case["id"])}
    for r in rows if isinstance(rows, list) else [rows]:
        if r.get("id") in items:
            p = items[r["id"]]
            inc = bool(r.get("included"))
            if not inc and not str(r.get("removed_reason") or "").strip():
                raise ApiError(400, "Give a short reason for leaving out this source.")
            p["included"] = inc
            p["removed_reason"] = None if inc else str(r.get("removed_reason")).strip()
            db.put("plan_item", p)
        elif r.get("source_name"):
            try:
                tier = int(r.get("stated_tier") or 3)
            except (TypeError, ValueError):
                raise ApiError(400, "Choose a source quality for the new source.")
            if tier not in (1, 2, 3, 4):
                raise ApiError(400, "Choose a source quality for the new source.")
            reason = str(r.get("reason") or r.get("add_reason") or "").strip() or "Added by the consultant"
            dom = str(r.get("domain") or "").strip().lower()
            dom = dom.split("://")[-1].split("/")[0].removeprefix("www.")
            db.insert("plan_item", case["id"], {"origin_type": "open_web", "source_name": str(r["source_name"]).strip(),
                                                "tier_reason": f"Added to the source plan by the consultant as Tier {tier}: {reason}",
                                                "included": True, "domain": dom, "tier": tier, "stated_by_consultant": True,
                                                "removed_reason": None})
        else:
            raise ApiError(400, "Name the source you want to add.")
    log(case["id"], "consultant", "source_plan_edited", 4, "Edited the sources")


def mark_requests_sent(case: dict, body: dict) -> dict:
    require_step(case, 4)
    if done_map(case)[4]:
        j = running(case["id"], "collect") or running(case["id"], "clean")
        if j:
            return j[0]
        raise gate("The requests are already marked as sent.")
    if running(case["id"], "route"):
        raise gate("The searches are still being written. Wait a moment.")
    if not (body or {}).get("reviewed"):
        raise gate("Tick \"I've checked what goes out\" first.")
    blocked = [n["ref"] for n in db.rows("need", case["id"]) for q in n.get("queries_json") or [] if q.get("blocked")]
    if blocked:
        raise gate("Some searches still contain a private term. Edit them first: " + ", ".join(blocked) + ".", blocked)
    t = now_iso()
    touch(case, settings={"step4_reviewed_at": t, "requests_marked_sent_at": t})
    log(case["id"], "consultant", "reviewed_outbound", 4, "Checked the answers, the sources and what goes out")
    log(case["id"], "consultant", "requests_marked_sent", 4,
        "Marked the client request and expert questions as sent. The tool sent nothing itself.")
    from .steps_gather import start_collect
    return start_collect(case)


def requests_view(case: dict) -> dict:
    s = settings_of(case)
    return {"requests": s.get("requests") or {}, "needs": db.rows("need", case["id"])}
