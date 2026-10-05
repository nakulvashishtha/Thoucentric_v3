"""Engine unit tests. No I/O, no language model."""
import json
import pathlib

import pytest

from app.engine import checklist, convert, credibility, dedup, privacy, spotcheck, trips
from app.engine.addup import check_summary, sample_mix
from app.engine.numbers import fig_text, fmt, join, with_unit
from app.engine.verdict import classify, verdict_of
from app.engine.whatif import FormulaError, build_sliders, eval_formula, slider_range, what_if

REF = json.loads((pathlib.Path(__file__).resolve().parents[2] / "reference" / "recorded_backend_states.json").read_text())


def fig(eid, low, high=None, cr=False, calc=False, origin=None):
    high = low if high is None else high
    return {"evidence_id": eid, "low": low, "high": high, "client_reported": cr, "calculated": calc,
            "origin": origin or eid}


# ------------------------------------------------------------------ numbers
def test_fmt_matches_replica():
    assert fmt(2400) == "2,400"
    assert fmt(21.818181818181817) == "21.8"
    assert fmt(14.324609027821644) == "14.3"
    assert fmt(5.53) == "5.53"
    assert fmt(0.12345) == "0.1235"
    assert fmt(1234.56) == "1,234.6"
    assert fmt(None) == "?"
    assert with_unit(20, "% a year") == "20% a year"
    assert with_unit(12, "months") == "12 months"
    assert fig_text(12, 18, "% a year") == "12 to 18% a year"
    assert join(["a", "b", "c"]) == "a, b and c"


# ------------------------------------------------------------------ verdicts: the Sample 1 table
def test_sample1_verdict_table():
    ms = {"market": 2, "client_operational": 1}
    r = verdict_of([fig("E12", 12, 18), fig("E16", 13.8)], 20, ">=", 5, "market", "% a year", ms)
    assert r == ("fails", "high", "12 to 18% a year and 13.8% a year miss the target of at least 20% a year by more "
                 "than the close-call margin, and 2 separate sources agree.")
    r = verdict_of([], 24, "<=", 5, "client_operational", "months", ms)
    assert r[:2] == ("not_enough", "none")
    assert r[2] == "No usable evidence yet. This idea needs 1 separate source to compare with the target of at most 24 months."
    r = verdict_of([fig("E29", 21.818181818181817, cr=True, calc=True)], 24, "<=", 5, "client_operational", "months", ms)
    assert r[:2] == ("holds", "medium")
    assert r[2].endswith("Confidence stays at Fair because the evidence comes from the client.")
    assert verdict_of([fig("E24", 34, cr=True)], 30, ">=", 5, "client_operational", "%", ms)[:2] == ("holds", "medium")
    r = verdict_of([fig("E14", 9, 11), fig("E27", 10, 12)], 12, "<=", 5, "market", "months", ms)
    assert r == ("holds", "low", "10 to 12 months and 9 to 11 months meet the target of at most 12 months. It's a close "
                 "call: the range 10 to 12 months includes the target.")
    assert verdict_of([fig("E14", 9, 11), fig("E27", 10, 12)], 9, "<=", 5, "market", "months", ms)[:2] == ("fails", "low")


def test_verdict_edge_cases():
    ms = {"market": 2, "client_operational": 1}
    # duplicates (same origin) count once, so one market source is not enough
    r = verdict_of([fig("E1", 30, origin="G"), fig("E2", 31, origin="G")], 20, ">=", 5, "market", "%", ms)
    assert r[0] == "not_enough" and r[2].startswith("Only 1 separate source so far")
    assert classify(20, 20, 20, ">=", 5) == ("pass", True)          # exactly on the line is a close call
    assert classify(15, 25, 20, ">=", 5) == ("pass", True)          # range straddling the line
    assert classify(10, 18, 20, ">=", 5) == ("fail", False)
    r = verdict_of([fig("A", 30), fig("B", 10)], 20, ">=", 5, "market", "%", ms)
    assert r[:2] == ("conflicting", "low") and r[2].startswith("The sources disagree.")
    r = verdict_of([fig("A", 30, cr=True)], 20, ">=", 5, "client_operational", "%", ms)
    assert r[1] == "medium"                                          # client data capped at Fair
    r = verdict_of([fig("A", 30), fig("B", 31)], 20, ">=", 5, "market", "%", ms)
    assert r[:2] == ("holds", "high")


