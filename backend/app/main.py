"""Research Workbench API and static front end. One service, same origin: /api for the API, / for the app."""
from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response

from . import budget, bundle, config, db, evidence, export, modes, samples, selfcheck
from . import steps_decide as S3
from . import steps_frame as S1
from . import steps_gather as S2
from .core import ApiError, activity, gate, job_get, log, running
from .state import done_map

COOKIE = "rw_session"


def _startup() -> None:
    db.connect()
    # jobs cannot survive a restart: mark any that were running as interrupted, so Try again appears
    for c in db.case_list():
        for j in db.rows("job", c["id"]):
            if j["status"] == "running":
                j.update(status="failed", error="This step was interrupted when the app restarted. Try again.")
                db.put("job", j)
    r = selfcheck.run(live_checks=False)
    print("Self-check at startup:", ", ".join(f"{i['label']}: {'ok' if i['ok'] else 'needs a fix' if i['ok'] is False else 'info'}"
                                              for i in r["items"]))


@asynccontextmanager
async def lifespan(_app):
    _startup()
    yield


app = FastAPI(title="Research Workbench", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


# ------------------------------------------------------------------ errors
@app.exception_handler(ApiError)
async def _api_error(_: Request, e: ApiError):
    return JSONResponse({"reason": e.reason, "required": e.required}, status_code=e.status)


@app.exception_handler(RequestValidationError)
async def _bad(_: Request, e: RequestValidationError):
    return JSONResponse({"reason": "Something in the request wasn't right. Refresh the page and try again.", "required": []},
                        status_code=400)


@app.exception_handler(Exception)
async def _crash(_: Request, e: Exception):
    import traceback
    traceback.print_exc()
    return JSONResponse({"reason": "Something went wrong. Try again.", "required": []}, status_code=500)


# ------------------------------------------------------------------ passcode
def _token() -> str:
    pc = config.env("ADMIN_PASSCODE")
    return hmac.new(pc.encode(), b"research-workbench-session", hashlib.sha256).hexdigest() if pc else ""


def _signed_in(request: Request) -> bool:
    t = _token()
    return not t or hmac.compare_digest(request.cookies.get(COOKIE, ""), t)


_attempts: dict[str, list[float]] = defaultdict(list)


@app.middleware("http")
async def _guard(request: Request, call_next):
    p = request.url.path
    if p.startswith("/api/") and p not in ("/api/session", "/api/login") and not _signed_in(request):
        return JSONResponse({"reason": "Enter the passcode to continue.", "required": []}, status_code=401)
    resp = await call_next(request)
    if not p.startswith("/api/"):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    return resp


async def body(request: Request) -> dict | list:
    try:
        raw = await request.body()
        return json.loads(raw) if raw else {}
    except (ValueError, UnicodeDecodeError):
        raise ApiError(400, "Something in the request wasn't right. Refresh the page and try again.")


def case_of(cid: int) -> dict:
    c = db.case_get(cid)
    if not c:
        raise ApiError(404, f"Case {cid} not found")
    return c


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/session")
def session(request: Request):
    return {"required": bool(_token()), "signed_in": _signed_in(request)}


@app.post("/api/login")
async def login(request: Request):
    ip = request.client.host if request.client else "?"
    now = time.time()
    _attempts[ip] = [t for t in _attempts[ip] if now - t < 60]
    if len(_attempts[ip]) >= 10:
        raise ApiError(429, "Too many tries. Wait a minute and try again.")
    _attempts[ip].append(now)
    b = await body(request)
    pc = config.env("ADMIN_PASSCODE")
    if pc and not hmac.compare_digest(str((b or {}).get("passcode") or ""), pc):
        raise ApiError(401, "That passcode isn't right. Check it and try again.")
    resp = JSONResponse({"ok": True})
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    resp.set_cookie(COOKIE, _token(), httponly=True, samesite="lax", secure=secure, max_age=60 * 60 * 24 * 14)
    return resp


# ------------------------------------------------------------------ app level
def settings_view() -> dict:
    m, notice = modes.effective()
    return {"mode": m, "notice": notice, "keys": {k: config.has(k) for k in config.KEY_NAMES}, "app": modes.app_settings(),
            "spend": budget.spend(None), "rules_yaml": config.rules_text(), "registry_yaml": config.registry_text()}


@app.get("/api/settings")
def get_settings():
    return settings_view()


@app.put("/api/settings")
async def put_settings(request: Request):
    b = await body(request)
    cur = modes.app_settings()
    before = cur.get("double_check", True) is not False
    for k in ("mode", "fast_demo", "larger_text", "double_check"):
        if k in (b or {}):
            v = b[k]
            if k == "mode" and v not in ("", "live", "fixtures"):
                raise ApiError(400, "Choose live or demo data.")
            cur[k] = v
    db.kv_put("app_settings", cur)
    after = cur.get("double_check", True) is not False
    if before != after:
        for c in db.case_list():
            d = done_map(c)
            if d[6] and not d[7]:
                log(c["id"], "consultant", "double_check_setting", 7,
                    "Switched the quick double-check on in Settings" if after else "Switched the quick double-check off in Settings")
    return settings_view()


@app.get("/api/selfcheck")
def get_selfcheck():
    return selfcheck.run()


@app.get("/api/samples")
def get_samples():
    return samples.listing()


@app.post("/api/samples/{name}/load")
def load_sample(name: str):
    c = S1.load_sample(name, modes.new_case_mode())
    return {"id": c["id"]}


@app.get("/api/samples/{name}/replies/{idea}")
def sample_reply(name: str, idea: str):
    r = samples.reply_file(name, idea)
    if not r:
        raise ApiError(404, "There's no sample reply for this idea.")
    fn, data = r
    return Response(data, media_type="application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{fn}"'})


@app.get("/api/cases")
def list_cases():
    out = []
    for c in db.case_list():
        from .state import progress
        out.append({"id": c["id"], "title": c["title"], "client_name": c["client_name"], "sample": c.get("sample", ""),
                    "mode": c.get("mode"), "current_step": progress(c)["current"], "updated_at": c["updated_at"],
                    "status": c.get("status", "open")})
    return out


@app.post("/api/cases")
def new_case():
    c = S1.new_case({}, modes.new_case_mode())
    log(c["id"], "consultant", "case_created", 1, "Started a case")
    return {"id": c["id"]}


@app.post("/api/cases/import")
async def import_case(request: Request):
    form = await request.form()
    f = form.get("file")
    if f is None or not hasattr(f, "read"):
        raise ApiError(400, "Choose the JSON file you exported from this tool.")
    try:
        data = json.loads((await f.read()).decode("utf-8"))
        cid = export.import_case(data, modes.new_case_mode())
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        raise ApiError(400, "We couldn't read this file. Choose a JSON export from Research Workbench.")
    return {"id": cid}


# ------------------------------------------------------------------ archive (past work the agent may search)
@app.get("/api/archive")
def archive_list():
    return [{"id": r["id"], "title": r["title"], "filename": r["filename"], "published_date": r["published_date"]}
            for r in db.q("SELECT id, title, filename, published_date FROM archive_doc ORDER BY id DESC")]


@app.post("/api/archive")
async def archive_add(request: Request):
    from .files import parse
    from .core import now_iso
    form = await request.form()
    f = form.get("file")
    if f is None or not hasattr(f, "read"):
        raise ApiError(400, "Choose a file to add.")
    data = await f.read()
    if not (f.filename or "").lower().endswith(parse.ALLOWED):
        raise ApiError(400, "This file type isn't supported. Upload a csv, xlsx, txt or pdf file.")
    try:
        text = parse.parse(f.filename, data)
    except parse.ParseError as e:
        raise ApiError(400, str(e))
    title = str(form.get("title") or "").strip() or f.filename
    rid = db.ex("INSERT INTO archive_doc (title, filename, published_date, text, created_at) VALUES (?,?,?,?,?)",
                (title, f.filename, str(form.get("published_date") or ""), text, now_iso()))
    try:
        db.ex("INSERT INTO archive_fts (rowid, title, text) VALUES (?,?,?)", (rid, title, text))
    except Exception:
        pass
    return {"id": rid}


@app.delete("/api/archive/{aid}")
def archive_delete(aid: int):
    r = db.q("SELECT title, text FROM archive_doc WHERE id=?", (aid,))
    if r:
        try:
            db.ex("INSERT INTO archive_fts (archive_fts, rowid, title, text) VALUES ('delete', ?, ?, ?)", (aid, r[0]["title"], r[0]["text"]))
        except Exception:
            pass
        db.ex("DELETE FROM archive_doc WHERE id=?", (aid,))
    return {"ok": True}


# ------------------------------------------------------------------ one case
@app.get("/api/cases/{cid}")
def get_case(cid: int):
    return bundle.build(case_of(cid))


CASE_FIELDS = ("client_name", "country", "industry", "function", "raw_ask", "title", "client_aliases", "private_numbers")


@app.put("/api/cases/{cid}")
async def put_case(cid: int, request: Request):
    c = case_of(cid)
    b = await body(request) or {}
    upd = {}
    for k in CASE_FIELDS:
        if k in b:
            if k != "title" and done_map(c)[1] and b[k] != c.get(k):
                raise gate("The ask has been checked, so its details can't change now. Reset the case to start again.")
            v = b[k]
            if k in ("client_aliases", "private_numbers"):
                v = [str(x).strip() for x in (v if isinstance(v, list) else str(v).split(",")) if str(x).strip()]
            else:
                v = str(v or "")
            upd[k] = v
    s = {}
    if "ai_reads_client_files" in b:
        s["ai_reads_client_files"] = bool(b["ai_reads_client_files"])
    S1.touch(c, **upd, **({"settings": s} if s else {}))
    return {"ok": True}


@app.delete("/api/cases/{cid}")
def delete_case(cid: int):
    case_of(cid)
    db.case_delete(cid)
    return {"ok": True}


@app.post("/api/cases/{cid}/reset")
def reset_case(cid: int):
    c = case_of(cid)
    if running(cid):
        raise gate("Wait for the current step to finish, then reset.")
    S1.reset(c)
    return {"ok": True}


@app.get("/api/cases/{cid}/activity")
def get_activity(cid: int, since_id: int = 0, format: str = "json"):
    case_of(cid)
    acts = activity(cid, since_id)
    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["id", "time", "actor", "step", "event", "message"])
        for a in acts:
            w.writerow([a["id"], a["ts"], a["actor"], a["step"], a["event_type"], a["message"]])
        return Response(buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="history-case-{cid}.csv"'})
    return acts


@app.get("/api/cases/{cid}/export")
def get_export(cid: int, format: str = ""):
    c = case_of(cid)
    if format not in ("md", "json"):
        raise ApiError(400, "Choose Markdown, JSON or the printable page.")
    b = bundle.build(c)
    if format == "md":
        return Response(export.markdown(b), media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{export.filename(b, "md")}"'})
    return Response(export.as_json(b), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{export.filename(b, "json")}"'})


@app.get("/api/cases/{cid}/jobs/{jid}")
def get_job(cid: int, jid: int):
    j = job_get(jid)
    if not j or j["case_id"] != cid:
        raise ApiError(404, "That job isn't in this case.")
    return j


async def _upload(request: Request) -> tuple[str, bytes | None, str | None, dict]:
    ctype = request.headers.get("content-type", "")
    if "multipart/form-data" in ctype or "application/x-www-form-urlencoded" in ctype:
        form = await request.form()
        f = form.get("file")
        fields = {k: v for k, v in form.items() if k != "file"}
        if f is not None and hasattr(f, "read"):
            return f.filename or "upload.txt", await f.read(), None, fields
        return str(fields.get("filename") or "pasted-note.txt"), None, str(fields.get("text") or ""), fields
    b = await body(request) or {}
    return str(b.get("filename") or "pasted-note.txt"), None, str(b.get("text") or ""), b


@app.post("/api/cases/{cid}/files")
async def add_file(cid: int, request: Request):
    c = case_of(cid)
    fn, data, text, fields = await _upload(request)
    kind = str(fields.get("kind") or "initial")
    if kind not in ("initial", "followup", "expert_note", "trip"):
        raise ApiError(400, "Choose who the file is from.")
    d = done_map(c)
    if kind == "initial":
        if d[1] or running(cid, "frame"):
            raise gate("The ask has been checked. Add new files as a reply in step 5 or step 9.")
        f = S1.add_file(c, fn, data, "initial", text=text)
        return {"file_id": f["id"]}
    if kind == "trip":
        trips = [t for t in db.rows("trip", cid) if t.get("marked_sent_at") and not t.get("reply_file_id")]
        if not trips:
            raise gate("Mark a follow-up request as sent first.")
        S3.trip_reply(c, trips[0]["id"], fn, data, text)
        return {"ok": True}
    if d[7]:
        raise gate("The tests have run. Add new evidence through Fill the gaps.")
    if not d[4]:
        raise gate('Finish "Plan the research" first', ["Plan the research"])
    f = S1.add_file(c, fn, data, kind, text=text, step=5 if not d[6] else 7)
    if d[6]:
        e = S2.ingest_file_now(c, f)
        log(cid, "client" if kind == "followup" else "expert", "reply_added", 7, f"Added {e['id']} ({fn}). It needs your call.")
    return {"file_id": f["id"]}


@app.put("/api/cases/{cid}/files/{fid}/figures")
async def file_figures(cid: int, fid: int, request: Request):
    c = case_of(cid)
    b = await body(request) or {}
    S1.set_file_figures(c, fid, b.get("figures") or [])
    return {"ok": True}


@app.post("/api/cases/{cid}/read-ask")
def read_ask(cid: int):
    return {"job": S1.read_ask(case_of(cid))}


@app.put("/api/cases/{cid}/frame")
async def put_frame(cid: int, request: Request):
    S1.edit_frame(case_of(cid), await body(request) or {})
    return {"ok": True}


@app.post("/api/cases/{cid}/frame/confirm")
def confirm_frame(cid: int):
    return {"job": S1.confirm_frame(case_of(cid))}


@app.get("/api/cases/{cid}/hypotheses")
def get_hyps(cid: int):
    case_of(cid)
    return sorted(db.rows("hypothesis", cid), key=lambda h: h["order"])


@app.put("/api/cases/{cid}/hypotheses")
async def put_hyps(cid: int, request: Request):
    b = await body(request)
    S1.edit_hypotheses(case_of(cid), b if isinstance(b, list) else [b])
    return {"ok": True}


@app.post("/api/cases/{cid}/plan/lock")
async def lock(cid: int, request: Request):
    return {"job": S1.lock_plan(case_of(cid), await body(request) or {})}


@app.post("/api/cases/{cid}/plan/retry")
def plan_retry(cid: int):
    c = case_of(cid)
    if not done_map(c)[2] or done_map(c)[3]:
        raise gate("There's nothing to retry here.")
    return {"job": S1.start_plan(c)}


@app.post("/api/cases/{cid}/needs/retry")
def needs_retry(cid: int):
    c = case_of(cid)
    if not done_map(c)[3] or done_map(c)[4]:
        raise gate("There's nothing to retry here.")
    return {"job": S1.start_route(c)}


@app.post("/api/cases/{cid}/plan/retarget")
async def retarget(cid: int, request: Request):
    return S3.retarget(case_of(cid), await body(request) or {})


@app.get("/api/cases/{cid}/needs")
def get_needs(cid: int):
    case_of(cid)
    return db.rows("need", cid)


@app.put("/api/cases/{cid}/needs/{ref}/query")
async def put_query(cid: int, ref: str, request: Request):
    S1.edit_query(case_of(cid), ref, (await body(request) or {}).get("query"))
    return {"ok": True}


@app.get("/api/cases/{cid}/source-plan")
def get_plan(cid: int):
    case_of(cid)
    return db.rows("plan_item", cid)


@app.put("/api/cases/{cid}/source-plan")
async def put_plan(cid: int, request: Request):
    S1.edit_source_plan(case_of(cid), await body(request))
    return {"ok": True}


@app.get("/api/cases/{cid}/requests")
def get_requests(cid: int):
    return S1.requests_view(case_of(cid))


@app.post("/api/cases/{cid}/requests/mark-sent")
async def mark_sent(cid: int, request: Request):
    return {"job": S1.mark_requests_sent(case_of(cid), await body(request) or {})}


@app.post("/api/cases/{cid}/collect/start")
def collect_start(cid: int):
    return {"job": S2.collect_start(case_of(cid))}


@app.post("/api/cases/{cid}/collect/stop")
def collect_stop(cid: int):
    return S2.stop_collect(case_of(cid))


@app.post("/api/cases/{cid}/clean/run")
def clean_run(cid: int):
    return {"job": S2.clean_run(case_of(cid))}


@app.get("/api/cases/{cid}/evidence")
def get_evidence(cid: int):
    return bundle.build(case_of(cid))["evidence"]


@app.post("/api/cases/{cid}/evidence/{eid}/decision")
async def decision(cid: int, eid: str, request: Request):
    S3.decide(case_of(cid), eid, await body(request) or {})
    return {"ok": True}


@app.put("/api/cases/{cid}/evidence/{eid}/links")
async def links(cid: int, eid: str, request: Request):
    S3.edit_links(case_of(cid), eid, await body(request))
    return {"ok": True}


@app.post("/api/cases/{cid}/evidence/manual")
async def manual(cid: int, request: Request):
    raise ApiError(400, "Type figures against the client file they came from, in step 1.")


@app.post("/api/cases/{cid}/review/seen/{eid}")
async def review_seen(cid: int, eid: str, request: Request):
    S3.seen(case_of(cid), eid, await body(request) or {})
    return {"ok": True}


@app.post("/api/cases/{cid}/review/spot-check/{eid}")
async def review_spot(cid: int, eid: str, request: Request):
    S3.spot_check(case_of(cid), eid, await body(request) or {})
    return {"ok": True}


@app.post("/api/cases/{cid}/review/confirm-sources")
async def review_confirm(cid: int, request: Request):
    S3.confirm_sources(case_of(cid), await body(request) or {})
    return {"ok": True}


@app.post("/api/cases/{cid}/test/run")
def test_run(cid: int):
    S3.run_tests(case_of(cid))
    return {"ok": True}


@app.post("/api/cases/{cid}/trips")
async def trips(cid: int, request: Request):
    return S3.create_trip(case_of(cid), await body(request) or {})


@app.put("/api/cases/{cid}/trips/{tid}")
async def trip_edit(cid: int, tid: int, request: Request):
    S3.edit_trip(case_of(cid), tid, await body(request) or {})
    return {"ok": True}


@app.post("/api/cases/{cid}/trips/{tid}/mark-sent")
@app.post("/api/cases/{cid}/trips/{tid}/sent")
def trip_sent(cid: int, tid: int):
    S3.trip_mark_sent(case_of(cid), tid)
    return {"ok": True}


@app.post("/api/cases/{cid}/trips/{tid}/reply")
async def trip_reply(cid: int, tid: int, request: Request):
    fn, data, text, _ = await _upload(request)
    return {"job": S3.trip_reply(case_of(cid), tid, fn, data, text)}


@app.post("/api/cases/{cid}/trips/{tid}/sample-mix")
async def sample_mix(cid: int, tid: int, request: Request):
    return S3.trip_sample_mix(case_of(cid), tid, await body(request) or {})


@app.post("/api/cases/{cid}/retest")
async def retest(cid: int, request: Request):
    S3.retest(case_of(cid), await body(request) or {})
    return {"ok": True}


@app.post("/api/cases/{cid}/addup/run")
def addup(cid: int):
    return {"job": S3.run_addup(case_of(cid))}


@app.get("/api/cases/{cid}/unknowns")
def unknowns(cid: int):
    case_of(cid)
    s = db.one("summary", cid)
    return (s or {}).get("unknowns") or []


@app.post("/api/cases/{cid}/whatif")
async def whatif(cid: int, request: Request):
    return S3.whatif(case_of(cid), await body(request) or {})


@app.put("/api/cases/{cid}/conclusion")
async def conclusion(cid: int, request: Request):
    S3.save_conclusion(case_of(cid), await body(request) or {})
    return {"ok": True}


@app.post("/api/cases/{cid}/sample/advance")
def advance(cid: int, to: int = 12):
    return {"job": S3.advance(case_of(cid), to)}


@app.post("/api/cases/{cid}/use-demo-data")
def use_demo(cid: int):
    c = case_of(cid)
    if not c.get("sample"):
        raise ApiError(400, "Only sample cases have stored answers.")
    S1.touch(c, mode="fixtures", settings={"live_failures": 0})
    log(cid, "consultant", "mode_switched", c.get("current_step", 1), "Switched this case to its stored sample answers")
    _retry_failed(c)
    return {"ok": True}


def _retry_failed(c: dict) -> None:
    from .core import latest_jobs
    for kind, j in latest_jobs(c["id"]).items():
        if j["status"] != "failed":
            continue
        if kind == "frame":
            S1.read_ask(c)
        elif kind == "plan":
            S1.start_plan(c)
        elif kind == "route":
            S1.start_route(c)
        elif kind == "collect":
            S2.start_collect(c)
        elif kind == "clean":
            S2.start_clean(c)
        elif kind == "addup":
            from .core import start_job
            start_job(c["id"], "addup", lambda job: S3._addup_job(job, c["id"]), progress={"label": "Writing the summary"})


@app.post("/api/cases/{cid}/fresh-answers")
async def fresh(cid: int, request: Request):
    c = case_of(cid)
    on = bool((await body(request) or {}).get("on", True))
    S1.touch(c, settings={"bypass_cache": on})
    log(cid, "consultant", "fresh_answers", c.get("current_step", 1),
        "Asked for fresh answers for this case instead of saved ones" if on else "Went back to saved answers for this case")
    return {"ok": True}


@app.put("/api/cases/{cid}/settings")
async def case_settings(cid: int, request: Request):
    c = case_of(cid)
    b = await body(request) or {}
    s = {}
    if "ai_reads_client_files" in b:
        s["ai_reads_client_files"] = bool(b["ai_reads_client_files"])
    if "bypass_cache" in b:
        s["bypass_cache"] = bool(b["bypass_cache"])
    S1.touch(c, settings=s)
    return {"ok": True}


# ------------------------------------------------------------------ the front end (frontend/dist, served as-is)
@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "DELETE"])
def api_404(rest: str):
    raise ApiError(404, "Not found")


@app.get("/{path:path}")
def static(path: str):
    root = config.DIST_DIR.resolve()
    target = (root / path).resolve() if path else root / "index.html"
    if path and str(target).startswith(str(root)) and target.is_file():
        headers = {"Cache-Control": "no-cache"} if target.suffix == ".html" else {}
        return FileResponse(target, headers=headers)
    return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})
