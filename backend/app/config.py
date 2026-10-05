"""Configuration from environment variables and the YAML files in backend/config. Never logs a secret."""
from __future__ import annotations

import os
import pathlib
from functools import lru_cache

import yaml

BACKEND = pathlib.Path(__file__).resolve().parent.parent
ROOT = BACKEND.parent
CONFIG_DIR = BACKEND / "config"
SAMPLES_DIR = BACKEND / "samples"
PROMPTS_DIR = BACKEND / "prompts"
DIST_DIR = ROOT / "frontend" / "dist"

KEY_NAMES = ("ANTHROPIC_API_KEY", "TAVILY_API_KEY", "ADMIN_PASSCODE", "MODEL_FAST", "MODEL_SMART")


def _load_dotenv() -> None:
    """Read a local .env if present (values already in the environment win). No extra library needed."""
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.split(" #", 1)[0].strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v


_load_dotenv()


def env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def env_float(name: str, default: float) -> float:
    try:
        return float(env(name) or default)
    except ValueError:
        return default


def has(name: str) -> bool:
    return bool(env(name))


def data_dir() -> pathlib.Path:
    d = pathlib.Path(env("DATA_DIR", str(ROOT / "data")))
    if not d.is_absolute():
        d = ROOT / d
    return d


def requested_mode() -> str:
    m = env("MODE", "live").lower()
    return m if m in ("live", "fixtures") else "live"


def live_keys_present() -> bool:
    return has("ANTHROPIC_API_KEY") and has("TAVILY_API_KEY") and has("MODEL_FAST") and has("MODEL_SMART")


def daily_cap() -> float:
    return env_float("DAILY_SPEND_CAP", 5.0)


def max_calls() -> int:
    return int(env_float("MAX_LLM_CALLS_PER_CASE", 150))


MAX_SEARCH_CREDITS = 40.0


@lru_cache(maxsize=1)
def rules_text() -> str:
    return (CONFIG_DIR / "rules.yaml").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def registry_text() -> str:
    return (CONFIG_DIR / "source_registry.yaml").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def rules() -> dict:
    r = yaml.safe_load(rules_text())
    r["adding_up_rule"] = " ".join(str(r.get("adding_up_rule", "")).split())
    return r


@lru_cache(maxsize=1)
def registry() -> dict:
    return yaml.safe_load(registry_text()) or {}


@lru_cache(maxsize=1)
def prices() -> dict:
    return yaml.safe_load((CONFIG_DIR / "prices.yaml").read_text(encoding="utf-8")) or {}


def ruleset_thresholds() -> dict:
    """The part of the rules that is locked into each case at step 3."""
    r = rules()
    keys = ("tolerance_pct_default", "recency_months", "checklist", "minimum_sources", "spot_check", "trips")
    return {k: r[k] for k in keys if k in r}
