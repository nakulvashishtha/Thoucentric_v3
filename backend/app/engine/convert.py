"""Number normalisation, the safe unit-conversion table and derived figures (ratio, difference, cagr).

No currency conversion and nothing outside the table below: anything else goes to a person."""
from __future__ import annotations

import re

from .numbers import fmt

SCALES = {"thousand": 1e3, "k": 1e3, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "crore": 1e7, "crores": 1e7, "cr": 1e7,
          "million": 1e6, "mn": 1e6, "m": 1e6, "billion": 1e9, "bn": 1e9, "b": 1e9}

_NUM = r"[-+]?\d[\d,]*(?:\.\d+)?|[-+]?\d+(?:,\d+)?"


def parse_number(text: str) -> dict | None:
    """'about 12 to 18%' -> {low:12, high:18, unit:'%'}; '1,500 crore' -> {low:1.5e10...}; handles decimal commas."""
    if text is None:
        return None
    s = str(text).strip().lower().replace("–", "-").replace("—", "-")
    s = re.sub(r"^(about|approximately|approx\.?|around|roughly|nearly|almost|~)\s*", "", s)
    m = re.match(r"^(" + _NUM + r")\s*(?:%|percent)?\s*(?:to|-|and)\s*(" + _NUM + r")(.*)$", s)
    if m:
        lo, hi, rest = _num(m.group(1)), _num(m.group(2)), m.group(3)
    else:
        m = re.match(r"^(" + _NUM + r")(.*)$", s)
        if not m:
            return None
        lo = hi = _num(m.group(1))
        rest = m.group(2)
    rest = rest.strip()
    scale = 1.0
    w = rest.split(" ", 1)[0] if rest else ""
    if w in SCALES and w not in ("m", "b", "k") or (w in ("k", "m", "b") and len(rest) == 1):
        scale = SCALES[w]
        rest = rest[len(w):].strip()
    return {"low": lo * scale, "high": hi * scale, "unit": rest}


def _num(t: str) -> float:
    t = t.strip()
    if re.fullmatch(r"[-+]?\d+,\d{1,2}", t):          # decimal comma: 12,5
        return float(t.replace(",", "."))
    return float(t.replace(",", ""))


# ---------------------------------------------------------------------------------------------------- units
_PERCENT = {"%", "percent", "per cent", "pct"}
_PER_YEAR = ("a year", "per year", "per annum", "p.a.", "pa", "yearly", "annual", "/year", "/yr", "per yr")
_PER_MONTH = ("a month", "per month", "monthly", "/month", "/mo")


