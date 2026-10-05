"""Privacy: the deny-list, masking of client names, and the hard filter that runs before every outbound call.

Deny-list: the client name and aliases, private numbers entered at step 1, and client-file figures that carry a unit or
currency symbol. Four-digit years (1900 to 2100) and plain integers below 100 never count unless marked private."""
from __future__ import annotations

import re

from .convert import SCALES

_CURRENCY = r"(?:rs\.?|inr|usd|us\$|\$|€|eur|£|gbp|kes|ksh|₹)"
_NUM_RE = re.compile(r"(" + _CURRENCY + r"\s*)?(\d[\d,]*(?:\.\d+)?)\s*(%|percent|thousand|lakh|lakhs|crore|crores|"
                     r"million|billion|bn|mn)?", re.I)


def _names(case: dict) -> list[str]:
    names = [case.get("client_name") or ""] + list(case.get("client_aliases") or [])
    return sorted({n.strip() for n in names if n and len(n.strip()) >= 2}, key=len, reverse=True)


def mask_names(text: str, case: dict, replacement: str = "the client") -> tuple[str, list[str]]:
    """Replace the client name and aliases with 'the client'. Returns (text, removed terms)."""
    removed = []
    out = text or ""
    for n in _names(case):
        pat = re.compile(r"(?<![\w])" + re.escape(n) + r"(?![\w])", re.I)
        if pat.search(out):
            removed.append(n)
            out = pat.sub(replacement, out)
    return out, removed


def _numbers_in(text: str) -> list[dict]:
    out = []
    for m in _NUM_RE.finditer(text or ""):
        raw = m.group(2)
        try:
            v = float(raw.replace(",", ""))
        except ValueError:
            continue
        unit = (m.group(3) or "").lower()
        scale = SCALES.get(unit, 1.0) if unit not in ("%", "percent") else 1.0
        out.append({"value": v * scale, "plain": v, "percent": unit in ("%", "percent"),
                    "currency": bool(m.group(1)), "text": m.group(0).strip(), "has_unit": bool(unit or m.group(1))})
    return out


def deny_numbers(case: dict, files: list[dict]) -> list[dict]:
    """Numbers that must never leave the firm."""
    out = []
    for p in case.get("private_numbers") or []:
        for n in _numbers_in(p):
            if _is_year(n["plain"]) and not n["has_unit"]:
                continue
            out.append({"value": n["value"], "percent": n["percent"], "label": p, "marked": True})
    for f in files or []:
        if f.get("kind") == "archive":
            continue
        for fig in f.get("figures") or []:
            unit = (fig.get("unit") or "").strip()
            if not unit:
                continue
            for key in ("value", "low", "high"):
                v = fig.get(key)
                if v is None:
                    continue
                v = float(v)
                if _is_year(v) and not unit:
                    continue
                out.append({"value": v, "percent": unit.startswith("%") or "percent" in unit.lower(),
                            "label": f"{fig.get('quote_span') or v} ({f.get('filename')})", "marked": False})
    return out


def _is_year(v: float) -> bool:
    return v == int(v) and 1900 <= v <= 2100


def find_private(text: str, case: dict, files: list[dict]) -> list[str]:
    """Return the private terms found in text (names are matched as whole words, numbers by value)."""
    hits = []
    for n in _names(case):
        if re.search(r"(?<![\w])" + re.escape(n) + r"(?![\w])", text or "", re.I):
            hits.append(n)
    deny = deny_numbers(case, files)
    for num in _numbers_in(text):
        if _is_year(num["plain"]) and not num["has_unit"]:
            continue
        for d in deny:
            if abs(num["value"] - d["value"]) > 1e-9 * max(1.0, abs(d["value"])):
                continue
            small_plain = d["value"] == int(d["value"]) and abs(d["value"]) < 100 and not d["marked"]
            if small_plain and not num["has_unit"]:
                continue                       # a bare small integer is too common to count as private
            if d["percent"] != num["percent"] and (d["percent"] or num["percent"]):
                continue
            hits.append(num["text"])
            break
    return list(dict.fromkeys(hits))


def check_outbound(text: str, case: dict, files: list[dict]) -> dict:
    """The hard filter. Names are masked; any private number blocks the call."""
    sanitised, removed = mask_names(text, case)
    blocked = find_private(sanitised, case, files)
    return {"original": text, "sanitised": sanitised, "removed": removed, "blocked": blocked}


def mask_for_model(text: str, case: dict) -> str:
    """Before text goes to the language model: client name and aliases become 'the client'."""
    return mask_names(text, case)[0]
