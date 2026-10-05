"""Shared helpers: time, errors, the activity record and background jobs."""
from __future__ import annotations

import json
import threading
import traceback
from datetime import datetime, timezone

from . import db


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ApiError(Exception):
    """A refusal shown to the consultant: {reason, required} with an HTTP status."""

    def __init__(self, status: int, reason: str, required: list | None = None):
        super().__init__(reason)
        self.status, self.reason, self.required = status, reason, list(required or [])


def gate(reason: str, required: list | None = None) -> ApiError:
    return ApiError(409, reason, required)


class JobError(Exception):
    """A job failed with a plain sentence the consultant can act on."""


# ------------------------------------------------------------------ activity (append-only)
def log(cid: int, actor: str, event_type: str, step: int, message: str, payload: dict | None = None) -> None:
    db.ex("INSERT INTO activity (case_id, ts, actor, event_type, step, message, payload_json) VALUES (?,?,?,?,?,?,?)",
          (cid, now_iso(), actor, event_type, step, message, json.dumps(payload) if payload else None))


def activity(cid: int, since_id: int = 0) -> list[dict]:
    out = []
    for r in db.q("SELECT * FROM activity WHERE case_id=? AND id>? ORDER BY id", (cid, since_id)):
        out.append({"id": r["id"], "ts": r["ts"], "actor": r["actor"], "event_type": r["event_type"], "step": r["step"],
                    "message": r["message"], "case_id": r["case_id"],
                    "payload_json": json.loads(r["payload_json"]) if r["payload_json"] else None})
    return out


# ------------------------------------------------------------------ background jobs (threads, progress in the job table)
_threads: dict[int, threading.Thread] = {}


def job_get(jid: int) -> dict | None:
    return db.get("job", jid)


def latest_jobs(cid: int) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for j in db.rows("job", cid):
        out[j["kind"]] = j
    return out


def running(cid: int, kind: str | None = None) -> list[dict]:
    return [j for j in latest_jobs(cid).values() if j["status"] in ("running", "queued") and (kind is None or j["kind"] == kind)]


class Job:
    def __init__(self, row: dict):
        self.row = row

    @property
    def cid(self) -> int:
        return self.row["case_id"]

    def progress(self, **kw) -> None:
        with db.lock():
            cur = db.get("job", self.row["id"]) or self.row
            cur["progress"] = dict(cur.get("progress") or {}, **kw)
            self.row = cur
            db.put("job", cur)

    def set_progress(self, progress: dict) -> None:
        with db.lock():
            cur = db.get("job", self.row["id"]) or self.row
            cur["progress"] = progress
            self.row = cur
            db.put("job", cur)


def start_job(cid: int, kind: str, fn, label: str = "", progress: dict | None = None, sync: bool = False) -> dict:
    """Start a background job. Idempotent: a job of the same kind that is still running is returned instead."""
    with db.lock():
        for j in running(cid, kind):
            return j
        row = db.insert("job", cid, {"kind": kind, "status": "running", "error": "",
                                     "progress": progress if progress is not None else ({"label": label} if label else {}),
                                     "started_at": now_iso(), "finished_at": None})
    job = Job(row)

    def run():
        try:
            fn(job)
            _finish(job, "done", "")
        except JobError as e:
            _finish(job, "failed", str(e))
        except Exception as e:                                  # never a stack trace on screen
            traceback.print_exc()
            msg = getattr(e, "plain", None) or "Something went wrong in this step. Try again."
            _finish(job, "failed", msg)

    if sync:
        run()
    else:
        t = threading.Thread(target=run, daemon=True, name=f"job-{kind}-{row['id']}")
        _threads[row["id"]] = t
        t.start()
    return db.get("job", row["id"])


def _finish(job: Job, status: str, error: str) -> None:
    with db.lock():
        cur = db.get("job", job.row["id"])
        if cur is None:                                         # the case was deleted or reset meanwhile
            return
        cur.update(status=status, error=error, finished_at=now_iso())
        db.put("job", cur)
        case = db.case_get(cur["case_id"])
        if case and case.get("mode") == "live" and cur["kind"] != "advance":
            s = case.setdefault("settings_json", {})
            s["live_failures"] = (int(s.get("live_failures") or 0) + 1) if status == "failed" else 0
            db.case_put(case)


def wait_all(timeout: float = 30.0) -> None:
    """Tests only: wait for every background job thread."""
    for t in list(_threads.values()):
        t.join(timeout)
