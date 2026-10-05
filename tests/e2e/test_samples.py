"""Scripted end-to-end runs through the API in demo data mode, asserting verdicts, gates and the History."""
from helpers import client, decide_all, finish_review, run_to_review, settle, verdicts


def test_sample1_full_run():
    c = client()
    cid, b = run_to_review(c, "sample_01_card_launch")
    assert b["counts"]["collected"] == 25 and b["counts"]["unique"] == 16 and b["counts"]["auto_approved"] == 6
    assert b["review"]["decision_total"] == 10
    # the excluded forum source was never collected
    assert not [e for e in b["evidence"] if "forum" in (e.get("domain") or "")]
    finish_review(c, cid, b)
    assert c.post(f"/api/cases/{cid}/test/run").status_code == 200
    b = c.get(f"/api/cases/{cid}").json()
    assert verdicts(b) == {"H1": ("fails", "high"), "H2": ("not_enough", "none"), "H3": ("holds", "medium"),
                           "H4": ("holds", "low"), "H5": ("not_enough", "none")}
    tid = c.post(f"/api/cases/{cid}/trips", json={"hypothesis": "H2", "override": False}).json()["trip_id"]
    b = settle(c, cid)
    assert "2025 pilot" in b["trips"][0]["question"]
    c.post(f"/api/cases/{cid}/trips/{tid}/mark-sent")
    blob = c.get("/api/samples/sample_01_card_launch/replies/H2").content
    assert c.post(f"/api/cases/{cid}/trips/{tid}/reply", files={"file": ("pilot_costs.xlsx", blob)}).status_code == 200
    b = settle(c, cid)
    assert b["progress"]["reopened"] == ["H2"]
    assert b["trips"][0]["sample_mix_json"]["passes"] is True
    r = c.post(f"/api/cases/{cid}/retest", json={"hypothesis": "H2"})
    assert r.status_code == 409 and r.json()["reason"].startswith("Make a call on the new evidence first: E29")
    decide_all(c, cid, b, trip=True)
    assert c.post(f"/api/cases/{cid}/retest", json={"hypothesis": "H2"}).status_code == 200
    assert verdicts(c.get(f"/api/cases/{cid}").json())["H2"] == ("holds", "medium")
    c.post(f"/api/cases/{cid}/addup/run")
    b = settle(c, cid)
    assert b["overall"]["result"] == "not_achievable"
    ids = {e["id"] for e in b["evidence"]}
    assert all(s["evidence_ids"] and set(s["evidence_ids"]) <= ids for s in b["summary"]["sentences"])
    w = c.post(f"/api/cases/{cid}/whatif", json={"assumptions": {"build_months": 9}}).json()
    assert [i for i in w["ideas"] if i["code"] == "H4"][0]["result"] == "fails" and w["locked_plan_unchanged"]
    assert c.get(f"/api/cases/{cid}").json()["hypotheses"][3]["line"] == 12     # nothing written
    assert c.put(f"/api/cases/{cid}/conclusion", json={"text": " "}).status_code == 400
    assert c.put(f"/api/cases/{cid}/conclusion", json={"text": "Do not launch yet."}).status_code == 200
    md = c.get(f"/api/cases/{cid}/export?format=md").text
    assert "| H1 " in md and "Not supported" in md and "Do not launch yet." in md
    assert c.get(f"/api/cases/{cid}/export?format=docx").status_code == 400
    csv = c.get(f"/api/cases/{cid}/activity?format=csv").text
    assert csv.splitlines()[0] == "id,time,actor,step,event,message"
    acts = c.get(f"/api/cases/{cid}/activity").json()
    actors = {a["actor"] for a in acts}
    assert {"consultant", "llm", "rule_engine", "client", "expert", "system"} <= actors
    # import the export back
    j = c.get(f"/api/cases/{cid}/export?format=json").content
    nid = c.post("/api/cases/import", files={"file": ("x.json", j)}).json()["id"]
    nb = c.get(f"/api/cases/{nid}").json()
    assert verdicts(nb) == verdicts(c.get(f"/api/cases/{cid}").json()) and nb["overall"]["result"] == "not_achievable"


def test_stress_test_retarget():
    c = client()
    cid = c.post("/api/samples/sample_01_card_launch/load").json()["id"]
    c.post(f"/api/cases/{cid}/sample/advance?to=12")
    b = settle(c, cid, 120)
    assert b["overall"]["result"] == "not_achievable"
    r = c.post(f"/api/cases/{cid}/plan/retarget", json={"kind": "assumption", "key": "required_growth", "value": 12})
    assert r.status_code == 200
    b = settle(c, cid)
    assert b["overall"]["result"] == "achievable"
    assert [h for h in b["hypotheses"] if h["code"] == "H1"][0]["line"] == 12
    assert c.post(f"/api/cases/{cid}/plan/retarget", json={"kind": "pass_line", "key": "H1", "value": 999}).status_code == 400


def test_blank_case_without_keys_fails_plainly():
    c = client()
    cid = c.post("/api/cases").json()["id"]
    r = c.post(f"/api/cases/{cid}/read-ask")
    assert r.status_code == 409 and "Client" in r.json()["required"]
    c.put(f"/api/cases/{cid}", json={"client_name": "Acme", "country": "Chile", "industry": "Retail", "function": "Strategy",
                                    "raw_ask": "Should Acme open 20 stores?"})
    assert c.post(f"/api/cases/{cid}/read-ask").status_code == 200
    b = settle(c, cid)
    j = b["jobs"]["frame"]
    assert j["status"] == "failed" and j["error"].startswith("A new case needs the live AI and search services")
    assert "Traceback" not in j["error"]


def test_startup_without_keys_is_demo_mode():
    c = client()
    s = c.get("/api/settings").json()
    assert s["mode"] == "fixtures" and not any(s["keys"].values())
    assert c.get("/healthz").json() == {"ok": True}
    sc = c.get("/api/selfcheck").json()
    assert sc["red"] >= 3 and all(i["fix"] for i in sc["items"] if i["ok"] is False)


def test_sample2_unrelated_domain_no_code_change():
    import json, pathlib
    exp = json.loads((pathlib.Path(__file__).resolve().parents[2] / "backend/samples/sample_02_hospital_expansion/expected.json").read_text())
    c = client()
    cid = c.post("/api/samples/sample_02_hospital_expansion/load").json()["id"]
    c.post(f"/api/cases/{cid}/sample/advance?to=12")
    b = settle(c, cid, 120)
    assert b["jobs"]["advance"]["status"] == "done", b["jobs"]["advance"]
    v = verdicts(b)
    want = dict(exp["before_trip"], **exp["after_trip"])
    assert v == {k: tuple(x) for k, x in want.items()}
    assert b["overall"]["result"] == exp["overall"]
    text = json.dumps(b).lower()
    assert "credit card" not in text and "example client" not in text
