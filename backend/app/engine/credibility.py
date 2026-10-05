"""Source credibility: tier from the registry (never the language model), recency and traced."""
from __future__ import annotations

import fnmatch
import re
from datetime import datetime, timezone

TIER_LABELS = {1: "Official", 2: "Trusted", 3: "Press", 4: "Unverified"}
NO_TIER_REASON = "Client and expert material has no tier; a person always decides"
_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov",
                                       "dec"], 1)}


def domain_of(url: str) -> str:
    m = re.match(r"^[a-z]+://([^/?#:]+)", (url or "").strip().lower())
    d = m.group(1) if m else ""
    return d[4:] if d.startswith("www.") else d


def _match(domain: str, pattern: str) -> bool:
    pattern = pattern.lower()
    if fnmatch.fnmatch(domain, pattern):
        return True
    if "*" not in pattern and (domain == pattern or domain.endswith("." + pattern)):
        return True
    return False


def country_packs(registry: dict, country: str) -> list[tuple[str, dict]]:
    c = (country or "").strip().lower()
    out = []
    for code, pack in (registry.get("countries") or {}).items():
        names = [n.lower() for n in pack.get("names") or []] + [code.lower()]
        if c and c in names:
            out.append((code, pack))
    return out


def tier_for(domain: str, origin_type: str, registry: dict, country: str = "", industry: str = "",
             plan: list[dict] | None = None) -> tuple[int | None, str]:
    """Return (tier, reason). Client and expert material has no tier."""
    if origin_type in ("client_file", "expert_note"):
        return None, NO_TIER_REASON
    if origin_type == "firm_archive":
        return 2, "Source is the firm archive (Tier 2 by type)"
    if origin_type == "paid_db":
        return 2, "Source is the paid research database (Tier 2 by type)"
    domain = (domain or "").lower()
    for item in plan or []:
        d = (item.get("domain") or "").lower()
        if item.get("stated_by_consultant") and d and item.get("tier") and (domain == d or domain.endswith("." + d)):
            reason = item.get("tier_reason") or ""
            prefix = f"Added to the source plan by the consultant as Tier {item['tier']}: "
            return int(item["tier"]), reason if reason.startswith(prefix) else prefix + reason
    if not domain:
        return 4, "The source has no web address (unknown sources are Tier 4)"
    packs = [(f"the country pack {code}", p) for code, p in country_packs(registry, country)]
    ind = (registry.get("industries") or {}).get((industry or "").strip().lower())
    if ind:
        packs.append((f"the industry pack {industry}", ind))
    packs.append(("the global list", registry.get("global") or {}))
    for t in (1, 2, 3, 4):
        for where, pack in packs:
            for pat in pack.get(f"tier{t}") or []:
                if _match(domain, pat):
                    return t, f"{domain} matches '{pat}' in {where}"
    return 4, f"{domain} is not in the source registry (unknown domains are Tier 4)"


def parse_date(text: str, now: datetime | None = None) -> datetime | None:
    """'2026-03-04', '2026-03', 'Dec 2024', 'March 2026', '2025' -> first day of that month. Future or bad -> None."""
    now = now or datetime.now(timezone.utc)
    s = str(text or "").strip().lower()
    if not s:
        return None
    y = mo = None
    m = re.match(r"^((?:19|20)\d\d)-(\d{1,2})(?:-(\d{1,2}))?", s)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
    else:
        m = re.search(r"([a-z]{3})[a-z]*\.?\s+((?:19|20)\d\d)", s)
        if m and m.group(1) in _MONTHS:
            y, mo = int(m.group(2)), _MONTHS[m.group(1)]
        else:
            m = re.fullmatch(r"(?:fy\s*)?((?:19|20)\d\d)", s)
            if m:
                y, mo = int(m.group(1)), 1
    if y is None or not (1 <= mo <= 12):
        return None
    d = datetime(y, mo, 1, tzinfo=timezone.utc)
    if d > now:
        return None
    return d


def recency(data_as_of: str, published_date: str, window_months: int, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    d = parse_date(data_as_of, now) or parse_date(published_date, now)
    if d is None:
        return {"recency_ok": False, "recency_actual": "no date", "recency_window": window_months}
    months = (now.year - d.year) * 12 + now.month - d.month
    return {"recency_ok": months <= window_months, "recency_actual": f"{d.year}-{d.month:02d} ({months} months old)",
            "recency_window": window_months}


def traced(describe: dict | None, tier: int | None) -> bool:
    d = describe or {}
    return bool(d.get("method_cited") or d.get("original_source_named") or tier == 1)