def test_whatif_checks_reproduced():
    b = REF["states"]["s10_added"]["bundle"]
    ev = {e["id"]: e for e in b["evidence"]}
    for chk in REF["meta"]["whatif_checks"]:
        got = what_if(b["hypotheses"], ev, b["rules"]["thresholds"]["minimum_sources"], chk["body"], b["overall"]["result"])
        assert got == chk["result"]


def test_sliders_and_formulas():
    b = REF["states"]["s10_added"]["bundle"]
    assert build_sliders(b["hypotheses"]) == b["sliders"]
    assert eval_formula("18 - build_months", {"build_months": 6}) == 12
    assert eval_formula("max(10, a * 2) / 4", {"a": 10}) == 5
    for bad in ("__import__('os')", "a ** 2", "open('x')", "a.b"):
        with pytest.raises(FormulaError):
            eval_formula(bad, {"a": 1})
    assert slider_range(20, {}) == [10, 30]
    assert slider_range(0, {}) == [0, 10]                           # -10 clamped at 0
    assert slider_range(5, {"slider_min": 1, "slider_max": 9}) == [1, 9]


# ------------------------------------------------------------------ conversion and derivations
def test_number_parsing_and_conversion():
    assert convert.parse_number("about 12 to 18%") == {"low": 12, "high": 18, "unit": "%"}
    assert convert.parse_number("1,500 crore")["low"] == 1.5e10
    assert convert.parse_number("12,5")["low"] == 12.5
    assert convert.convert(5.53, "crore cards", "crore cards") == (5.53, "same unit")
    assert convert.convert(1.5, "years", "months")[0] == 18
    assert convert.convert(0.3, "ratio", "%")[0] == pytest.approx(30)
    assert convert.convert(2, "lakh cards", "cards")[0] == 200000
    assert convert.convert(12, "% a year", "% a month")[0] == 1
    v, note = convert.convert(100, "USD", "months")
    assert v is None and note.startswith("different unit")


def test_derivations_and_unit_check():
    d = convert.derive("ratio", {"value": 2400, "unit": "INR"}, {"value": 110, "unit": "INR per month"}, None, "months")
    assert d["formula"] == "2,400 ÷ 110 = 21.8" and d["unit_ok"]
    d = convert.derive("cagr", {"value": 5.53, "unit": "crore cards", "period": "Dec 2019"},
                       {"value": 10.8, "unit": "crore cards", "period": "Dec 2024"}, 5, "% a year")
    assert d["formula"] == "(10.8 ÷ 5.53)^(1/5) − 1 = 14.3%" and d["years_ok"]
    assert d["value"] == pytest.approx(14.324609027821644)
    d = convert.derive("cagr", {"value": 5.53, "unit": "cards", "period": "2019"},
                       {"value": 10.8, "unit": "cards", "period": "2024"}, 4, "% a year")
    assert not d["years_ok"]
    d = convert.derive("difference", {"value": 10, "unit": "months"}, {"value": 4, "unit": "months"}, None, "months")
    assert d["value"] == 6 and d["unit_ok"]
    d = convert.derive("ratio", {"value": 10, "unit": "INR"}, {"value": 2, "unit": "cards"}, None, "months")
    assert not d["unit_ok"] and d["note"] == "unit check needs your confirmation"


# ------------------------------------------------------------------ credibility
REG = __import__("yaml").safe_load((pathlib.Path(__file__).resolve().parents[2] / "backend/config/source_registry.yaml").read_text())


def test_credibility_tiers():
    assert credibility.tier_for("rbi.org.in", "open_web", REG, "India")[0] == 1
    assert credibility.tier_for("rbi.org.in", "open_web", REG, "India")[1] == "rbi.org.in matches 'rbi.org.in' in the country pack IN"
    assert credibility.tier_for("data.gov.uk", "open_web", REG, "")[0] == 1
    assert credibility.tier_for("reuters.com", "open_web", REG, "")[0] == 3
    assert credibility.tier_for("random-blog.example", "open_web", REG, "")[0] == 4
    assert credibility.tier_for("", "firm_archive", REG, "")[0] == 2
    assert credibility.tier_for("", "client_file", REG, "")[0] is None
    plan = [{"domain": "press.sample", "tier": 3, "stated_by_consultant": True, "tier_reason": "Named outlets"}]
    t, why = credibility.tier_for("daily.press.sample", "open_web", REG, "", plan=plan)
    assert t == 3 and why == "Added to the source plan by the consultant as Tier 3: Named outlets"


