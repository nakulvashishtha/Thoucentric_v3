"""A blank case in live mode, end to end, with a scripted stand-in model and a mocked search service.
It proves the live wiring (framing, planning, benchmark search, routing, Tavily results, reading, linking, the
checklist, a follow-up and the summary) works on a case with no stored answers. No real call is made."""
import json
import types

from helpers import client, settle, verdicts
from app import db
from app.llm import live as live_mod
from app.search import live as search_live

PAGES = {
    "growth": ("https://www.stats.gov.example/retail/2025", "Official retail statistics",
               "Grocery sales in Santiago grew 6.5% a year between 2021 and 2025, according to the national statistics office. "
               "Figures come from monthly retail returns."),
    "growth2": ("https://www.reuters.com/markets/chile-grocery", "Chile grocery outlook",
                "Analysts expect grocery sales in Santiago to grow 5 to 7% a year to 2030, based on a survey of retailers."),
    "bench": ("https://www.oecd.org/retail/store-payback", "Store payback benchmarks",
              "New grocery stores in Latin American capitals typically pay back in 30 to 40 months, a study of 200 openings found."),
}


def fake_llm(self, job, key, p):
    if job == "READ_FILE":
        return {"figures": [{"value": 12, "low": None, "high": None, "unit": "stores", "period": "2026", "quote_span": "12",
                             "locator": "B2"}], "describe": {"author_type": "client", "method_cited": False,
                             "original_source_named": False, "original_source_name": "", "published_date": "2026-01",
                             "data_as_of": ""}, "sample_mix": None}
    if job == "FRAME":
        return {"client_belief": "Grocery demand in Santiago grows fast.", "decision": "Open 20 stores?",
                "case_measure_name": "Grocery sales, Santiago", "case_measure_definition": "Annual grocery sales value."}
    if job == "PLAN_HYPOTHESES":
        return {"ideas": [
            {"text": "Demand grows: grocery sales grow at least 4% a year.", "fact_type": "market", "measure_name": "Sales growth",
             "measure_unit": "% a year", "measure_definition": "Annual growth.", "comparator": ">=", "pass_line_value": 4,
             "pass_line_formula": None, "assumptions": [], "pass_line_source_type": "estimate", "pass_line_source_note": "Plan.",
             "benchmark_query": "", "must_have": True, "recency_category": "size_growth_price", "tolerance_pct": 5},
            {"text": "Stores pay back within 36 months.", "fact_type": "market", "measure_name": "Payback", "measure_unit": "months",
             "measure_definition": "Months to pay back.", "comparator": "<=", "pass_line_value": 36, "pass_line_formula": None,
             "assumptions": [], "pass_line_source_type": "benchmark", "pass_line_source_note": "Benchmark.",
             "benchmark_query": "grocery store payback benchmark", "must_have": False,
             "recency_category": "structural_timing", "tolerance_pct": 5}]}
    if job == "ROUTE_NEEDS":
        return {"needs": [{"idea": "H1", "text": "Growth in grocery sales in Santiago.", "route": "desk", "coverage": "not_covered",
                           "covered_by_file": "", "covered_locator": "", "coverage_note": ""},
                          {"idea": "H2", "text": "Typical payback of new grocery stores.", "route": "expert",
                           "coverage": "not_covered", "covered_by_file": "", "covered_locator": "", "coverage_note": ""}],
                "sources": [{"source_name": "Statistics office", "domain": "stats.gov.example"}]}
    if job == "GENERATE_QUERIES":
        return {"queries": ["Santiago grocery sales growth 2021 to 2025"]}
    if job == "READ_SOURCE":
        t = p["text"]
        if "6.5%" in t:
            f = {"value": 6.5, "low": None, "high": None, "unit": "% a year", "period": "2021 to 2025", "quote_span": "grew 6.5% a year"}
        elif "5 to 7%" in t:
            f = {"value": None, "low": 5, "high": 7, "unit": "% a year", "period": "2025 to 2030", "quote_span": "grow 5 to 7% a year"}
        else:
            f = {"value": None, "low": 30, "high": 40, "unit": "months", "period": "", "quote_span": "pay back in 30 to 40 months"}
        f["locator"] = "para 1"
        return {"figures": [f], "describe": {"author_type": "statistics office", "method_cited": True, "original_source_named": False,
                                             "original_source_name": "", "published_date": "2026-02", "data_as_of": "2025"}}
    if job == "LINK_EVIDENCE":
        return {"links": [{"idea": "H1", "figure_index": 0, "role": "supports_test"}], "derivations": []}
    if job == "DRAFT_FOLLOWUP":
        return {"question": "How long did your last stores take to pay back?", "what_we_have": "From you we already have the store list."}
    if job == "SUMMARISE":
        ids = [f["id"] for i in p["ideas"] for f in i["evidence"]]
        return {"sentences": [{"text": "Two sources put sales growth at 6.5% a year and 5 to 7% a year, above the 4% a year target.",
                               "evidence_ids": ids[:2]}]}
    if job == "UNKNOWNS":
        return {"unknowns": [{"idea": "H1", "text": "Growth outside the city centre."}]}
    raise AssertionError(job)


