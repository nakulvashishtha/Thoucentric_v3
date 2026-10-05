#!/usr/bin/env python3
"""Drive Sample 1 through all 12 steps over HTTP and check the backend against the recorded original.

  python tools/contract_check.py http://localhost:8000 [--passcode CODE] [--no-gates]

At each stage it (1) calls the same endpoints the front end calls, (2) compares the shape of GET /api/cases/{id}
with the bundle recorded on the original backend (tools/shape_diff.py), and (3) checks the Sample 1 results
(H1 Not supported/Strong, H2 Not enough evidence then Supported/Fair, H3 Supported/Fair, H4 Supported/Weak,
overall Not achievable). With --no-gates the checks that the server must refuse early calls (409) are skipped; use that
only against tools/mock_api_server.js. Standard library only. Exit code 0 means every check passed."""
import json, sys, time, uuid, urllib.request, urllib.error, http.cookiejar, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from shape_diff import diff

args = [a for a in sys.argv[1:] if not a.startswith("--")]
BASE = (args[0] if args else "http://localhost:8765").rstrip("/")
GATES = "--no-gates" not in sys.argv
PASS = sys.argv[sys.argv.index("--passcode") + 1] if "--passcode" in sys.argv else None
jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
fails, checks = [], 0

def call(method, path, body=None, raw=False, headers=None):
    data = None; h = dict(headers or {})
    if body is not None and not isinstance(body, bytes):
        data = json.dumps(body).encode(); h["Content-Type"] = "application/json"
    elif isinstance(body, bytes): data = body
    req = urllib.request.Request(BASE + "/api" + path, data=data, method=method, headers=h)
    try:
        r = op.open(req, timeout=60); b = r.read(); code = r.status
    except urllib.error.HTTPError as e:
        b = e.read(); code = e.code
    if raw: return code, b
    try: return code, json.loads(b or b"{}")
    except Exception: return code, {"_text": b.decode("utf8", "replace")}

def check(ok, what):
    global checks; checks += 1
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok: fails.append(what)

def multipart(fields, fname=None, fbytes=None):
    bd = uuid.uuid4().hex; out = b""
    for k, v in fields.items(): out += f'--{bd}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    if fname: out += f'--{bd}\r\nContent-Disposition: form-data; name="file"; filename="{fname}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + fbytes + b"\r\n"
    out += f"--{bd}--\r\n".encode()
    return out, {"Content-Type": f"multipart/form-data; boundary={bd}"}

def bundle(cid): return call("GET", f"/cases/{cid}")[1]
def settle(cid, until=None, limit=240):
    t0 = time.time(); time.sleep(0.4)
    while time.time() - t0 < limit:
        b = bundle(cid)
        if not b.get("running_jobs") and (until is None or until(b)): return b
        time.sleep(1)
    check(False, "timed out waiting for the background job"); return bundle(cid)
def shape(cid, state, b=None):
    b = b or bundle(cid)
    r = diff(b, state)
    bad = sorted(set(r["missing"] + r["mismatch"]))
    check(not bad, f"bundle shape matches {state}" + ("" if not bad else ": " + "; ".join(bad[:6])))
    return b
def verdicts(b): return {h["code"]: (h["verdict"]["result"], h["verdict"]["confidence"]) for h in b["hypotheses"] if h.get("verdict") and not h.get("removed_reason")}

print(f"Checking {BASE}")
if PASS:
    c, _ = call("POST", "/login", {"passcode": PASS}); check(c == 200, "passcode accepted")
c, s = call("GET", "/session"); check(c == 200 and "signed_in" in s, "GET /session answers")
c, samples = call("GET", "/samples"); check(c == 200 and any(x["name"] == "sample_01_card_launch" for x in samples), "GET /samples lists sample_01_card_launch")
check(len(samples) >= 2, "a second, unrelated sample is listed (generality)")
c, sc = call("GET", "/selfcheck"); check(c == 200 and "items" in sc, "GET /selfcheck answers")
c, st = call("GET", "/settings"); check(c == 200 and "mode" in st, "GET /settings answers")

