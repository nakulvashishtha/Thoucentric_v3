"""Live model calls through the Anthropic SDK: structured JSON output, one retry, cache, spending caps and a ledger.
The model never decides a verdict, confidence, approval, tier or recommendation; it only returns the schema."""
from __future__ import annotations

import hashlib
import json

from .. import budget, config, db
from ..core import JobError, now_iso
from .interface import MODEL_CLASS
from .schemas import MAX_TOKENS, SCHEMAS, normalise

TIMEOUT_S = 40.0


def _prompt(job: str) -> tuple[str, str]:
    rules = (config.PROMPTS_DIR / "_rules.md").read_text(encoding="utf-8")
    task = (config.PROMPTS_DIR / f"{job}.md").read_text(encoding="utf-8")
    version = hashlib.sha256((rules + task).encode()).hexdigest()[:12]
    return rules + "\n\nYour task:\n" + task, version


def _client():
    import anthropic
    return anthropic.Anthropic(api_key=config.env("ANTHROPIC_API_KEY"), timeout=TIMEOUT_S, max_retries=1)


def model_for(job: str) -> str:
    return config.env("MODEL_SMART") if MODEL_CLASS.get(job) == "smart" else config.env("MODEL_FAST")


def ping(model: str) -> tuple[bool, str]:
    """Self-check: is the key valid and the model name accepted? Uses the Models API, so it costs nothing."""
    import anthropic
    try:
        m = _client().models.retrieve(model)
        return True, f"{getattr(m, 'display_name', model)} answers."
    except anthropic.AuthenticationError:
        return False, "The AI key was refused."
    except anthropic.NotFoundError:
        return False, f"The model name {model} isn't recognised."
    except anthropic.PermissionDeniedError:
        return False, "This key can't use that model."
    except anthropic.APIConnectionError:
        return False, "The AI service can't be reached from the server."
    except anthropic.APIStatusError as e:
        return False, f"The AI service answered with an error ({e.status_code})."


class LiveLLM:
    live = True

    def __init__(self, case: dict):
        self.case = case

    def has(self, job: str, key: str = "") -> bool:
        return True

    def run(self, job: str, key: str, payload: dict) -> dict:
        import anthropic
        system, version = _prompt(job)
        model = model_for(job)
        canon = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        ck = hashlib.sha256(f"{job}|{model}|{version}|{canon}".encode()).hexdigest()
        bypass = bool(((db.case_get(self.case["id"]) or self.case).get("settings_json") or {}).get("bypass_cache"))
        if not bypass:
            hit = db.q("SELECT output_json FROM llm_cache WHERE k=?", (ck,))
            if hit:
                return json.loads(hit[0]["output_json"])
        user = f"<data>\n{canon}\n</data>"
        error_note = ""
        for attempt in range(2):                      # one retry with the validation error appended, never more
            budget.check(self.case["id"], "llm")
            params = {"model": model, "max_tokens": MAX_TOKENS.get(job, 4000), "system": system,
                      "messages": [{"role": "user", "content": user + error_note}],
                      "output_config": {"format": {"type": "json_schema", "schema": SCHEMAS[job]}}}
            if "haiku" not in model.lower():
                params["output_config"]["effort"] = "medium" if MODEL_CLASS.get(job) == "smart" else "low"
            try:
                resp = _client().messages.create(**params)
            except anthropic.AuthenticationError:
                raise JobError("The AI key was refused. Open Settings and run the checks to see the fix.")
            except (anthropic.NotFoundError, anthropic.BadRequestError) as e:
                raise JobError("The AI service refused the request. Open Settings and run the checks; the model "
                               "names may be wrong.") from e
            except anthropic.RateLimitError:
                raise JobError("The AI service is busy right now. Wait a minute, then press Try again.")
            except (anthropic.APIConnectionError, anthropic.APITimeoutError):
                raise JobError("The AI service didn't answer in time. Press Try again.")
            except anthropic.APIStatusError:
                raise JobError("The AI service had a problem. Press Try again in a minute.")
            u = resp.usage
            budget.record(self.case["id"], "llm", job, model,
                          int(u.input_tokens or 0) + int(getattr(u, "cache_creation_input_tokens", 0) or 0),
                          int(u.output_tokens or 0))
            if resp.stop_reason == "refusal":
                raise JobError("The AI service declined this request. Rephrase the ask, or continue with your own input.")
            text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
            try:
                out = json.loads(text)
                if not isinstance(out, dict):
                    raise ValueError("not an object")
            except ValueError as e:
                error_note = f"\n\nYour previous answer was not valid JSON for the schema ({e}). Answer again."
                continue
            out = normalise(job, out)
            db.ex("INSERT OR REPLACE INTO llm_cache (k, job, model, prompt_version, output_json, created_at) VALUES "
                  "(?,?,?,?,?,?)", (ck, job, model, version, json.dumps(out), now_iso()))
            return out
        raise JobError("The AI answer couldn't be read twice in a row. Press Try again.")
