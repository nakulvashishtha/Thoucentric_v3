#!/usr/bin/env python3
"""Twin of contract_check.py for any sample: drives one sample case through all 12 steps over HTTP using the pack's
consultant script rules, and checks the verdicts and the overall result against the pack's expected.json.

  python tools/sample_check.py http://localhost:8000 --sample sample_02_hospital_expansion [--passcode CODE]

Standard library only. Exit code 0 means every check passed."""
import json, sys, time, pathlib, urllib.request, urllib.error, http.cookiejar, uuid

args = [a for a in sys.argv[1:] if not a.startswith("--")]
BASE = (args[0] if args else "http://localhost:8000").rstrip("/")
SAMPLE = sys.argv[sys.argv.index("--sample") + 1] if "--sample" in sys.argv else "sample_02_hospital_expansion"
PASS = sys.argv[sys.argv.index("--passcode") + 1] if "--passcode" in sys.argv else None
PACK = pathlib.Path(__file__).resolve().parent.parent / "backend" / "samples" / SAMPLE
EXP = json.loads((PACK / "expected.json").read_text())
OTHER_TERMS = {"sample_01_card_launch": ["credit card", "Example Client"], "sample_02_hospital_expansion": ["hospital", "Nakuru", "Mzuri"]}
jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
fails, checks = [], 0


def call(method, path, body=None, raw=False, headers=None):
    data, h = None, dict(headers or {})
    if isinstance(body, bytes):
        data = body
    elif body is not None:
        data, h["Content-Type"] = json.dumps(body).encode(), "application/json"
    req = urllib.request.Request(BASE + "/api" + path, data=data, method=method, headers=h)
    try:
        r = op.open(req, timeout=60); b = r.read(); code = r.status
    except urllib.error.HTTPError as e:
        b, code = e.read(), e.code
    if raw:
        return code, b
    try:
        return code, json.loads(b or b"{}")
    except ValueError:
        return code, {}


def check(ok, what):
    global checks
    checks += 1
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        fails.append(what)


def settle(cid, until=lambda b: True, limit=240):
    t0 = time.time(); time.sleep(0.3)
    while time.time() - t0 < limit:
        b = call("GET", f"/cases/{cid}")[1]
        if not b.get("running_jobs") and until(b):
            return b
        time.sleep(0.5)
    check(False, "timed out waiting for a background job"); return call("GET", f"/cases/{cid}")[1]


def verdicts(b):
    return {h["code"]: [h["verdict"]["result"], h["verdict"]["confidence"]] for h in b["hypotheses"] if h.get("verdict") and not h.get("removed_reason")}


def decide(cid, e):
    tag = e.get("script_tag") or ""
    if tag == "cross_check": act = {"action": "keep_cross_check"}
    elif tag == "reject_no_method": act = {"action": "reject", "reason": "no method shown"}
    elif e["origin_type"] == "client_file" and (e.get("credibility_json") or {}).get("matches_belief"): act = {"action": "keep_belief"}
    elif e["origin_type"] == "client_file": act = {"action": "keep_client_reported"}
    else: act = {"action": "approve"}
    if e.get("formula_needs_you") and act["action"] in ("approve", "keep_client_reported"): act["confirm_formula"] = True
    c, r = call("POST", f"/cases/{cid}/evidence/{e['id']}/decision", act)
    check(c == 200, f"decision on {e['id']}: {act['action']}")


print(f"Checking {BASE} with {SAMPLE}")
if PASS:
    check(call("POST", "/login", {"passcode": PASS})[0] == 200, "passcode accepted")
c, r = call("POST", f"/samples/{SAMPLE}/load"); check(c == 200, "load the sample"); cid = r["id"]
c, r = call("POST", f"/cases/{cid}/test/run"); check(c == 409 and set(r) == {"reason", "required"}, "early test/run refused with 409")
call("POST", f"/cases/{cid}/read-ask"); b = settle(cid, lambda b: b.get("frame"))
check(bool(b["frame"] and b["frame"]["client_belief"]), "question framed")
call("POST", f"/cases/{cid}/frame/confirm"); b = settle(cid, lambda b: b["hypotheses"])
check(2 <= len(b["hypotheses"]) <= 8, f"{len(b['hypotheses'])} ideas drafted")
check(call("POST", f"/cases/{cid}/plan/lock", {"ticked": True})[0] == 200, "targets locked"); b = settle(cid, lambda b: b["needs"])
check(call("PUT", f"/cases/{cid}/hypotheses", [{"code": "H1", "pass_line_value": 1}])[0] == 409, "targets can't change after the lock")
check(call("POST", f"/cases/{cid}/requests/mark-sent", {"reviewed": True})[0] == 200, "requests marked as sent")
b = settle(cid, lambda b: b["progress"]["done"].get("6") and b.get("review"), 300)
check(b["counts"]["collected"] >= 8, f"collected {b['counts']['collected']} items, {b['counts']['unique']} separate")
check(not [e for e in b["evidence"] if "forum." in (e.get("domain") or "")], "the excluded source was never collected")
for e in b["evidence"]:
    if e["bucket"] == "decision" and e["status"] == "needs_decision": decide(cid, e)
