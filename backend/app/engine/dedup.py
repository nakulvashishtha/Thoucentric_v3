"""De-duplication. Copies are traced to one original, which counts once.

Rules, in order: (1) same normalised address or identical text (found before reading, so copies are never read);
(2) the item names the same original source as another item and a figure matches within rounding;
(3) token-set similarity of the texts is at least the configured threshold (default 0.8)."""
from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit

RULE_EXACT = "same address or identical text"
RULE_NAMED = "names the same original source with a matching figure"
RULE_SIMILAR = "near-identical text"


def norm_url(url: str) -> str:
    if not url:
        return ""
    p = urlsplit(url.strip().lower())
    host = p.netloc[4:] if p.netloc.startswith("www.") else p.netloc
    q = [(k, v) for k, v in parse_qsl(p.query) if not k.startswith("utm_") and k not in ("ref", "fbclid", "gclid")]
    path = p.path.rstrip("/")
    return host + path + ("?" + urlencode(q) if q else "")


def text_hash(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha256(t.encode("utf-8")).hexdigest() if t else ""


def norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", (text or "").lower()))


def similarity(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def exact_copies(items: list[dict]) -> dict[str, str]:
    """items in collection order: [{id, url, text}]. Returns {copy_id: earlier_id} for exact copies."""
    seen_url, seen_hash, out = {}, {}, {}
    for it in items:
        u, h = norm_url(it.get("url", "")), text_hash(it.get("text", ""))
        first = (seen_url.get(u) if u else None) or (seen_hash.get(h) if h else None)
        if first:
            out[it["id"]] = first
        else:
            if u:
                seen_url[u] = it["id"]
            if h:
                seen_hash[h] = it["id"]
    return out


def _fig_values(item: dict) -> list[float]:
    vals = []
    for f in item.get("figures") or []:
        if f.get("kind") == "calculated" or not f.get("verified", True):
            continue
        for k in ("value", "low", "high"):
            if f.get(k) is not None:
                vals.append(float(f[k]))
    return vals


def _figures_match(a: dict, b: dict) -> bool:
    for x in _fig_values(a):
        for y in _fig_values(b):
            if abs(x - y) <= max(0.05, 0.005 * max(abs(x), abs(y))):
                return True
    return False


def _identity(item: dict) -> set[str]:
    """Names this item is known by: its title and publisher, and the original it names when that is itself."""
    names = {norm_name(item.get("title", "")), norm_name(item.get("publisher", ""))}
    return {n for n in names if n}


def group(items: list[dict], threshold: float = 0.8) -> tuple[dict[str, str], dict[str, str]]:
    """items (already read, not exact copies, in collection order): [{id, seq, title, publisher, tier, text,
    figures, describe}]. Returns ({copy_id: original_id}, {copy_id: rule})."""
    parent = {it["id"]: it["id"] for it in items}
    rule_of: dict[str, str] = {}
    byid = {it["id"]: it for it in items}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b, rule, copy):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
        rule_of.setdefault(copy, rule)

    for i, a in enumerate(items):
        named = norm_name((a.get("describe") or {}).get("original_source_name", ""))
        if not named or not (a.get("describe") or {}).get("original_source_named", True):
            continue
        for b in items:
            if b is a:
                continue
            b_named = norm_name((b.get("describe") or {}).get("original_source_name", ""))
            if (named in _identity(b) or (b_named == named and b["seq"] < a["seq"])) and _figures_match(a, b):
                union(b["id"], a["id"], RULE_NAMED, a["id"])
                break
    for i, a in enumerate(items):
        for b in items[:i]:
            if find(a["id"]) == find(b["id"]):
                continue
            if similarity(a.get("text", ""), b.get("text", "")) >= threshold:
                union(b["id"], a["id"], RULE_SIMILAR, a["id"])
                break
    groups: dict[str, list[dict]] = {}
    for it in items:
        groups.setdefault(find(it["id"]), []).append(it)
    original_of, rules = {}, {}
    for members in groups.values():
        if len(members) < 2:
            continue
        orig = min(members, key=lambda m: (0 if _is_self_original(m, members) else 1, m.get("tier") or 9, m["seq"]))
        for m in members:
            if m["id"] != orig["id"]:
                original_of[m["id"]] = orig["id"]
                rules[m["id"]] = rule_of.get(m["id"]) or rule_of.get(orig["id"]) or RULE_SIMILAR
    return original_of, rules


def _is_self_original(m: dict, members: list[dict]) -> bool:
    """True when another member names this item (by its title or publisher) as the original source."""
    ident = _identity(m)
    for o in members:
        if o is m:
            continue
        named = norm_name((o.get("describe") or {}).get("original_source_name", ""))
        if named and named in ident:
            return True
    return False