def unit_key(u: str) -> dict:
    """Split a free-form unit into {scale, base, rate}. rate is 'year', 'month' or ''."""
    s = (u or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    rate = ""
    for p in _PER_YEAR:
        if s.endswith(" " + p) or s.endswith(p) and p.startswith("/") or s == p:
            rate, s = "year", s[: -len(p)].strip()
            break
    else:
        for p in _PER_MONTH:
            if s.endswith(" " + p) or s.endswith(p) and p.startswith("/") or s == p:
                rate, s = "month", s[: -len(p)].strip()
                break
    scale = 1.0
    first = s.split(" ", 1)[0] if s else ""
    if first in SCALES and first not in ("m", "b", "k"):
        scale = SCALES[first]
        s = s[len(first):].strip()
    if s in _PERCENT or s.startswith("%"):
        s = "%"
    elif s in ("ratio", "share", "fraction", "x"):
        s = "ratio"
    elif s in ("month", "months", "mo", "mos"):
        s = "months"
    elif s in ("year", "years", "yr", "yrs"):
        s = "years"
    elif s.endswith("s") and not s.endswith("ss") and len(s) > 3:
        s = s[:-1]
    return {"scale": scale, "base": s, "rate": rate}


def convert(value: float, from_unit: str, to_unit: str) -> tuple[float | None, str]:
    """Return (converted value, note). note is 'same unit', 'converted ...', or a reason it cannot convert."""
    a, b = unit_key(from_unit), unit_key(to_unit)
    if a == b:
        return value, "same unit"
    v = value * a["scale"] / b["scale"]
    base_a, base_b = a["base"], b["base"]
    if base_a == "ratio" and base_b == "%":
        v, base_a = v * 100.0, "%"
    elif base_a == "%" and base_b == "ratio":
        v, base_a = v / 100.0, "ratio"
    if base_a == "months" and base_b == "years" and a["rate"] == b["rate"]:
        v, base_a = v / 12.0, "years"
    elif base_a == "years" and base_b == "months" and a["rate"] == b["rate"]:
        v, base_a = v * 12.0, "months"
    if base_a != base_b:
        return None, f"different unit ({from_unit or 'none'})"
    if a["rate"] != b["rate"]:
        if base_a == "%":                          # a growth or share rate per period cannot be rescaled safely
            if not a["rate"] and b["rate"] == "year":
                return None, f"different unit ({from_unit})"
        if a["rate"] == "year" and b["rate"] == "month":
            v = v / 12.0
        elif a["rate"] == "month" and b["rate"] == "year":
            v = v * 12.0
        else:
            return None, f"different unit ({from_unit or 'none'})"
    return v, f"converted from {from_unit}"


# ---------------------------------------------------------------------------------------------------- derivations
def _result_unit(op: str, a_unit: str, b_unit: str) -> str | None:
    a, b = unit_key(a_unit), unit_key(b_unit)
    if op == "cagr":
        return "% a year" if (a["base"] == b["base"]) else None
    if op == "difference":
        return a_unit if a == b else None
    if op == "ratio":
        if a["base"] == b["base"] and not a["rate"] and b["rate"]:
            return {"month": "months", "year": "years"}[b["rate"]]
        if a == b:
            return "ratio"
        if b["base"] in ("months", "years") and not b["rate"]:
            return f"{a_unit} per {b['base'][:-1]}"
    return None


def derive(op: str, a: dict, b: dict, years: float | None, result_unit: str) -> dict:
    """a and b are figures {value|low/high, unit, period}. Returns the calculated figure dict (kind 'calculated')."""
    av = float(a["value"] if a.get("value") is not None else a["low"])
    bv = float(b["value"] if b.get("value") is not None else b["low"])
    note = ""
    years_ok = True
    if op == "ratio":
        if bv == 0:
            raise ValueError("Can't divide by zero")
        value = av / bv
        formula = f"{fmt(av)} ÷ {fmt(bv)} = {fmt(value)}"
    elif op == "difference":
        value = av - bv
        formula = f"{fmt(av)} − {fmt(bv)} = {fmt(value)}"
    elif op == "cagr":
        if not years or av <= 0:
            raise ValueError("A growth rate needs a start value above zero and a number of years")
        value = ((bv / av) ** (1.0 / float(years)) - 1.0) * 100.0
        formula = f"({fmt(bv)} ÷ {fmt(av)})^(1/{fmt(years)}) − 1 = {fmt(value)}%"
        ya, yb = _year_of(a.get("period")), _year_of(b.get("period"))
        if ya is not None and yb is not None and abs((yb - ya) - float(years)) > 1e-9:
            years_ok = False
            note = f"The periods are {fmt(yb - ya)} years apart, not {fmt(years)}. Check the formula."
    else:
        raise ValueError(f"Unknown calculation {op!r}")
    expected = _result_unit(op, a.get("unit", ""), b.get("unit", ""))
    unit_ok = expected is not None and unit_key(expected) == unit_key(result_unit)
    if not unit_ok and not note:
        note = "unit check needs your confirmation"
    return {"value": value, "unit": result_unit, "kind": "calculated", "verified": True,
            "verify_note": "recomputed from its stored inputs", "quote_span": "", "locator": "",
            "formula": formula, "unit_ok": unit_ok, "years_ok": years_ok, "note": note,
            "inputs": {"a": av, "a_unit": a.get("unit", ""), "b": bv, "b_unit": b.get("unit", ""),
                       "years": float(years) if years else None, "op": op}}


def _year_of(period) -> float | None:
    m = re.findall(r"(19|20)\d\d", str(period or ""))
    years = re.findall(r"(?:19|20)\d\d", str(period or ""))
    if len(years) == 1:
        return float(years[0])
    return None
