"""Verdict and confidence for one idea. Deterministic; no language model anywhere in this module.

classify() and verdict_of() are ported from reference/offline_api_replica.js (which reproduces the original server),
so the results and the "why" sentences match it character for character."""
from __future__ import annotations

from .numbers import fig_text, fmt, join, with_unit

RESULT_WORDS = {"holds": "Supported", "fails": "Not supported", "conflicting": "Sources disagree",
                "not_enough": "Not enough evidence"}
CONF_WORDS = {"high": "Strong", "medium": "Fair", "low": "Weak"}


def classify(low: float, high: float, L: float, cmp: str, tol: float) -> tuple[str, bool]:
    """Return (side, boundary) for one figure against pass line L."""
    T = abs(L) * tol / 100.0
    d = 1 if cmp == ">=" else -1
    if low != high and low <= L <= high:
        return ("pass" if ((low + high) / 2 - L) * d >= 0 else "fail"), True
    nearest = low if abs(low - L) <= abs(high - L) else high
    margin = (nearest - L) * d
    return ("pass" if margin >= 0 else "fail"), abs(margin) <= T


def verdict_of(figs: list[dict], L: float, cmp: str, tol: float, fact_type: str, unit: str,
               min_sources: dict | None = None) -> tuple[str, str, str]:
    """figs: [{low, high, origin, client_reported, calculated}]. Returns (result, confidence, why)."""
    min_sources = min_sources or {}
    n = len({f["origin"] for f in figs})
    need = min_sources.get(fact_type) or (2 if fact_type == "market" else 1)
    target = f"the target of {'at least' if cmp == '>=' else 'at most'} {with_unit(L, unit)}"
    figures = join(sorted({fig_text(f['low'], f['high'], unit) for f in figs}))
    if n < need:
        if n == 0:
            why = (f"No usable evidence yet. This idea needs {need} separate source{'s' if need > 1 else ''} "
                   f"to compare with {target}.")
        else:
            what = "market figure" if fact_type == "market" else "idea"
            why = f"Only {n} separate source so far ({figures}). This {what} needs {need}."
        return "not_enough", "none", why
    cls = []
    for f in figs:
        side, b = classify(f["low"], f["high"], L, cmp, tol)
        cls.append({"side": side, "b": b, "straddles": f["low"] != f["high"] and f["low"] <= L <= f["high"],
                    "text": fig_text(f["low"], f["high"], unit)})
    sides = {c["side"] for c in cls}
    boundary = any(c["b"] for c in cls)
    if len(sides) == 2:
        p = [c["text"] for c in cls if c["side"] == "pass"]
        fl = [c["text"] for c in cls if c["side"] == "fail"]
        why = (f"The sources disagree. {join(p)} meet{'s' if len(p) == 1 else ''} {target}, "
               f"but {join(fl)} do{'es' if len(fl) == 1 else ''} not.")
        return "conflicting", "low", why
    res = "holds" if "pass" in sides else "fails"
    single_calc = fact_type == "market" and n == 1 and all(f.get("calculated") for f in figs)
    if boundary or single_calc:
        conf = "low"
    elif all(f.get("client_reported") for f in figs) or n < 2:
        conf = "medium"
    else:
        conf = "high"
    verb = "meet" if res == "holds" else "miss"
    if len(figs) == 1:
        verb += "es" if verb == "miss" else "s"
    why = f"{figures} {verb} {target}"
    st = [c["text"] for c in cls if c["b"] and c["straddles"]]
    nr = [c["text"] for c in cls if c["b"] and not c["straddles"]]
    if st or nr:
        parts = []
        if st:
            parts.append(f"the range {join(st)} include{'s' if len(st) == 1 else ''} the target")
        if nr:
            parts.append(f"{join(nr)} {'is' if len(nr) == 1 else 'are'} within the {fmt(tol)}% close-call margin")
        why += ". It's a close call: " + " and ".join(parts)
    else:
        why += " by more than the close-call margin"
    if single_calc:
        why += ". It rests on one calculated figure"
    if conf == "medium":
        why += (". Confidence stays at Fair because the evidence comes from the client"
                if all(f.get("client_reported") for f in figs) else ". There's only one separate source")
    elif conf == "high":
        why += f", and {n} separate sources agree"
    why += "."
    return res, conf, why[0].upper() + why[1:]


def reason_codes(result: str, confidence: str, figs: list[dict], L: float, cmp: str, tol: float,
                 fact_type: str) -> list[str]:
    if result == "not_enough":
        return ["NOT_ENOUGH_SOURCES"]
    if result == "conflicting":
        return ["CONFLICTING"]
    n = len({f["origin"] for f in figs})
    boundary = any(classify(f["low"], f["high"], L, cmp, tol)[1] for f in figs)
    single_calc = fact_type == "market" and n == 1 and all(f.get("calculated") for f in figs)
    codes = []
    if boundary:
        codes.append("BOUNDARY")
    if single_calc:
        codes.append("SINGLE_CALCULATED")
    if codes:
        return codes
    codes.append("ALL_PASS_CLEAR" if result == "holds" else "ALL_FAIL_CLEAR")
    if confidence == "medium":
        codes.append("CLIENT_REPORTED_CAP" if all(f.get("client_reported") for f in figs) else "SINGLE_SOURCE")
    elif confidence == "high":
        codes.append("INDEPENDENT_AGREE")
    return codes


def detail_figures(figs: list[dict], L: float, cmp: str, tol: float, unit: str) -> list[dict]:
    out = []
    for f in figs:
        side, b = classify(f["low"], f["high"], L, cmp, tol)
        figure = fmt(f["low"]) if f["low"] == f["high"] else f"{fmt(f['low'])} to {fmt(f['high'])}"
        out.append({"evidence_id": f["evidence_id"], "figure": figure, "side": side, "boundary": b,
                    "straddles": f["low"] != f["high"] and f["low"] <= L <= f["high"],
                    "text": fig_text(f["low"], f["high"], unit), "low": f["low"], "high": f["high"],
                    "client_reported": bool(f.get("client_reported")), "calculated": bool(f.get("calculated"))})
    return out


def headline(code: str, result: str, confidence: str, why: str) -> str:
    """The History line for a verdict, e.g. 'H1: Not supported, confidence Strong. ...'"""
    conf = f", confidence {CONF_WORDS[confidence]}" if confidence != "none" else ""
    return f"{code}: {RESULT_WORDS[result]}{conf}. {why}"
