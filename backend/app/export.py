"""Exports: Markdown summary and full JSON (which can be imported again). The printable page is the UI's print view."""
from __future__ import annotations

import json

from . import db
from .core import activity
from .engine.verdict import CONF_WORDS, RESULT_WORDS

PRINCIPLE = ("_The tool does the searching, sorting and maths and shows its working. You check what matters and make "
             "the call._")


def markdown(b: dict) -> str:
    c = b["case"]
    L = [f"# Summary: {c['title']}", "", PRINCIPLE, "",
         f"**Client:** {c['client_name']} · **Country:** {c['country']} · **Industry:** {c['industry']} · "
         f"**Function:** {c['function']}", "", f"**The ask, as the client wrote it:** {c['raw_ask']}", ""]
    fr = b.get("frame")
    if fr:
        L += ["## The question", f"- What they believe (to be tested): {fr['client_belief']}",
              f"- The decision they face: {fr['decision']}",
              f"- How we compare numbers: {fr['case_measure_name']} ({fr['case_measure_definition']})", ""]
    kept = [h for h in b["hypotheses"] if not h.get("removed_reason")]
    if kept:
        L += ["## Results", "", "| Idea | Target | Result | Confidence | Evidence |", "|---|---|---|---|---|"]
        for h in kept:
            v = h.get("verdict")
            res = RESULT_WORDS[v["result"]] if v else "Not tested yet"
            conf = CONF_WORDS.get(v["confidence"], "") if v else ""
            ev = ", ".join(v["evidence_ids"]) if v and v["evidence_ids"] else "none"
            tgt = f"{'at least' if h['comparator'] == '>=' else 'at most'} {h['line_text']}"
            L.append(f"| {h['code']} {h['text']}{' (critical)' if h['must_have'] else ''} | {tgt} | {res} | {conf} | {ev} |")
        L.append("")
    ov = b.get("overall")
    if ov:
        L += [f"**The answer:** {ov['label']}. {ov['rule_applied']}", ""]
    s = b.get("summary")
    if s and s.get("sentences"):
        L += ["## What the evidence says (each line cites its evidence)"]
        L += [f"- {x['text']} [{', '.join(x['evidence_ids'])}]" for x in s["sentences"]]
        L.append("")
    if s and s.get("unknowns"):
        L += ["## Still unknown"] + [f"- {u['idea']}: {u['text']}" for u in s["unknowns"]] + [""]
    k = b["counts"]
    L += ["## Evidence", f"- Collected: {k['collected']} · separate sources: {k['unique']} · passed the quality check "
                         f"(sources reviewed by you): {k['auto_approved']} · decided by you: {k['decided_by_person']} · "
                         f"rejected: {k['rejected']} · still waiting: {k['pending']}", ""]
    rej = [e for e in b["evidence"] if e["status"] == "rejected"]
    if rej:
        L += ["### Rejected evidence (kept on record)"] + [f"- {e['id']} {e['title']}: {e['decision_reason'] or 'no reason given'}" for e in rej] + [""]
    concl = b.get("conclusion")
    L += ["## Your conclusion", ""]
    L += [concl["text"] if concl and concl.get("saved_at") else "_Not written yet._", ""]
    if c.get("sample"):
        L += ["", "_Sample data (simulated)._"]
    return "\n".join(L) + "\n"


TABLES = {"Frame": "frame", "RuleSet": "ruleset", "Hypothesis": "hypothesis", "EvidenceNeed": "need",
          "ClientFile": "client_file", "SourcePlanItem": "plan_item", "EvidenceItem": "evidence", "Calc": "calc",
          "Trip": "trip", "Overall": "overall", "Summary": "summary", "Conclusion": "conclusion"}