for e in b["evidence"]:
    if e["bucket"] == "auto": call("POST", f"/cases/{cid}/review/seen/{e['id']}")
    if e.get("spot_check_selected"): call("POST", f"/cases/{cid}/review/spot-check/{e['id']}", {"matches": True})
call("POST", f"/cases/{cid}/review/confirm-sources", {"ticked": True})
check(call("POST", f"/cases/{cid}/test/run")[0] == 200, "tests run")
v = verdicts(call("GET", f"/cases/{cid}")[1])
for code, want in EXP["before_trip"].items():
    check(v.get(code) == want, f"{code} {want} (got {v.get(code)})")
idea = EXP["trip_idea"]
c, r = call("POST", f"/cases/{cid}/trips", {"hypothesis": idea, "override": False}); check(c == 200, "follow-up drafted")
b = settle(cid, lambda b: b["trips"] and b["trips"][0]["question"]); tid = b["trips"][0]["id"]
call("POST", f"/cases/{cid}/trips/{tid}/mark-sent")
c, blob = call("GET", f"/samples/{SAMPLE}/replies/{idea}", raw=True); check(c == 200, "sample reply downloads")
bd = uuid.uuid4().hex; fn = b["sample_replies"][idea]
body = (f'--{bd}\r\nContent-Disposition: form-data; name="file"; filename="{fn}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode() + blob + f"\r\n--{bd}--\r\n".encode()
check(call("POST", f"/cases/{cid}/trips/{tid}/reply", body, headers={"Content-Type": f"multipart/form-data; boundary={bd}"})[0] == 200, "reply added")
b = settle(cid, lambda b: any(e.get("trip_id") for e in b["evidence"]))
for e in b["evidence"]:
    if e.get("trip_id") and e["status"] == "needs_decision": decide(cid, e)
if not b["trips"][0]["sample_mix_json"]:
    call("POST", f"/cases/{cid}/trips/{tid}/sample-mix", {"not_applicable": True})
check(call("POST", f"/cases/{cid}/retest", {"hypothesis": idea})[0] == 200, "tested again")
v = verdicts(call("GET", f"/cases/{cid}")[1])
for code, want in EXP["after_trip"].items():
    check(v.get(code) == want, f"after the reply {code} {want} (got {v.get(code)})")
call("POST", f"/cases/{cid}/addup/run"); b = settle(cid, lambda b: b.get("summary"))
check(b["overall"]["result"] == EXP["overall"], f"overall {EXP['overall']} (got {b['overall']['result']})")
ids = {e["id"] for e in b["evidence"]}
check(all(s["evidence_ids"] and set(s["evidence_ids"]) <= ids for s in b["summary"]["sentences"]), "every summary sentence cites real evidence")
check(b["summary"]["source"] == "llm", "the drafted summary passed the citation check")
check(call("POST", f"/cases/{cid}/whatif", {"assumptions": {}, "pass_lines": {}})[1].get("locked_plan_unchanged") is True, "what-if answers")
check(call("PUT", f"/cases/{cid}/conclusion", {"text": "Written by the consultant."})[0] == 200, "conclusion saved")
c, md = call("GET", f"/cases/{cid}/export?format=md", raw=True); check(c == 200, "Markdown export")
text = json.dumps(call("GET", f"/cases/{cid}")[1]) + md.decode()
for other, terms in OTHER_TERMS.items():
    if other != SAMPLE:
        leaked = [t for t in terms if t.lower() in text.lower()]
        check(not leaked, f"no text from {other} leaks in" + (f" (found {leaked})" if leaked else ""))
print(f"\n{checks - len(fails)} of {checks} checks passed")
sys.exit(1 if fails else 0)
