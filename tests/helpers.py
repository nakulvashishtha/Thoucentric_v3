"""Drive the API in-process (no network, no real model or search calls)."""
import time

from fastapi.testclient import TestClient

from app import db
from app.main import app


def client(passcode: str | None = None) -> TestClient:
    db.reset_for_tests(":memory:")
    return TestClient(app)


def settle(c: TestClient, cid: int, timeout: float = 60) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        b = c.get(f"/api/cases/{cid}").json()
        if not b["running_jobs"]:
            return b
        time.sleep(0.05)
    raise AssertionError("background job did not finish")


def verdicts(b: dict) -> dict:
    return {h["code"]: (h["verdict"]["result"], h["verdict"]["confidence"]) for h in b["hypotheses"]
            if h.get("verdict") and not h.get("removed_reason")}


def decide_all(c, cid, b, trip=False):
    for e in b["evidence"]:
        if bool(e.get("trip_id")) != trip or e["status"] != "needs_decision":
            continue
        tag = e.get("script_tag") or ""
        if tag == "cross_check":
            act = {"action": "keep_cross_check"}
        elif tag == "reject_no_method":
            act = {"action": "reject", "reason": "no method shown"}
        elif e["origin_type"] == "client_file" and e["credibility_json"].get("matches_belief"):
            act = {"action": "keep_belief"}
        elif e["origin_type"] == "client_file":
            act = {"action": "keep_client_reported"}
        else:
            act = {"action": "approve"}
        if e.get("formula_needs_you"):
            act["confirm_formula"] = True
        r = c.post(f"/api/cases/{cid}/evidence/{e['id']}/decision", json=act)
        assert r.status_code == 200, r.json()


def run_to_review(c, name):
    cid = c.post(f"/api/samples/{name}/load").json()["id"]
    assert c.post(f"/api/cases/{cid}/read-ask").status_code == 200
    settle(c, cid)
    assert c.post(f"/api/cases/{cid}/frame/confirm").status_code == 200
    settle(c, cid)
    assert c.post(f"/api/cases/{cid}/plan/lock", json={"ticked": True}).status_code == 200
    settle(c, cid)
    assert c.post(f"/api/cases/{cid}/requests/mark-sent", json={"reviewed": True}).status_code == 200
    b = settle(c, cid)
    while not b["progress"]["done"]["6"]:
        time.sleep(0.05)
        b = settle(c, cid)
    return cid, b


def finish_review(c, cid, b):
    decide_all(c, cid, b)
    for e in b["evidence"]:
        if e.get("spot_check_selected"):
            assert c.post(f"/api/cases/{cid}/review/spot-check/{e['id']}", json={"matches": True}).status_code == 200
        if e["bucket"] == "auto":
            assert c.post(f"/api/cases/{cid}/review/seen/{e['id']}").status_code == 200
    assert c.post(f"/api/cases/{cid}/review/confirm-sources", json={"ticked": True}).status_code == 200
