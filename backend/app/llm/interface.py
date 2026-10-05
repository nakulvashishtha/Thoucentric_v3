"""The language model reads, writes and sorts. It never decides a verdict, confidence, approval, tier or recommendation.

Two implementations: FixtureLLM (stored answers from the sample pack) and LiveLLM (Anthropic, see live.py)."""
from __future__ import annotations

import copy

from ..core import JobError
from .. import samples

# job name -> model class (smart for framing, planning, follow-ups and the summary; fast for everything else)
MODEL_CLASS = {"FRAME": "smart", "PLAN_HYPOTHESES": "smart", "DRAFT_FOLLOWUP": "smart", "SUMMARISE": "smart",
               "READ_FILE": "fast", "READ_SOURCE": "fast", "ROUTE_NEEDS": "fast", "GENERATE_QUERIES": "fast",
               "LINK_EVIDENCE": "fast", "UNKNOWNS": "fast"}


class FixtureLLM:
    """Stored answers matched by a stable key: job name plus the idea code, need id, seed id or file name."""
    live = False

    def __init__(self, case: dict):
        self.case = case
        self.fx = samples.pack(case.get("sample") or "").get("fixtures", {}) if case.get("sample") else {}

    def run(self, job: str, key: str, payload: dict) -> dict:
        k = f"{job}:{key}" if key else job
        if k in self.fx:
            return copy.deepcopy(self.fx[k])
        if not key and job in self.fx:
            return copy.deepcopy(self.fx[job])
        raise JobError(f"Stored answer missing: {k}")

    def has(self, job: str, key: str = "") -> bool:
        return (f"{job}:{key}" if key else job) in self.fx


def get_llm(case: dict):
    if case.get("mode") == "live":
        from .live import LiveLLM
        return LiveLLM(case)
    return FixtureLLM(case)
