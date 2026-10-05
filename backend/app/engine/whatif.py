"""Pass-line formulas, the adding-up rule, what-if recalculation and slider ranges.

Formulas are parsed with Python's ast module and evaluated by a restricted evaluator: numbers, named assumptions,
+ - * /, unary minus, parentheses, min and max. Anything else is refused."""
from __future__ import annotations

import ast
import operator

from .verdict import verdict_of

_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


class FormulaError(ValueError):
    pass


def eval_formula(expr: str, values: dict) -> float:
    try:
        tree = ast.parse(str(expr).strip(), mode="eval")
    except SyntaxError as e:
        raise FormulaError(f"Can't read the formula {expr!r}") from e

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id in values:
                return float(values[node.id])
            raise FormulaError(f"Unknown name {node.id!r} in the formula")
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
            return _BIN[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            v = ev(node.operand)
            return -v if isinstance(node.op, ast.USub) else v
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("min", "max")
                and not node.keywords and len(node.args) >= 2):
            args = [ev(a) for a in node.args]
            return min(args) if node.func.id == "min" else max(args)
        raise FormulaError("Only numbers, named assumptions, + - * /, brackets, min and max are allowed")

    return ev(tree)


def check_formula(expr: str, names: list[str]) -> None:
    """Raise FormulaError if the formula uses anything not allowed (names are checked against the assumptions)."""
    eval_formula(expr, {n: 1.0 for n in names})


def line_of(h: dict, assumptions: dict | None = None) -> float:
    vals = {a["name"]: float(a["value"]) for a in (h.get("assumptions_json") or [])}
    if assumptions:
        for k, v in assumptions.items():
            if k in vals:
                vals[k] = float(v)
    if h.get("pass_line_formula"):
        return eval_formula(h["pass_line_formula"], vals)
    return float(h.get("pass_line_value") or 0.0)


OVERALL_LABELS = {"not_achievable": "Not achievable", "consultant_decides": "Needs your decision",
                  "achievable": "Achievable"}


def adding_up(rows: list[dict]) -> tuple[str, str]:
    """rows: [{code, must_have, result}]. Returns (overall, sentence)."""
    from .numbers import join
    must = [r for r in rows if r["must_have"]]
    failed = [r["code"] for r in must if r["result"] == "fails"]
    unsettled = [r["code"] for r in must if r["result"] in ("conflicting", "not_enough")]
    if failed:
        return "not_achievable", (f"Critical idea {join(failed)} is not supported by the evidence gathered so far, "
                                  "so the case does not hold at the agreed thresholds.")
    if unsettled:
        return "consultant_decides", (f"Critical idea {join(unsettled)} isn't settled yet, so the evidence is "
                                      "inconclusive on this point.")
    return "achievable", "Every critical idea is supported by the evidence at the agreed thresholds."


def what_if(hypotheses: list[dict], evidence_by_id: dict, min_sources: dict, body: dict,
            current_overall: str | None) -> dict:
    """Recalculate every verdict under changed assumptions or pass lines. Nothing is written."""
    assumptions = body.get("assumptions") or {}
    lines = body.get("pass_lines") or {}
    rows = []
    for h in hypotheses:
        if h.get("removed_reason"):
            continue
        line = line_of(h, assumptions)
        if h["code"] in lines and lines[h["code"]] is not None:
            line = float(lines[h["code"]])
        d = (h.get("verdict") or {}).get("detail_json") or {}
        figs = [{"low": f["low"], "high": f["high"], "client_reported": f.get("client_reported"),
                 "calculated": f.get("calculated"), "evidence_id": f["evidence_id"],
                 "origin": (evidence_by_id.get(f["evidence_id"]) or {}).get("original_group_id") or f["evidence_id"]}
                for f in d.get("figures") or []]
        result, conf, why = verdict_of(figs, line, h["comparator"], h["tolerance_pct"], h["fact_type"],
                                       h["measure_unit"], min_sources)
        cur = h.get("verdict") or {}
        rows.append({"code": h["code"], "text": h["text"], "must_have": h["must_have"], "unit": h["measure_unit"],
                     "comparator": h["comparator"], "line": line, "locked_line": h.get("line"),
                     "result": result, "confidence": conf, "why": why,
                     "evidence_ids": [f["evidence_id"] for f in figs],
                     "changed": cur.get("result") != result or cur.get("confidence") != conf})
    overall, text = adding_up(rows)
    return {"ideas": rows, "overall": overall, "overall_label": OVERALL_LABELS[overall], "rule_applied": text,
            "overall_changed": bool(current_overall and current_overall != overall), "locked_plan_unchanged": True}


def slider_range(v: float, h: dict) -> list[float]:
    if h.get("slider_min") is not None and h.get("slider_max") is not None:
        return [float(h["slider_min"]), float(h["slider_max"])]
    lo = -10.0 if v == 0 else min(v * 0.5, v * 1.5)
    hi = 10.0 if v == 0 else max(v * 0.5, v * 1.5)
    lo = max(0.0, lo)
    return [round(lo * 1e4) / 1e4, round(hi * 1e4) / 1e4]


def build_sliders(hypotheses: list[dict]) -> list[dict]:
    out = []
    for h in hypotheses:
        if h.get("removed_reason"):
            continue
        for a in h.get("assumptions_json") or []:
            v = float(a["value"])
            lo, hi = (a.get("min"), a.get("max"))
            if lo is None or hi is None:
                lo, hi = slider_range(v, {})
            out.append({"kind": "assumption", "key": a["name"], "label": a.get("label") or a["name"],
                        "idea": h["code"], "value": v, "unit": a.get("unit") or "", "min": float(lo), "max": float(hi)})
        line = float(h.get("line") if h.get("line") is not None else line_of(h))
        lo, hi = slider_range(line, h)
        out.append({"kind": "pass_line", "key": h["code"], "label": f"{h['code']} pass line ({h['measure_name']})",
                    "idea": h["code"], "value": line, "unit": h["measure_unit"], "min": lo, "max": hi,
                    "formula": h.get("pass_line_formula") or ""})
    return out
