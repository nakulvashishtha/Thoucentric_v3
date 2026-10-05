"""Search providers: seeded sample sources (fixtures), live Tavily web search and the firm archive."""
from __future__ import annotations


def get_search(case: dict):
    if case.get("mode") == "live":
        from .live import LiveSources
        return LiveSources(case)
    from .simulated import SimulatedSources
    return SimulatedSources(case)
