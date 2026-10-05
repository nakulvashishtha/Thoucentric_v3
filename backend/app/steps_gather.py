"""Steps 5 and 6: gathering the evidence and checking it. Both run on their own as background jobs."""
from __future__ import annotations

import os
import random
import time

from . import config, db, evidence, samples
from .core import gate, log, now_iso, running, start_job
from .engine import dedup, spotcheck
from .llm.interface import get_llm
from .search import get_search
from .state import done_map, require_step
from .steps_frame import _src_fields, read_file, read_payload, settings_of, touch

GROUPS = (("open_web", "Open web"), ("firm_archive", "Firm archive"), ("paid_db", "Paid or simulated databases"),
          ("client_file", "Client files"), ("expert_note", "Expert notes"))


def _pace() -> None:
    """Stored answers arrive instantly; a short pause per item lets the screen show the work happening."""
    d = float(os.environ.get("FIXTURE_PACE", "0.12"))
    if d > 0:
        time.sleep(d)


# ------------------------------------------------------------------ step 5: gathering evidence
def start_collect(case: dict) -> dict:
    groups = {k: {"label": label, "done": 0, "total": 0, "state": "waiting"} for k, label in GROUPS}
    return start_job(case["id"], "collect", lambda job: _collect_job(job, case["id"]),
                     progress={"label": "Collecting", "groups": groups, "pending": []})


def collect_start(case: dict) -> dict:
    require_step(case, 5)
    if done_map(case)[5]:
        raise gate("Collecting has already finished.")
    return start_collect(case)


def stop_collect(case: dict) -> dict:
    require_step(case, 5)
    if not running(case["id"], "collect"):
        if done_map(case)[5]:
            return {"ok": True}
        raise gate("Collecting isn't running.")
    touch(case, settings={"collect_stop_requested": True})
    log(case["id"], "consultant", "collect_stopped", 5, "Stopped collecting. Checking what has arrived.")
    return {"ok": True}


def _plan_allows(plan: list[dict]):
    excluded = [p["domain"] for p in plan if not p.get("included") and p.get("domain")]
    included_types = {p["origin_type"] for p in plan if p.get("included")}
    open_web_all = any(p.get("included") and p["origin_type"] == "open_web" and not p.get("domain") for p in plan)
    included_domains = [p["domain"] for p in plan if p.get("included") and p.get("domain")]

    def allowed(group: str, domain: str) -> bool:
        d = (domain or "").lower()
        if any(d == x or d.endswith("." + x) for x in excluded):
            return False
        if group != "open_web":
            return group in included_types
        return open_web_all or any(d == x or d.endswith("." + x) for x in included_domains)

    return allowed, included_types


