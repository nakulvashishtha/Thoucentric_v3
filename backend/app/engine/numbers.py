"""Number formatting shared by every sentence the engine writes.

Ported from reference/offline_api_replica.js (fmt, withUnit, figText, join) so the wording matches the original
backend character for character."""
from __future__ import annotations

import math


def _js_num(x: float) -> str:
    """String(Number(...)) in JavaScript: integers lose the trailing .0."""
    if x == int(x):
        return str(int(x))
    s = repr(float(x))
    return s


def _grouped(x: float, decimals: int) -> str:
    return f"{x:,.{decimals}f}"


def fmt(x) -> str:
    if x is None:
        return "?"
    x = float(x)
    if abs(x - round(x)) < 1e-9:
        return f"{int(round(x)):,}"
    if abs(x) >= 100:
        return _grouped(x, 1)
    if abs(x) < 1:
        return _js_num(float(f"{x:.4g}"))
    if abs(x) < 10:
        return _js_num(float(f"{x:.3g}"))
    return f"{_js_round(x, 1):.1f}"


def _js_round(x: float, d: int) -> float:
    """toFixed rounds the exact binary value half away from zero; Python's format does the same except on exact
    binary ties, where it rounds to even. Nudge exact ties so both agree."""
    m = 10 ** d
    y = x * m
    if abs(y - math.floor(y) - 0.5) < 1e-12:
        return (math.floor(y) + (1 if x > 0 else 0)) / m
    return x


def with_unit(v, u) -> str:
    u = (u or "").strip()
    return fmt(v) + u if (u.startswith("%") or not u) else f"{fmt(v)} {u}"


def fig_text(low, high, u) -> str:
    if low == high:
        return with_unit(low, u) if u else fmt(low)
    return f"{fmt(low)} to {with_unit(high, u) if u else fmt(high)}"


def join(parts: list[str]) -> str:
    if len(parts) == 1:
        return parts[0]
    if not parts:
        return ""
    return ", ".join(parts[:-1]) + " and " + parts[-1]
