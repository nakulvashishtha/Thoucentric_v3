"""The nine-test quality check. An item is approved without a person only if every test passes."""
from __future__ import annotations

from .convert import convert
from .credibility import TIER_LABELS

ORIGIN_WORDS = {"open_web": "web page", "firm_archive": "firm archive", "paid_db": "research database",
                "client_file": "client file", "expert_note": "expert note", "benchmark": "benchmark"}


def run(item: dict, link: dict | None, idea: dict | None, ideas_by_code: dict, corroborated: bool,
        thresholds: dict, private_hits: list[str]) -> list[dict]:
    """item: evidence with credibility_json, figures_json, links. link: the main link (supports_test first).
    Returns the list of {test, pass, threshold, actual}."""
    cl = thresholds.get("checklist") or {}
    cred = item.get("credibility_json") or {}
    origin = item["origin_type"]
    tier = cred.get("tier")
    tests = []

    never = set(cl.get("never_auto_approve_origins") or ["client_file", "expert_note"])
    if cred.get("matches_belief"):
        t1 = (False, "the client's claim")
    else:
        t1 = (origin not in never, ORIGIN_WORDS.get(origin, origin))
    tests.append(_t("Not from the client or an expert", t1, "not a client file, an expert note or the client's claim"))

    allowed = set(cl.get("allowed_tiers") or [1, 2])
    if tier is None:
        t2 = (False, "no rating (a person decides)")
    elif tier in allowed:
        t2 = (True, TIER_LABELS[tier])
    elif tier == 3 and cl.get("tier3_needs_corroboration", True):
        if not cred.get("traced"):
            t2 = (False, "Press, does not name its source")
        elif not corroborated:
            t2 = (False, "Press, no separate source agrees")
        else:
            t2 = (True, "Press, names its source and a separate source agrees")
    else:
        t2 = (False, TIER_LABELS.get(tier, "Unverified"))
    tests.append(_t("Source quality is Official or Trusted", t2,
                    "Official or Trusted (Press only if it names its source and a separate source agrees)"))

    window = cred.get("recency_window") or 36
    tests.append(_t("Source is recent enough", (bool(cred.get("recency_ok")), cred.get("recency_actual") or "no date"),
                    f"dated within {window} months"))
    tests.append(_t("Names its original source or method", (bool(cred.get("traced")),
                                                            "yes" if cred.get("traced") else "no"),
                    "names where the figure comes from"))

    fig = _figure(item, link)
    if fig is None:
        t5 = (False, "no figure to compare")
    elif fig.get("kind") == "calculated" or fig.get("derivation"):
        t5 = (False, "a calculated figure, so you decide")
    elif idea is None:
        t5 = (True, "not linked to an idea")
    else:
        v = fig.get("value") if fig.get("value") is not None else fig.get("low")
        _, note = convert(float(v), fig.get("unit", ""), idea["measure_unit"])
        t5 = (_ok_note(note), note if not _ok_note(note) else note)
        if not _ok_note(note):
            t5 = (False, f"{note}, so you decide")
    tests.append(_t("Uses the idea's measure", t5, "same unit as the idea, or a safe conversion; no calculated figure"))

    if fig is None:
        t6 = (False, "no figure")
    else:
        t6 = (bool(fig.get("verified")), fig.get("verify_note") or ("found" if fig.get("verified") else "not found"))
    tests.append(_t("Quote found in the source", t6, "the figure appears in the quoted text"))

    dup = item.get("duplicate_of")
    tests.append(_t("Not a duplicate", (not dup, f"copy of {dup}" if dup else "original"),
                    "not a copy of a source already counted"))
    tests.append(_t("No private terms", (not private_hits, "none" if not private_hits else ", ".join(private_hits)),
                    "no private client data"))

    load = None
    for lk in item.get("links") or []:
        h = ideas_by_code.get(lk["hypothesis_code"])
        if lk["role"] == "sets_pass_line":
            load = "sets a target"
        elif lk["role"] == "supports_test" and h and h.get("must_have"):
            load = load or "supports a critical idea"
    tests.append(_t("Not needed for a critical idea", (load is None, load or "no"),
                    "does not support a critical idea or set a target"))
    return tests


def _ok_note(note: str) -> bool:
    return note == "same unit" or note.startswith("converted")


def _figure(item: dict, link: dict | None) -> dict | None:
    figs = item.get("figures_json") or []
    if link is not None and link.get("figure_index") is not None and 0 <= link["figure_index"] < len(figs):
        return figs[link["figure_index"]]
    return figs[0] if figs else None


def _t(name: str, res: tuple, threshold: str) -> dict:
    return {"test": name, "pass": bool(res[0]), "threshold": threshold, "actual": res[1]}


def passes(tests: list[dict]) -> bool:
    return bool(tests) and all(t["pass"] for t in tests)


def main_link(item: dict) -> dict | None:
    links = item.get("links") or []
    for lk in links:
        if lk["role"] == "supports_test":
            return lk
    return links[0] if links else None
