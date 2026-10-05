"""Seeded sources from a sample pack: simulated web pages, firm-archive studies, a paid database and expert notes.
Everything it returns is marked "Sample data (simulated)"."""
from __future__ import annotations

import copy

from .. import samples


class SimulatedSources:
    live = False

    def __init__(self, case: dict):
        self.seeds = samples.pack(case.get("sample") or "").get("seeds", []) if case.get("sample") else []

    def search(self, group: str, need_ref: str, query: str = "", limit: int = 4) -> list[dict]:
        out = [copy.deepcopy(s) for s in self.seeds if s.get("group") == group and s.get("need_ref") == need_ref]
        return out[:limit]

    def benchmark(self, idea_code: str, query: str = "") -> list[dict]:
        return [copy.deepcopy(s) for s in self.seeds if s.get("need_ref") == f"bench:{idea_code}"]

    def expert_notes(self) -> list[dict]:
        return [copy.deepcopy(s) for s in self.seeds if s.get("group") == "expert_note"]