print("Step 1: load the sample")
c, r = call("POST", "/samples/sample_01_card_launch/load"); check(c == 200 and "id" in r, "load the sample"); cid = r["id"]
b = shape(cid, "s1_loaded")
if GATES:
    c, r = call("POST", f"/cases/{cid}/test/run"); check(c == 409 and "reason" in r and "required" in r, "test/run too early is refused with 409 {reason, required}")
    c, r = call("POST", f"/cases/{cid}/plan/lock", {"ticked": True}); check(c == 409, "plan/lock before the frame is confirmed is refused with 409")

print("Steps 1 to 2: read the ask")
c, r = call("POST", f"/cases/{cid}/read-ask"); check(c == 200, "POST read-ask")
b = settle(cid, lambda b: b.get("frame")); shape(cid, "s1_framed", b)
check(bool(b["frame"] and b["frame"].get("client_belief")), "the frame has a belief to test")
print("Steps 2 to 3: confirm the question")
c, r = call("POST", f"/cases/{cid}/frame/confirm"); check(c == 200, "POST frame/confirm")
b = settle(cid, lambda b: len(b.get("hypotheses", [])) > 0); shape(cid, "s2_planned", b)
check(2 <= len([h for h in b["hypotheses"] if not h.get("removed_reason")]) <= 8, "2 to 8 ideas were drafted")
print("Steps 3 to 4: lock the targets")
c, r = call("POST", f"/cases/{cid}/plan/lock", {"ticked": True}); check(c == 200, "POST plan/lock")
b = settle(cid, lambda b: len(b.get("needs", [])) > 0); shape(cid, "s3_locked", b)
if GATES:
    c, r = call("PUT", f"/cases/{cid}/hypotheses", [{"code": b["hypotheses"][0]["code"], "pass_line_value": 1}])
    check(c == 409, "editing targets after the lock is refused with 409")
print("Steps 4 to 7: send, collect, clean")
if GATES:
    c, r = call("POST", f"/cases/{cid}/requests/mark-sent", {"reviewed": False}); check(c == 409, "mark-sent without the review tick is refused with 409")
c, r = call("POST", f"/cases/{cid}/requests/mark-sent", {"reviewed": True}); check(c == 200, "POST requests/mark-sent")
b = settle(cid, lambda b: b["progress"]["done"].get("6") and b.get("review"), limit=300); shape(cid, "s7_review", b)
check(b["counts"]["collected"] >= 10, f"collected {b['counts']['collected']} items")
print("Step 7: review")
ev = [e for e in b["evidence"] if not e.get("trip_id")]
if GATES:
    c, r = call("POST", f"/cases/{cid}/test/run"); check(c == 409, "test/run before the review is done is refused with 409")
def decide(e, trip=False):
    tag = e.get("script_tag") or ""
    if tag == "cross_check": act = {"action": "keep_cross_check"}
    elif tag == "reject_no_method": act = {"action": "reject", "reason": "no method shown"}
    elif e["origin_type"] == "client_file": act = {"action": "keep_client_reported"}
    else: act = {"action": "approve"}
    if e.get("formula_needs_you") and act["action"] in ("approve", "keep_client_reported"): act["confirm_formula"] = True
    c, r = call("POST", f"/cases/{cid}/evidence/{e['id']}/decision", act)
    check(c == 200, f"decision on {e['id']}: {act['action']}" + ("" if c == 200 else f" -> {c} {r.get('reason')}"))
for e in ev:
    if e["bucket"] == "decision" and e["status"] == "needs_decision": decide(e)
for e in ev:
    if e["bucket"] == "auto":
        c, r = call("POST", f"/cases/{cid}/review/seen/{e['id']}"); check(c == 200, f"seen {e['id']}")
for e in ev:
    if e.get("spot_check_selected"):
        c, r = call("POST", f"/cases/{cid}/review/spot-check/{e['id']}", {"matches": True}); check(c == 200, f"double-check {e['id']}")
