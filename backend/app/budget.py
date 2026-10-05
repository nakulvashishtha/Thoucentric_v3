"""Spending: the ledger, the per-case call cap, the daily dollar cap and the per-case search cap."""
from __future__ import annotations

from datetime import datetime, timezone

from . import config, db
from .core import JobError, now_iso


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def record(cid: int, kind: str, job: str, model: str = "", input_tokens: int = 0, output_tokens: int = 0,
           search_credits: float = 0.0) -> float:
    cost = 0.0
    if kind == "llm":
        p = price(model)
        cost = input_tokens / 1e6 * p["input"] + output_tokens / 1e6 * p["output"]
    else:
        cost = search_credits * float((config.prices().get("search") or {}).get("tavily_basic", 0.008))
    db.insert("cost_ledger", cid, {"ts": now_iso(), "day": _today(), "kind": kind, "job": job, "model": model,
                                   "input_tokens": input_tokens, "output_tokens": output_tokens,
                                   "search_credits": search_credits, "cost_usd": round(cost, 6)})
    return cost


def price(model: str) -> dict:
    table = (config.prices().get("models") or {})
    for k, v in table.items():
        if k != "default" and (model or "").startswith(k):
            return v
    return table.get("default", {"input": 3.0, "output": 15.0})


def _rows_today() -> list[dict]:
    import json
    return [json.loads(r["data"]) for r in db.q("SELECT data FROM cost_ledger WHERE data LIKE ?", (f'%"day": "{_today()}"%',))]


def spend(cid: int | None) -> dict:
    rows = db.rows("cost_ledger", cid) if cid else []
    today = _rows_today()
    calls = sum(1 for r in rows if r["kind"] == "llm")
    credits = sum(float(r.get("search_credits") or 0) for r in rows)
    case_usd = round(sum(float(r["cost_usd"]) for r in rows), 4)
    today_usd = round(sum(float(r["cost_usd"]) for r in today), 4)
    cap, mc, ms = config.daily_cap(), config.max_calls(), config.MAX_SEARCH_CREDITS
    reached, warn = [], []
    for key, used, lim in (("calls", calls, mc), ("daily", today_usd, cap), ("search", credits, ms)):
        if lim and used >= lim:
            reached.append(key)
        elif lim and used >= 0.8 * lim:
            warn.append(key)
    return {"case_usd": case_usd, "today_usd": today_usd, "daily_cap_usd": float(cap), "calls": calls, "max_calls": mc,
            "search_credits": float(credits), "max_search_credits": float(ms), "reached": reached, "warn": warn}


LIMIT_TEXT = {"calls": "The call limit for this case is reached, so no more AI calls will be made. Open Settings to see "
                       "the spend.",
              "daily": "The daily spending limit is reached, so no more external calls will be made today. Open "
                       "Settings to see the spend.",
              "search": "The search limit for this case is reached, so no more searches will be made. Open Settings "
                        "to see the spend."}


def check(cid: int, kind: str) -> None:
    """Stop spending before a call when a cap is reached."""
    s = spend(cid)
    keys = ("calls", "daily") if kind == "llm" else ("search", "daily")
    for k in keys:
        if k in s["reached"]:
            raise JobError(LIMIT_TEXT[k])