def _collect_job(job, cid: int) -> None:
    case = db.case_get(cid)
    search = get_search(case)
    plan = db.rows("plan_item", cid)
    allowed, types = _plan_allows(plan)
    max_per = int(config.rules()["fast_demo"]["max_sources_per_need"])
    desk = [n for n in db.rows("need", cid) if n["route"] == "desk"]
    prog = dict(job.row["progress"])
    log(cid, "rule_engine", "collect_started", 5, "Started collecting evidence from the chosen sources")

    def stopped() -> bool:
        return bool(settings_of(case).get("collect_stop_requested"))

    def put(group, **kw):
        prog["groups"][group].update(kw)
        job.set_progress(dict(prog))

    is_stopped = False
    for group, label in GROUPS[:3]:
        if group not in types and group != "open_web":
            put(group, state="not in plan")
            continue
        if is_stopped or stopped():
            is_stopped = True
            put(group, state="stopped")
            continue
        put(group, state="searching")
        found = []
        for nd in desk:
            q = ((nd.get("queries_json") or [{}])[0]).get("query") or nd["text"]
            if ((nd.get("queries_json") or [{}])[0]).get("blocked"):
                continue
            for r in search.search(group, nd["ref"], q, max_per):
                if allowed(group, r.get("domain") or ""):
                    found.append((nd, r))
        put(group, total=len(found))
        n = 0
        for nd, r in found:
            if stopped():
                is_stopped = True
                break
            src = _src_fields(r)
            evidence.create(cid, group, need_ref=nd["ref"], **src)
            n += 1
            put(group, done=n)
            _pace()
        put(group, state="stopped" if is_stopped else "done", total=max(n, 0) if is_stopped else len(found))
        if n:
            log(cid, "rule_engine", "group_collected", 5, f"{label}: collected {n} items")

    # client files already received count as evidence
    files = [f for f in db.rows("client_file", cid) if f["kind"] == "initial"]
    needs = db.rows("need", cid)
    if files:
        put("client_file", state="reading", total=len(files))
        for i, f in enumerate(files, 1):
            add_file_evidence(case, f, needs)
            put("client_file", done=i)
            _pace()
        put("client_file", state="done")
        log(cid, "client", "client_files_used", 5, f"Added the {len(files)} client files you already had as evidence")
    else:
        put("client_file", state="done")

    # expert notes: simulated notes arrive for sample cases; pasted replies arrive the same way
    notes = search.expert_notes() if hasattr(search, "expert_notes") else []
    received = 0
    for r in notes:
        evidence.create(cid, "expert_note", need_ref=r.get("need_ref", ""), **_src_fields(r))
        received += 1
        put("expert_note", done=received, total=len(notes), state="receiving")
        _pace()
    if received:
        log(cid, "expert", "expert_notes_received", 5,
            f"Received {received} expert note{'s' if received != 1 else ''}" + (" (sample data, simulated)" if case.get("sample") else ""))
    for f in db.rows("client_file", cid):
        if f["kind"] in ("followup", "expert_note") and not f.get("trip_id") and not f.get("ingested"):
            add_file_evidence(case, f, needs)
    covered_expert = {r.get("need_ref") for r in notes}
    pending = []
    for nd in needs:
        if nd["route"] == "client" and nd["coverage"] != "answered_by_client_file":
            who, origin, label = "the client", "client_file", "Awaiting the client"
        elif nd["route"] == "expert" and nd["ref"] not in covered_expert:
            who, origin, label = "an expert", "expert_note", "Awaiting an expert"
        else:
            continue
        e = evidence.create(cid, origin, need_ref=nd["ref"], status="pending", bucket="pending", source_name=label,
                            title=f"{label}: {nd['text']}")
        pending.append({"id": e["id"], "need": nd["ref"], "text": nd["text"], "from": who})
        nd["status"] = "pending"
        db.put("need", nd)
        log(cid, "rule_engine", "pending", 5, f"Still waiting for {e['id']} from {who}: {nd['text']}")
    if not received and not any(p["from"] == "an expert" for p in pending):
        put("expert_note", state="done")
    prog["pending"] = pending
    prog["label"] = "Finished"
    job.set_progress(dict(prog))
    touch(case, current_step=6, settings={"collect_finished_at": now_iso(), "collect_stopped": is_stopped})
    with db.lock():
        cur = db.case_get(cid)
        cur["settings_json"].pop("collect_stop_requested", None)
        db.case_put(cur)
    log(cid, "system", "collect_finished", 5, "Finished collecting. Checking the evidence now.")
    start_clean(case)


def add_file_evidence(case: dict, f: dict, needs: list[dict], trip_id: int | None = None) -> dict:
    """A client file or pasted note becomes one evidence item. A person always decides on it."""
    need_ref = ""
    for want in ("answered_by_client_file", "partly"):
        for nd in needs:
            if nd.get("covered_by_file_id") == f["id"] and nd["coverage"] == want:
                need_ref = need_ref or nd["ref"]
    d = f.get("describe") or {}
    period = next((g.get("period") for g in f.get("figures") or [] if g.get("period")), "")
    origin = "expert_note" if f["kind"] == "expert_note" else "client_file"
    reply = f["kind"] != "initial"
    e = evidence.create(case["id"], origin, need_ref=need_ref, title=f["filename"], text=f["preview"],
                        source_name=(f"Client reply: {f['filename']}" if reply and origin == "client_file" else
                                     "Expert note" if origin == "expert_note" else f"Client file: {f['filename']}"),
                        publisher="Client" if origin == "client_file" else "Expert", file_id=f["id"],
                        figures_json=list(f.get("figures") or []), simulated=bool(case.get("sample")), trip_id=trip_id,
                        published_date=str(d.get("published_date") or period or ""),
                        data_as_of=str(d.get("data_as_of") or ("" if d else period) or ""))
    if d:
        evidence.apply_describe(e, d)
        evidence.save(e)
    f["ingested"] = True
    db.put("client_file", f)
    return e


