"""GET /api/selfcheck: every configuration mistake shows as a red item with the exact fix. Never prints a secret."""
from __future__ import annotations

import os
import tempfile

from . import budget, config, modes


def _item(key, label, ok, detail, fix=""):
    return {"key": key, "label": label, "ok": ok, "detail": detail, "fix": fix if ok is False else ""}


def run(live_checks: bool = True) -> dict:
    items = []
    d = config.data_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=d, delete=True) as fh:
            fh.write(b"ok")
        items.append(_item("database", "Database can be written", True, f"Saving cases in {os.environ.get('DATA_DIR') or './data'}"))
    except OSError:
        items.append(_item("database", "Database can be written", False, f"The folder {d} can't be written.",
                           "Set DATA_DIR to a folder the app can write to (for example /app/data), then restart the service."))
    if config.has("ADMIN_PASSCODE"):
        items.append(_item("passcode", "Passcode is set", True, "The app asks for the passcode."))
    else:
        items.append(_item("passcode", "Passcode is set", False, "Anyone with the address can open the app.",
                           "Add ADMIN_PASSCODE in the hosting settings (any phrase you choose), then restart the service."))
    m, notice = modes.effective()
    items.append(_item("mode", "Data mode", None, "Live: real AI and web search." if m == "live" else
                       "Demo data: stored answers for the sample cases only." + (f" {notice}" if notice else "")))
    akey = config.has("ANTHROPIC_API_KEY")
    for name in ("MODEL_FAST", "MODEL_SMART"):
        label = f"AI model in {name} works"
        if not akey:
            items.append(_item(name, label, False, "No AI key, so the model can't be checked.",
                               "Add ANTHROPIC_API_KEY from the Claude Console (platform.claude.com), then run the checks again."))
        elif not config.has(name):
            items.append(_item(name, label, False, f"{name} is empty.",
                               f"Set {name} to a model ID from the Claude Console model list, then restart the service."))
        elif not live_checks:
            items.append(_item(name, label, None, "Not checked yet."))
        else:
            from .llm.live import ping
            ok, detail = ping(config.env(name))
            items.append(_item(name, label, ok, detail, (f"Check the model ID in {name} against the Claude Console model "
                                                         "list, or check that ANTHROPIC_API_KEY is valid and has credit, "
                                                         "then restart the service.")))
    if not config.has("TAVILY_API_KEY"):
        items.append(_item("search", "Search key works", False, "No search key.",
                           "Add TAVILY_API_KEY from tavily.com (the free plan is enough), then run the checks again."))
    elif not live_checks:
        items.append(_item("search", "Search key works", None, "Not checked yet."))
    else:
        from .search.live import ping as sping
        ok, detail = sping()
        items.append(_item("search", "Search key works", ok, detail,
                           "Check TAVILY_API_KEY at tavily.com (copy it again without spaces), then restart the service."))
    s = budget.spend(None)
    items.append(_item("spend", "Spending today", None if not s["reached"] else False,
                       f"${s['today_usd']:.2f} of the ${s['daily_cap_usd']:g} daily limit.",
                       "Raise DAILY_SPEND_CAP in the hosting settings, or wait until tomorrow (UTC)."))
    red = sum(1 for i in items if i["ok"] is False)
    return {"items": items, "all_green": red == 0, "red": red}
