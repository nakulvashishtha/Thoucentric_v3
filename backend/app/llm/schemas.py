"""JSON schemas for every model job (structured outputs: every object closed, every field required)."""
from __future__ import annotations

S = {"type": "string"}
B = {"type": "boolean"}
N = {"type": "number"}
NN = {"anyOf": [{"type": "number"}, {"type": "null"}]}


def obj(**props) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def arr(item: dict) -> dict:
    return {"type": "array", "items": item}


FIGURE = obj(value=NN, low=NN, high=NN, unit=S, period=S, quote_span=S, locator=S)
DESCRIBE = obj(author_type=S, method_cited=B, original_source_named=B, original_source_name=S, published_date=S,
               data_as_of=S)

SCHEMAS = {
    "READ_FILE": obj(figures=arr(FIGURE), describe=DESCRIBE, sample_mix=arr(obj(group=S, share_pct=N))),
    "FRAME": obj(client_belief=S, decision=S, case_measure_name=S, case_measure_definition=S),
    "PLAN_HYPOTHESES": obj(ideas=arr(obj(
        text=S, fact_type={"type": "string", "enum": ["market", "client_operational"]}, measure_name=S, measure_unit=S,
        measure_definition=S, comparator={"type": "string", "enum": [">=", "<="]}, pass_line_value=N,
        pass_line_formula=S, assumptions=arr(obj(name=S, label=S, value=N, unit=S, min=NN, max=NN)),
        pass_line_source_type={"type": "string", "enum": ["client_goal", "benchmark", "estimate"]},
        pass_line_source_note=S, benchmark_query=S, must_have=B,
        recency_category={"type": "string", "enum": ["size_growth_price", "structural_timing"]}, tolerance_pct=N))),
    "ROUTE_NEEDS": obj(needs=arr(obj(
        idea=S, text=S, route={"type": "string", "enum": ["desk", "client", "expert"]},
        coverage={"type": "string", "enum": ["answered_by_client_file", "partly", "not_covered"]},
        covered_by_file=S, covered_locator=S, coverage_note=S)), sources=arr(obj(source_name=S, domain=S))),
    "GENERATE_QUERIES": obj(queries=arr(S)),
    "READ_SOURCE": obj(figures=arr(FIGURE), describe=DESCRIBE),
    "LINK_EVIDENCE": obj(links=arr(obj(idea=S, figure_index={"type": "integer"},
                                       role={"type": "string", "enum": ["supports_test", "context"]})),
                         derivations=arr(obj(op={"type": "string", "enum": ["ratio", "difference", "cagr"]}, a_ref=S,
                                             b_ref=S, years=NN, result_unit=S, rationale=S))),
    "DRAFT_FOLLOWUP": obj(question=S, what_we_have=S),
    "SUMMARISE": obj(sentences=arr(obj(text=S, evidence_ids=arr(S)))),
    "UNKNOWNS": obj(unknowns=arr(obj(idea=S, text=S))),
}

MAX_TOKENS = {"READ_FILE": 4000, "READ_SOURCE": 3000, "LINK_EVIDENCE": 2000, "GENERATE_QUERIES": 600,
              "ROUTE_NEEDS": 6000, "UNKNOWNS": 2000, "FRAME": 6000, "PLAN_HYPOTHESES": 12000,
              "DRAFT_FOLLOWUP": 6000, "SUMMARISE": 8000}


def normalise(job: str, out: dict) -> dict:
    """Turn the schema's closed shapes into the shapes the pipeline uses (same as the stored sample answers)."""
    if job == "READ_FILE":
        rows = out.get("sample_mix") or []
        out["sample_mix"] = {"sample": {r["group"]: r["share_pct"] for r in rows}, "target": {}} if rows else None
    if job == "PLAN_HYPOTHESES":
        for i in out.get("ideas") or []:
            if not i.get("pass_line_formula"):
                i["pass_line_formula"] = None
    if job == "LINK_EVIDENCE":
        for d in out.get("derivations") or []:
            for k in ("a_ref", "b_ref"):
                v = str(d.get(k) or "").strip()
                d[k] = int(v) if v.isdigit() else v
    return out
