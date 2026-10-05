"""Checks around the answer: the summary citation check, the template summary and the sample-mix check."""
from __future__ import annotations

import re

from .numbers import fmt
from .verdict import CONF_WORDS, RESULT_WORDS

_NUM = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)")


def allowed_numbers(hypotheses: list[dict], evidence: list[dict], calcs: list[dict]) -> set[float]:
    vals: set[float] = set()

    def add(v):
        if v is None:
            return
        v = float(v)
        vals.update({v, round(v, 1), round(v), round(v, 2)})

    for h in hypotheses:
        add(h.get("line"))
        add(h.get("tolerance_pct"))
        for a in h.get("assumptions_json") or []:
            add(a.get("value"))
        for f in ((h.get("verdict") or {}).get("detail_json") or {}).get("figures") or []:
            add(f.get("low"))
            add(f.get("high"))
        for v in re.findall(r"\d+(?:\.\d+)?", h.get("pass_line_formula") or ""):
            add(v)
    for e in evidence:
        for f in e.get("figures_json") or []:
            for k in ("value", "low", "high"):
                add(f.get(k))
    for c in calcs:
        add(c.get("result_value"))
    return vals


def check_summary(sentences: list[dict], evidence_ids: set[str], allowed: set[float],
                  verdicts: dict[str, dict], cited_ideas: dict[str, set[str]]) -> list[str]:
    """Return a list of problems; empty means every sentence passed."""
    problems = []
    if not sentences:
        return ["The summary is empty."]
    for i, s in enumerate(sentences, 1):
        ids = s.get("evidence_ids") or []
        if not ids:
            problems.append(f"Sentence {i} cites no evidence.")
        for eid in ids:
            if eid not in evidence_ids:
                problems.append(f"Sentence {i} cites {eid}, which doesn't exist.")
        for raw in _NUM.findall(s.get("text") or ""):
            v = float(raw.replace(",", ""))
            if 1900 <= v <= 2100 and v == int(v):
                continue
            if not any(abs(v - a) < 1e-6 for a in allowed):
                problems.append(f"Sentence {i} uses the number {raw}, which isn't in the data.")
        text = (s.get("text") or "").lower()
        for eid in ids:
            for code in cited_ideas.get(eid, set()):
                r = (verdicts.get(code) or {}).get("result")
                if r == "fails" and re.search(r"\b(is|are) supported\b|\bholds\b", text):
                    problems.append(f"Sentence {i} says {code} is supported, but the result is Not supported.")
                if r == "holds" and re.search(r"\bnot supported\b|\bfails\b", text):
                    problems.append(f"Sentence {i} says {code} is not supported, but the result is Supported.")
    return problems


def template_summary(hypotheses: list[dict]) -> list[dict]:
    out = []
    for h in hypotheses:
        v = h.get("verdict")
        if h.get("removed_reason") or not v:
            continue
        conf = f", confidence {CONF_WORDS[v['confidence']]}" if v["confidence"] != "none" else ""
        out.append({"text": f"{h['code']} ({h['measure_name']}): {RESULT_WORDS[v['result']]}{conf}. {v['why']}",
                    "evidence_ids": v.get("evidence_ids") or []})
    return [s for s in out if s["evidence_ids"]]


def sample_mix(sample: dict, target: dict, threshold: float, target_note: str = "") -> dict:
    rows = []
    for dim, sv in sample.items():
        if dim not in target:
            continue
        diff = abs(float(sv) - float(target[dim]))
        rows.append({"dimension": dim, "sample": float(sv), "target": float(target[dim]),
                     "difference": round(diff, 4), "flag": diff > threshold})
    return {"rows": rows, "passes": bool(rows) and not any(r["flag"] for r in rows), "threshold": threshold,
            "target_note": target_note}


def unknown_for_weak(code: str, result: str, confidence: str) -> str:
    return (f"The result ({RESULT_WORDS[result]}"
            f"{', confidence ' + CONF_WORDS[confidence] if confidence != 'none' else ''}) rests on thin or "
            "close-call evidence. More evidence would settle it.")


__all__ = ["allowed_numbers", "check_summary", "template_summary", "sample_mix", "unknown_for_weak", "fmt"]