def fake_post(url, json=None, headers=None, timeout=None):
    q = json["query"].lower()
    keys = ["bench"] if "payback" in q else ["growth", "growth2"]
    return types.SimpleNamespace(status_code=200, json=lambda: {"results": [
        {"url": PAGES[k][0], "title": PAGES[k][1], "content": PAGES[k][2] * 3, "published_date": "2026-02-01"} for k in keys]})


def test_blank_case_runs_live_with_stand_ins(monkeypatch):
    for k, v in {"ANTHROPIC_API_KEY": "t", "TAVILY_API_KEY": "t", "MODEL_FAST": "claude-haiku-4-5",
                 "MODEL_SMART": "claude-sonnet-5-5", "MODE": "live"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(live_mod.LiveLLM, "run", fake_llm)
    monkeypatch.setattr(search_live.httpx, "post", fake_post)
    c = client()
    cid = c.post("/api/cases").json()["id"]
    assert db.case_get(cid)["mode"] == "live"
    c.put(f"/api/cases/{cid}", json={"client_name": "Acme Retail", "client_aliases": ["Acme"], "country": "Chile",
                                     "industry": "Grocery retail", "function": "Strategy", "private_numbers": ["USD 40 million budget"],
                                     "raw_ask": "Acme Retail wants to know if 20 new stores in Santiago will pay back."})
    c.post(f"/api/cases/{cid}/files", files={"file": ("stores.csv", b"metric,value\nStores open,12\n")}, data={"kind": "initial"})
    for path, body in (("read-ask", None), ("frame/confirm", None), ("plan/lock", {"ticked": True})):
        r = c.post(f"/api/cases/{cid}/{path}", json=body)
        assert r.status_code == 200, (path, r.json())
        b = settle(c, cid)
        assert not [j for j in b["jobs"].values() if j["status"] == "failed"], b["jobs"]
    bench = [e for e in b["evidence"] if e["origin_type"] == "benchmark"]
    assert bench and bench[0]["tier_label"] == "Official"                    # oecd.org is Tier 1 in the global list
    assert b["needs"][0]["queries_json"][0]["query"] == "Santiago grocery sales growth 2021 to 2025"
    assert c.post(f"/api/cases/{cid}/requests/mark-sent", json={"reviewed": True}).status_code == 200
    b = settle(c, cid)
    while not b["progress"]["done"]["6"]:
        b = settle(c, cid)
    assert not [j for j in b["jobs"].values() if j["status"] == "failed"], b["jobs"]
    web = [e for e in b["evidence"] if e["origin_type"] == "open_web"]
    assert {e["tier_label"] for e in web} == {"Official", "Press"}
    assert all(f["verified"] for e in web for f in e["figures_json"])
    assert [e for e in b["evidence"] if e["status"] == "pending" and e["source_name"] == "Awaiting an expert"]
    for e in b["evidence"]:
        if e["status"] == "needs_decision":
            c.post(f"/api/cases/{cid}/evidence/{e['id']}/decision", json={"action": "approve"})
        if e["bucket"] == "auto":
            c.post(f"/api/cases/{cid}/review/seen/{e['id']}")
    c.post(f"/api/cases/{cid}/review/confirm-sources", json={"ticked": True})
    r = c.post(f"/api/cases/{cid}/test/run")
    assert r.status_code == 200, r.json()
    v = verdicts(c.get(f"/api/cases/{cid}").json())
    assert v["H1"][0] == "holds"
    assert c.post(f"/api/cases/{cid}/trips", json={"hypothesis": "H2"}).status_code == 200
    b = settle(c, cid)
    assert b["trips"][0]["question"]
    c.post(f"/api/cases/{cid}/addup/run")
    b = settle(c, cid)
    assert b["overall"]["result"] == "achievable" and b["summary"]["source"] == "llm"
    md = c.get(f"/api/cases/{cid}/export?format=md").text
    assert "Achievable" in md
