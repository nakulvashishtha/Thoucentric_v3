"""Sample packs: data only (case, client files, seeded sources, stored model answers, the consultant script)."""
from __future__ import annotations

import json
from functools import lru_cache

from . import config


def names() -> list[str]:
    return sorted(p.name for p in config.SAMPLES_DIR.iterdir() if (p / "case.json").exists())


@lru_cache(maxsize=None)
def pack(name: str) -> dict:
    d = config.SAMPLES_DIR / name
    if not (d / "case.json").exists():
        return {}
    out = {"dir": d, "case": json.loads((d / "case.json").read_text(encoding="utf-8"))}
    for key, fn in (("seeds", "seed_evidence.json"), ("fixtures", "llm_fixtures.json"), ("script", "consultant_script.json")):
        p = d / fn
        out[key] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else ({} if key != "seeds" else [])
    seed = d / "seed.txt"
    out["seed"] = int(seed.read_text().strip()) if seed.exists() else out["case"].get("spot_seed", 1)
    return out


def listing() -> list[dict]:
    out = []
    for n in names():
        c = pack(n)["case"]
        out.append({"name": n, "title": c["title"], "description": c.get("description", ""), "country": c.get("country", ""),
                    "industry": c.get("industry", "")})
    return out


def reply_file(name: str, idea: str) -> tuple[str, bytes] | None:
    p = pack(name)
    fn = (p.get("case") or {}).get("replies", {}).get(idea) if p else None
    if not fn:
        return None
    path = p["dir"] / "replies" / fn
    return (fn, path.read_bytes()) if path.exists() else None