def test_recency():
    from datetime import datetime, timezone
    now = datetime(2026, 10, 5, tzinfo=timezone.utc)
    assert credibility.recency("Dec 2025", "", 36, now)["recency_actual"] == "2025-12 (10 months old)"
    assert credibility.recency("2025", "", 36, now)["recency_actual"] == "2025-01 (21 months old)"
    assert credibility.recency("", "", 36, now)["recency_ok"] is False           # a missing date fails
    assert credibility.recency("2031-01", "", 36, now)["recency_ok"] is False    # a future date counts as missing
    assert credibility.recency("2019-01", "", 36, now)["recency_ok"] is False


# ------------------------------------------------------------------ dedup
def test_dedup_rules():
    items = [{"id": "E1", "url": "https://www.x.com/a?utm_source=q", "text": "alpha"},
             {"id": "E2", "url": "https://x.com/a/", "text": "beta"},
             {"id": "E3", "url": "https://y.com/b", "text": "Alpha "}]
    assert dedup.exact_copies(items) == {"E2": "E1", "E3": "E1"}
    read = [{"id": "E4", "seq": 4, "title": "Copy", "publisher": "News", "tier": 3, "text": "a b c",
             "figures": [{"value": 13.8}], "describe": {"original_source_named": True, "original_source_name": "Big Outlook"}},
            {"id": "E5", "seq": 5, "title": "Big Outlook", "publisher": "Firm", "tier": 2, "text": "d e f",
             "figures": [{"value": 13.8}], "describe": {}},
            {"id": "E6", "seq": 6, "title": "Other", "publisher": "Z", "tier": 2,
             "text": "one two three four five six seven eight nine ten", "figures": [], "describe": {}},
            {"id": "E7", "seq": 7, "title": "Other 2", "publisher": "Z", "tier": 2,
             "text": "one two three four five six seven eight nine ten eleven", "figures": [], "describe": {}}]
    orig, rules = dedup.group(read)
    assert orig == {"E4": "E5", "E7": "E6"}
    assert rules["E4"] == dedup.RULE_NAMED and rules["E7"] == dedup.RULE_SIMILAR


# ------------------------------------------------------------------ privacy
CASE = {"client_name": "Acme Holdings Ltd", "client_aliases": ["Acme"], "private_numbers": ["Rs 1,500 crore budget"]}
FILES = [{"filename": "f.csv", "kind": "initial", "figures": [{"value": 34, "unit": "%", "quote_span": "34%"},
                                                              {"value": 2025, "unit": "", "quote_span": "2025"}]}]


def test_privacy_filter():
    r = privacy.check_outbound("Can Acme Holdings Ltd grow? credit cards growth 2025 to 2030", CASE, FILES)
    assert r["sanitised"] == "Can the client grow? credit cards growth 2025 to 2030"
    assert r["removed"] == ["Acme Holdings Ltd"] and r["blocked"] == []      # the year 2025 passes
    assert privacy.check_outbound("market share 34% in India", CASE, FILES)["blocked"] == ["34%"]
    assert privacy.check_outbound("budget of 1,500 crore", CASE, FILES)["blocked"]
    assert privacy.check_outbound("about 34 banks", CASE, FILES)["blocked"] == []  # bare small integer is fine
    assert privacy.find_private("acme said", CASE, FILES) == ["Acme"]


# ------------------------------------------------------------------ checklist, spot check, trips
TH = REF["states"]["s10_added"]["bundle"]["rules"]["thresholds"]