# ------------------------------------------------------------------ step 6: checking the evidence
def start_clean(case: dict) -> dict:
    return start_job(case["id"], "clean", lambda job: _clean_job(job, case["id"]),
                     progress={"label": "Reading sources", "done": 0, "total": 0, "stage": "read"})


def clean_run(case: dict) -> dict:
    require_step(case, 6)
    if done_map(case)[6]:
        raise gate("The evidence has already been checked.")
    return start_clean(case)


def _clean_job(job, cid: int) -> None:
    case = db.case_get(cid)
    llm = get_llm(case)
    plan = db.rows("plan_item", cid)
    hyps = {h["code"]: h for h in db.rows("hypothesis", cid)}
    kept = {c: h for c, h in hyps.items() if not h.get("removed_reason")}
    th = (db.one("ruleset", cid) or {}).get("thresholds_json") or config.ruleset_thresholds()
    fr = db.one("frame", cid) or {}
    needs = {n["ref"]: n for n in db.rows("need", cid)}
    items = [e for e in evidence.all_items(cid) if e["origin_type"] != "benchmark" and e["status"] == "pending_clean"
             and not e.get("trip_id")]
    for e in items:                                   # a re-run starts from a clean slate
        e.update(duplicate_of=None, duplicate_rule="", original_group_id="", links=[], checklist_json=[])
    # 1. exact copies are found before reading, so they are never read twice
    copies = dedup.exact_copies([e for e in items if e["origin_type"] not in ("client_file", "expert_note")])
    for e in items:
        if e["id"] in copies:
            e.update(status="duplicate", bucket="duplicate", duplicate_rule=dedup.RULE_EXACT, duplicate_of=copies[e["id"]])
            evidence.grade_tier(e, case, plan)
            e["credibility_json"]["traced"] = e["credibility_json"].get("tier") == 1
            evidence.save(e)
    if copies:
        log(cid, "rule_engine", "copies_found", 6, f"Found {len(copies)} exact cop{'ies' if len(copies) != 1 else 'y'} "
                                                   "before reading, so they weren't read twice")
    to_read = [e for e in items if e["id"] not in copies]
    job.progress(total=len(to_read), done=0)
    # 2. the fast model reads each source once (figures with quotes, plus a description of the source)
    files = {f["id"]: f for f in db.rows("client_file", cid)}
    for i, e in enumerate(to_read, 1):
        if e["origin_type"] == "client_file" and e.get("file_id") in files:
            pass                                      # read at step 1; figures already checked word for word
        elif not (e.get("text") or "").strip():
            e["status"] = "unreadable"
        else:
            key = e.get("seed_id") or e.get("url") or e["id"]
            idea_list = list(kept.values())
            out = llm.run("READ_SOURCE", key, read_payload(case, e, idea_list))
            e["figures_json"] = evidence.clean_figures(out.get("figures") or [], e["text"], web=e["origin_type"] != "expert_note"
                                                       or "[line" not in e["text"])
            evidence.apply_describe(e, out.get("describe") or {})
        evidence.save(e)
        job.progress(done=i)
        _pace()
    readable = [e for e in to_read if e["status"] != "unreadable"]
    log(cid, "llm", "sources_read", 6, f"Read {len(readable)} sources and pulled out each figure with its quote")
    figs = [f for e in readable for f in e["figures_json"] if f.get("kind") == "reported"]
    ok = sum(1 for f in figs if f.get("verified"))
    log(cid, "rule_engine", "quotes_verified", 6, f"Found {ok} of {len(figs)} figures word for word in their sources. "
                                                  f"{len(figs) - ok} couldn't be found and won't count in the tests.")
    unread = [e for e in to_read if e["status"] == "unreadable"]
    if unread:
        log(cid, "rule_engine", "unreadable", 6, f"Couldn't read {len(unread)} source(s): "
                                                 f"{', '.join(e['id'] for e in unread)}. They stay listed.")
    # 3. copies traced to their original (named source with a matching figure, or near-identical text)
    for e in readable:
        evidence.grade_tier(e, case, plan)
    web_like = [e for e in readable if e["origin_type"] not in ("client_file", "expert_note")]
    orig_of, rules = dedup.group([{"id": e["id"], "seq": e["seq"], "title": e["title"], "publisher": e["publisher"],
                                   "tier": e["credibility_json"].get("tier"), "text": e["text"], "figures": e["figures_json"],
                                   "describe": e["credibility_json"].get("describe") or {}} for e in web_like],
                                 float(config.rules()["dedup"]["similarity_threshold"]))
    byid = {e["id"]: e for e in items}
    for eid, oid in orig_of.items():
        e = byid[eid]
        e.update(status="duplicate", bucket="duplicate", duplicate_rule=rules[eid], duplicate_of=oid)
        d = e["credibility_json"].get("describe") or {}
        e["credibility_json"].update(method_cited=bool(d.get("method_cited")), original_source_name=d.get("original_source_name") or "",
                                     traced=bool(d.get("method_cited") or d.get("original_source_named") or e["credibility_json"].get("tier") == 1))
    for eid, first in copies.items():                 # an exact copy points at the original of what it copied
        byid[eid]["duplicate_of"] = orig_of.get(first, first)
    for e in items:
        e["original_group_id"] = e["duplicate_of"] or e["id"] if e["status"] != "pending" else ""
        if e["status"] == "duplicate" and byid.get(e["duplicate_of"], {}).get("status") == "duplicate":
            e["duplicate_of"] = byid[e["duplicate_of"]]["duplicate_of"]
            e["original_group_id"] = e["duplicate_of"]
    if orig_of:
        log(cid, "rule_engine", "deduplicated", 6, f"Traced {len(orig_of)} cop{'ies' if len(orig_of) != 1 else 'y'} to "
                                                   "their original source. Each original counts once.")
    # 4. links proposed by the model, derived figures computed in code
    originals = [e for e in readable if e["status"] != "duplicate"]
    for e in originals:
        key = e["seed_id"] if e.get("seed_id") else f"file:{e['title']}" if e["origin_type"] in ("client_file", "expert_note") and e.get("file_id") else (e.get("url") or e["id"])
        nd = needs.get(e.get("need_ref") or "")
        default = nd["hypothesis_code"] if nd and nd["hypothesis_code"] in kept else None
        proposal = _link_proposal(llm, case, e, key, kept)
        formulas = evidence.apply_links(e, proposal, kept, default)
        if formulas:
            log(cid, "rule_engine", "derived", 6, f"Worked out {len(formulas)} figure(s) for {e['id']}: "
                                                  f"{'; '.join(formulas)}. It's checked when you accept the item.")
    # 5. grade and run the quality check
    job.progress(label="Running the checklist", stage="checklist")
    files_l = list(files.values())
    passed = flagged = 0
    for e in originals:
        evidence.grade_full(e, case, plan, kept, th, fr.get("client_belief", ""))
    for e in originals:
        auto = evidence.run_checklist(e, originals, kept, th, case, files_l)
        e["status"], e["bucket"] = ("auto_approved", "auto") if auto else ("needs_decision", "decision")
        passed += auto
        flagged += not auto
    for e in items:
        evidence.save(e)
    log(cid, "rule_engine", "checklist_run", 6, f"Ran the quality check: {passed} passed, {flagged} need your call")
    # 6. the quick double-check picks
    auto_ids = [e["id"] for e in originals if e["status"] == "auto_approved"]
    seed = samples.pack(case["sample"])["seed"] if case.get("sample") else random.randint(1, 9999)
    sc = th.get("spot_check") or {"fraction": 0.2, "minimum": 2}
    picks = spotcheck.pick(auto_ids, seed, sc.get("fraction", 0.2), sc.get("minimum", 2))
    for e in originals:
        if e["id"] in picks:
            e["spot_check_selected"] = True
            evidence.save(e)
    if picks:
        log(cid, "rule_engine", "spot_check_picked", 6, f"Picked {len(picks)} of the {len(auto_ids)} items that passed for an "
                                                        f"optional quick double-check: {', '.join(picks)} (seed {seed})",
            {"seed": seed, "picks": picks})
    else:
        log(cid, "rule_engine", "spot_check_picked", 6, "No item passed the quality check, so there is nothing to "
                                                        "double-check.", {"seed": seed, "picks": []})
    job.progress(done=len(to_read))
    touch(case, current_step=7, settings={"clean_finished_at": now_iso(), "spot_seed": seed})


