"""Demo data mode versus live mode. Demo data is never disguised as live."""
from __future__ import annotations

from . import config, db

DEFAULT_APP = {"mode": "", "fast_demo": True, "larger_text": False, "double_check": True}
NO_KEYS = "Live keys not found, so the app opened in demo data mode."


def app_settings() -> dict:
    return dict(DEFAULT_APP, **(db.kv_get("app_settings", {}) or {}))


def effective() -> tuple[str, str]:
    want = app_settings().get("mode") or config.requested_mode()
    if want == "live" and not config.live_keys_present():
        return "fixtures", NO_KEYS
    return want, ""


def case_mode(case: dict) -> dict:
    m, notice = effective()
    return {"case": case.get("mode") or m, "app": m, "notice": notice}


def new_case_mode() -> str:
    return effective()[0]