def as_json(b: dict) -> str:
    cid = b["case"]["id"]
    out = dict(b)
    acts = activity(cid)
    out["activity"] = acts
    tables = {"Case": [db.case_get(cid)]}
    for name, t in TABLES.items():
        tables[name] = db.rows(t, cid)
    tables["EvidenceLink"] = [lk for e in db.rows("evidence", cid) for lk in e.get("links") or []]
    tables["Verdict"] = [h["verdict"] for h in db.rows("hypothesis", cid) if h.get("verdict")]
    tables["Activity"] = acts
    out["tables"] = tables
    return json.dumps(out, indent=1, ensure_ascii=False)


def filename(b: dict, ext: str) -> str:
    t = "".join(ch if ch.isalnum() or ch in "()-_" else "_" for ch in b["case"]["title"].replace(", ", "_").replace(" ", "_"))
    while "__" in t:
        t = t.replace("__", "_")
    return f"{t or 'case'}.{ext}"


def import_case(data: dict, mode: str) -> int:
    """Restore a case from its JSON export (free hosting loses data on restart)."""
    from .core import log
    b = data
    if not isinstance(b, dict) or "case" not in b or "progress" not in b:
        raise ValueError("This isn't a case export from Research Workbench.")
    c = dict(b["case"])
    c.pop("id", None)
    c["title"] = c.get("title") or "Imported case"
    c["mode"] = c.get("mode") or mode
    cid = db.case_insert(c)
    one = {"frame": b.get("frame"), "ruleset": b.get("ruleset"), "overall": b.get("overall"), "summary": b.get("summary"),
           "conclusion": b.get("conclusion")}
    for t, row in one.items():
        if row:
            db.insert(t, cid, {k: v for k, v in row.items() if k not in ("id", "case_id")})
    for h in b.get("hypotheses") or []:
        db.insert("hypothesis", cid, {k: v for k, v in h.items() if k not in ("id", "case_id")})
    fmap = {}
    for f in (b.get("tables") or {}).get("ClientFile") or b.get("files") or []:
        row = db.insert("client_file", cid, {k: v for k, v in f.items() if k not in ("id", "case_id")} | {"preview": f.get("preview", "")})
        fmap[f["id"]] = row["id"]
    for n in b.get("needs") or []:
        db.insert("need", cid, {k: v for k, v in n.items() if k not in ("id", "case_id")} |
                  {"covered_by_file_id": fmap.get(n.get("covered_by_file_id"))})
    for p in b.get("plan") or []:
        db.insert("plan_item", cid, {k: v for k, v in p.items() if k not in ("id", "case_id")})
    present_keys = ("status_label", "tier", "tier_label", "date", "claim", "copies", "pk", "case_id")
    for e in b.get("evidence") or []:
        row = {k: v for k, v in e.items() if k not in present_keys}
        row["file_id"] = fmap.get(e.get("file_id"))
        row["links"] = [dict(lk, case_id=cid) for lk in e.get("links") or []]
        db.insert("evidence", cid, row)
    for x in b.get("calcs") or []:
        db.insert("calc", cid, {k: v for k, v in x.items() if k not in ("id", "case_id")})
    for t in b.get("trips") or []:
        db.insert("trip", cid, {k: v for k, v in t.items() if k not in ("case_id", "pk")} | {"reply_file_id": fmap.get(t.get("reply_file_id"))})
    for kind, j in (b.get("jobs") or {}).items():
        if j.get("status") == "running":
            j = dict(j, status="failed", error="This step was interrupted. Try again.")
        db.insert("job", cid, {k: v for k, v in j.items() if k not in ("id", "case_id")})
    for a in b.get("activity") or []:
        db.ex("INSERT INTO activity (case_id, ts, actor, event_type, step, message, payload_json) VALUES (?,?,?,?,?,?,?)",
              (cid, a["ts"], a["actor"], a["event_type"], a["step"], a["message"],
               json.dumps(a.get("payload_json")) if a.get("payload_json") else None))
    log(cid, "consultant", "case_imported", c.get("current_step", 1), "Restored this case from a JSON export")
    return cid