def _link_proposal(llm, case: dict, e: dict, key: str, kept: dict) -> dict:
    payload = {"item": {"id": e["id"], "title": e["title"], "need": e.get("need_ref", ""),
                        "figures": [{"index": i, "value": f.get("value"), "low": f.get("low"), "high": f.get("high"),
                                     "unit": f.get("unit"), "period": f.get("period"), "quote": f.get("quote_span")}
                                    for i, f in enumerate(e["figures_json"]) if f.get("verified")]},
               "ideas": [{"code": h["code"], "text": h["text"], "measure": h["measure_name"], "unit": h["measure_unit"]}
                         for h in kept.values()]}
    if not payload["item"]["figures"]:
        return {"links": [], "derivations": []}
    if not llm.live and not llm.has("LINK_EVIDENCE", key):
        return {"links": [], "derivations": []}
    return llm.run("LINK_EVIDENCE", key, payload)


def ingest_file_now(case: dict, f: dict, trip: dict | None = None) -> dict:
    """A reply that arrives after the checks ran: read it, check its quotes, link it and grade it right away."""
    cid = case["id"]
    llm = get_llm(case)
    hyps = {h["code"]: h for h in db.rows("hypothesis", cid) if not h.get("removed_reason")}
    th = (db.one("ruleset", cid) or {}).get("thresholds_json") or config.ruleset_thresholds()
    step = 9 if trip else 7
    if (case.get("settings_json") or {}).get("ai_reads_client_files", True) and not f.get("read"):
        f = read_file(case, f, llm, step=step)
    needs = db.rows("need", cid)
    e = add_file_evidence(case, f, needs, trip_id=trip["id"] if trip else None)
    if trip:
        pend = next((n for n in needs if n["hypothesis_code"] == trip["hypothesis_code"] and n["route"] in ("client", "expert")
                     and n["coverage"] != "answered_by_client_file"), None)
        e["need_ref"] = pend["ref"] if pend else ""
        for p in evidence.all_items(cid):
            if p["status"] == "pending" and pend and p["need_ref"] == pend["ref"]:
                p["decision_reason"] = f"Answered by the trip {trip['n']} reply ({e['id']})"
                evidence.save(p)
        log(cid, "client" if e["origin_type"] == "client_file" else "expert", "trip_reply", 9,
            f"The client's reply arrived as {e['id']} ({f['filename']})" if e["origin_type"] == "client_file" else
            f"The expert's reply arrived as {e['id']} ({f['filename']})")
    key = f"file:{f['filename']}"
    default = trip["hypothesis_code"] if trip else None
    proposal = _link_proposal(llm, case, e, key, hyps)
    if trip:                                          # only the reopened idea's links can change
        proposal["links"] = [lk for lk in proposal.get("links") or [] if lk.get("idea") == trip["hypothesis_code"]]
    formulas = evidence.apply_links(e, proposal, hyps, default)
    if formulas:
        log(cid, "rule_engine", "derived", step, f"Worked out {len(formulas)} figure(s) for {e['id']}: "
                                                 f"{'; '.join(formulas)}. It's checked when you accept the item.")
    e["original_group_id"] = ""
    evidence.grade_full(e, case, db.rows("plan_item", cid), hyps, th, (db.one("frame", cid) or {}).get("client_belief", ""))
    if not (e["credibility_json"].get("describe")):
        e["credibility_json"].pop("describe", None)
        for k in ("method_cited", "original_source_name"):
            e["credibility_json"].pop(k, None)
    evidence.run_checklist(e, evidence.all_items(cid), hyps, th, case, db.rows("client_file", cid))
    e["status"], e["bucket"] = "needs_decision", ("trip" if trip else "decision")
    evidence.save(e)
    return e