c, r = call("POST", f"/cases/{cid}/review/confirm-sources", {"ticked": True}); check(c == 200, "confirm-sources")
b = bundle(cid); check(b["review"]["ready"], "review.ready is true")
print("Step 8: run the tests")
c, r = call("POST", f"/cases/{cid}/test/run"); check(c == 200, "POST test/run")
b = shape(cid, "s8_tested"); v = verdicts(b)
check(v.get("H1") == ("fails", "high"), f"H1 Not supported, Strong (got {v.get('H1')})")
check(v.get("H2") == ("not_enough", "none"), f"H2 Not enough evidence (got {v.get('H2')})")
check(v.get("H3") == ("holds", "medium"), f"H3 Supported, Fair (got {v.get('H3')})")
check(v.get("H4") == ("holds", "low"), f"H4 Supported, Weak (got {v.get('H4')})")
print("Step 9: fill the gap")
c, r = call("POST", f"/cases/{cid}/trips", {"hypothesis": "H2", "override": False}); check(c == 200, "POST trips")
b = settle(cid, lambda b: b.get("trips") and b["trips"][0].get("question")); shape(cid, "s9_drafted", b)
tid = b["trips"][0]["id"]
c, r = call("PUT", f"/cases/{cid}/trips/{tid}", {"question": b["trips"][0]["question"]}); check(c == 200, "PUT trips/{id}")
c, r = call("POST", f"/cases/{cid}/trips/{tid}/mark-sent"); check(c == 200, "POST trips/{id}/mark-sent")
name = b["sample_replies"].get("H2")
c, blob = call("GET", f"/samples/sample_01_card_launch/replies/H2", raw=True); check(c == 200 and len(blob) > 0, f"sample reply file {name} downloads")
body, h = multipart({}, name or "reply.xlsx", blob)
c, r = call("POST", f"/cases/{cid}/trips/{tid}/reply", body, headers=h); check(c == 200, "POST trips/{id}/reply (multipart file)")
b = settle(cid, lambda b: any(e.get("trip_id") for e in b["evidence"])); shape(cid, "s9_replied", b)
for e in [e for e in b["evidence"] if e.get("trip_id") and e["status"] == "needs_decision"]: decide(e, True)
c, r = call("POST", f"/cases/{cid}/trips/{tid}/sample-mix", {"not_applicable": True}); check(c in (200, 409), "sample-mix endpoint answers")
c, r = call("POST", f"/cases/{cid}/retest", {"hypothesis": "H2"}); check(c == 200, "POST retest" + ("" if c == 200 else f" -> {c} {r.get('reason')}"))
b = shape(cid, "s9_retested"); v = verdicts(b)
check(v.get("H2") == ("holds", "medium"), f"H2 now Supported, Fair (got {v.get('H2')})")
print("Step 10: add it up")
c, r = call("POST", f"/cases/{cid}/addup/run"); check(c == 200, "POST addup/run")
b = settle(cid, lambda b: b.get("summary")); shape(cid, "s10_added", b)
check(b["overall"]["result"] == "not_achievable", f"overall Not achievable (got {b['overall']['result']})")
ids = {e["id"] for e in b["evidence"]}
check(all(set(s["evidence_ids"]) <= ids and s["evidence_ids"] for s in b["summary"]["sentences"]), "every summary sentence cites evidence ids that exist")
print("Step 11: what if")
c, w = call("POST", f"/cases/{cid}/whatif", {"assumptions": {"build_months": 9}, "pass_lines": {}}); check(c == 200 and "ideas" in w and w.get("locked_plan_unchanged") is True, "POST whatif answers and leaves the locked plan unchanged")
check(any(i["code"] == "H4" and i["result"] == "fails" for i in w.get("ideas", [])), "build_months = 9 makes H4 Not supported")
print("Step 12: conclusion and exports")
if GATES:
    c, r = call("PUT", f"/cases/{cid}/conclusion", {"text": "  "}); check(c in (400, 409), "an empty conclusion is refused")
c, r = call("PUT", f"/cases/{cid}/conclusion", {"text": "Not achievable at the agreed targets. Test a narrower segment first."}); check(c == 200, "PUT conclusion")
b = bundle(cid); check(b["conclusion"] and b["conclusion"]["saved_at"], "conclusion saved")
for f in ("md", "json"):
    c, t = call("GET", f"/cases/{cid}/export?format={f}", raw=True); check(c == 200 and len(t) > 200, f"export {f}")
c, t = call("GET", f"/cases/{cid}/activity?format=csv", raw=True); check(c == 200 and b"message" in t, "History CSV")
c, acts = call("GET", f"/cases/{cid}/activity"); check(c == 200 and isinstance(acts, list) and acts and all(k in acts[0] for k in ("id", "ts", "actor", "event_type", "step", "message")), "activity list shape")
print(f"\n{checks - len(fails)} of {checks} checks passed")
sys.exit(1 if fails else 0)