def _item(**kw):
    base = {"origin_type": "firm_archive", "duplicate_of": None,
            "credibility_json": {"tier": 2, "traced": True, "recency_ok": True, "recency_actual": "2025-12 (10 months old)",
                                 "recency_window": 60, "matches_belief": False},
            "figures_json": [{"value": None, "low": 9, "high": 11, "unit": "months", "kind": "reported", "verified": True,
                              "verify_note": "found at para 1"}],
            "links": [{"hypothesis_code": "H4", "role": "supports_test", "figure_index": 0}]}
    base.update(kw)
    return base


IDEAS = {"H4": {"code": "H4", "must_have": False, "measure_unit": "months"},
         "H1": {"code": "H1", "must_have": True, "measure_unit": "% a year"}}


def test_checklist_auto_and_test9():
    it = _item()
    tests = checklist.run(it, it["links"][0], IDEAS["H4"], IDEAS, False, TH, [])
    assert checklist.passes(tests) and len(tests) == 9
    it = _item(links=[{"hypothesis_code": "H1", "role": "supports_test", "figure_index": 0}])
    tests = checklist.run(it, it["links"][0], IDEAS["H1"], IDEAS, False, TH, [])
    assert not checklist.passes(tests) and tests[8]["actual"] == "supports a critical idea"


def test_checklist_never_auto():
    for origin in ("client_file", "expert_note"):
        it = _item(origin_type=origin)
        assert not checklist.passes(checklist.run(it, it["links"][0], IDEAS["H4"], IDEAS, False, TH, []))
    cred = dict(_item()["credibility_json"], tier=3, traced=True)
    it = _item(credibility_json=cred, origin_type="open_web")
    assert not checklist.passes(checklist.run(it, it["links"][0], IDEAS["H4"], IDEAS, False, TH, []))  # not corroborated
    assert checklist.passes(checklist.run(it, it["links"][0], IDEAS["H4"], IDEAS, True, TH, []))
    it = _item(credibility_json=dict(cred, tier=4))
    assert not checklist.passes(checklist.run(it, it["links"][0], IDEAS["H4"], IDEAS, True, TH, []))
    it = _item(credibility_json=dict(_item()["credibility_json"], recency_ok=False, recency_actual="no date"))
    assert not checklist.passes(checklist.run(it, it["links"][0], IDEAS["H4"], IDEAS, False, TH, []))
    it = _item(figures_json=[{"value": 3, "unit": "USD", "verified": True, "verify_note": "found"}])
    tests = checklist.run(it, it["links"][0], IDEAS["H4"], IDEAS, False, TH, [])
    assert tests[4]["pass"] is False                                  # an unconvertible unit goes to a person
    it = _item()
    assert not checklist.passes(checklist.run(it, it["links"][0], IDEAS["H4"], IDEAS, False, TH, ["Acme"]))


def test_spot_check():
    ids = ["E14", "E15", "E18", "E19", "E21", "E22"]
    assert spotcheck.pick(ids, 2, 0, 1) == ["E14"]                  # the recorded pick with seed 2
    assert spotcheck.pick(ids, 2, 0, 1) == spotcheck.pick(ids, 2, 0, 1)
    assert spotcheck.size(0, 0.2, 2) == 0
    assert spotcheck.size(10, 0.2, 2) == 2 and spotcheck.size(20, 0.2, 2) == 4 and spotcheck.size(1, 0.2, 2) == 1


def test_trip_limits():
    assert trips.check(0, False, "") is None and trips.check(1, False, "") is None
    assert trips.check(2, False, "") is not None
    assert trips.check(2, True, "  ") is not None
    assert trips.check(2, True, "client changed the scope") is None
    assert trips.check(3, True, "again") is not None


def test_summary_check_and_sample_mix():
    probs = check_summary([{"text": "Growth is 13.8% a year.", "evidence_ids": ["E1"]}], {"E1"}, {13.8}, {}, {})
    assert probs == []
    assert check_summary([{"text": "x", "evidence_ids": ["E9"]}], {"E1"}, set(), {}, {})
    assert check_summary([{"text": "Growth is 55%.", "evidence_ids": ["E1"]}], {"E1"}, {13.8}, {}, {})
    m = sample_mix({"existing customers": 42, "new customers": 58}, {"existing customers": 42, "new customers": 58}, 10)
    assert m["passes"] and m["rows"][0]["difference"] == 0
    assert not sample_mix({"a": 70}, {"a": 42}, 10)["passes"]
