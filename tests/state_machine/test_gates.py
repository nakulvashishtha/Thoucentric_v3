"""Every gate refuses early calls with 409 {reason, required}; the locked plan cannot change."""
from helpers import client, finish_review, run_to_review, settle


def test_early_calls_refused():
    c = client()
    cid = c.post("/api/samples/sample_01_card_launch/load").json()["id"]
    for method, path, body in [("post", "test/run", None), ("post", "plan/lock", {"ticked": True}),
                               ("post", "requests/mark-sent", {"reviewed": True}), ("post", "frame/confirm", None),
                               ("post", "addup/run", None), ("post", "whatif", {}), ("put", "conclusion", {"text": "x"}),
                               ("post", "trips", {"hypothesis": "H2"}), ("post", "collect/start", None)]:
        r = getattr(c, method)(f"/api/cases/{cid}/{path}", json=body)
        assert r.status_code == 409, (path, r.status_code, r.json())
        assert set(r.json()) == {"reason", "required"}, path
    assert c.post(f"/api/cases/{cid}/whatif", json={}).json()["reason"] == "Run the tests first."


def test_plan_lock_rules_and_immutability():
    c = client()
    cid = c.post("/api/samples/sample_01_card_launch/load").json()["id"]
    c.post(f"/api/cases/{cid}/read-ask"); settle(c, cid)
    c.post(f"/api/cases/{cid}/frame/confirm"); b = settle(c, cid)
    r = c.post(f"/api/cases/{cid}/plan/lock", json={})
    assert r.status_code == 409 and r.json()["reason"] == "Tick the box to confirm the targets first."
    assert c.put(f"/api/cases/{cid}/hypotheses", json=[{"code": "H5", "removed_reason": " "}]).status_code == 400
    assert c.put(f"/api/cases/{cid}/hypotheses", json=[{"code": "H1", "pass_line_formula": "__import__('os')"}]).status_code == 400
    assert c.put(f"/api/cases/{cid}/hypotheses", json=[{"code": "H5", "removed_reason": "not needed"}]).status_code == 200
    assert c.post(f"/api/cases/{cid}/plan/lock", json={"ticked": True}).status_code == 200
    b = settle(c, cid)
    for row in ({"code": "H1", "pass_line_value": 1}, {"code": "H2", "must_have": False}, {"code": "H3", "tolerance_pct": 9}):
        assert c.put(f"/api/cases/{cid}/hypotheses", json=[row]).status_code == 409
    r = c.post(f"/api/cases/{cid}/requests/mark-sent", json={"reviewed": False})
    assert r.status_code == 409 and r.json()["reason"] == "Tick \"I've checked what goes out\" first."


def test_review_gate_and_messages():
    c = client()
    cid, b = run_to_review(c, "sample_01_card_launch")
    r = c.post(f"/api/cases/{cid}/test/run")
    assert r.status_code == 409
    assert r.json()["reason"] == ("Finish the review first: decide 10 more items; look at 6 more sources; "
                                  "tick \"I've checked these sources\".")
    assert r.json()["required"] == ["Decide 10 more items", "Look at 6 more sources", "Tick \"I've checked these sources\""]
    # client files and expert notes are never auto-approved
    assert not [e for e in b["evidence"] if e["origin_type"] in ("client_file", "expert_note") and e["status"] == "auto_approved"]
    assert c.post(f"/api/cases/{cid}/evidence/E10/decision", json={"action": "maybe"}).status_code == 400
    finish_review(c, cid, b)
    assert c.post(f"/api/cases/{cid}/test/run").status_code == 200
    assert c.post(f"/api/cases/{cid}/evidence/E12/decision", json={"action": "approve"}).status_code == 409


def test_trip_limits_and_retest_gate():
    c = client()
    cid, b = run_to_review(c, "sample_01_card_launch")
    finish_review(c, cid, b)
    c.post(f"/api/cases/{cid}/test/run")
    for n in (1, 2):
        r = c.post(f"/api/cases/{cid}/trips", json={"hypothesis": "H4", "override": False})
        assert r.status_code == 200
        tid = r.json()["trip_id"]
        settle(c, cid)
        if n == 1:
            assert c.post(f"/api/cases/{cid}/retest", json={"hypothesis": "H4"}).json()["reason"] == "Add the reply first."
        # close the request so the next one can start: reply, mark the sample check not needed, test again
        c.post(f"/api/cases/{cid}/trips/{tid}/mark-sent")
        assert c.post(f"/api/cases/{cid}/trips/{tid}/reply", data={"text": "No new figures yet.", "filename": "n.txt"}).status_code in (200, 409)
        b = settle(c, cid)
        c.post(f"/api/cases/{cid}/trips/{tid}/sample-mix", json={"not_applicable": True})
        for e in b["evidence"]:
            if e.get("trip_id") == tid and e["status"] == "needs_decision":
                c.post(f"/api/cases/{cid}/evidence/{e['id']}/decision", json={"action": "reject", "reason": "no figure"})
        c.post(f"/api/cases/{cid}/retest", json={"hypothesis": "H4"})
    r = c.post(f"/api/cases/{cid}/trips", json={"hypothesis": "H4", "override": False})
    assert r.status_code == 409                                   # a third request needs a reason and the tick
    r = c.post(f"/api/cases/{cid}/trips", json={"hypothesis": "H4", "override": True, "override_reason": "scope changed"})
    assert r.status_code == 200
