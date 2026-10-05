"""SQLite storage. One table per record type; each row keeps its fields as JSON next to its id and case id.

WAL mode, tables created at startup, no migration framework. All access goes through one lock, so background jobs and
requests never write at the same time."""
from __future__ import annotations

import json
import sqlite3
import threading

from . import config

TABLES = ("frame", "ruleset", "hypothesis", "need", "client_file", "plan_item", "evidence", "calc", "trip",
          "overall", "summary", "conclusion", "job", "outbound_query", "cost_ledger", "verdict_history")

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None


def connect(path: str | None = None) -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is not None and path is None:
            return _conn
        if path is None:
            d = config.data_dir()
            d.mkdir(parents=True, exist_ok=True)
            path = str(d / "workbench.db")
        c = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        c.row_factory = sqlite3.Row
        if path != ":memory:":
            c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("CREATE TABLE IF NOT EXISTS cases (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL)")
        for t in TABLES:
            c.execute(f"CREATE TABLE IF NOT EXISTS {t} (id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER, "
                      "data TEXT NOT NULL)")
            c.execute(f"CREATE INDEX IF NOT EXISTS ix_{t}_case ON {t}(case_id)")
        c.execute("CREATE TABLE IF NOT EXISTS activity (id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER, "
                  "ts TEXT, actor TEXT, event_type TEXT, step INTEGER, message TEXT, payload_json TEXT)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_activity_case ON activity(case_id)")
        c.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS llm_cache (k TEXT PRIMARY KEY, job TEXT, model TEXT, prompt_version TEXT, "
                  "output_json TEXT, created_at TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS search_cache (k TEXT PRIMARY KEY, provider TEXT, response_json TEXT, "
                  "created_at TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS archive_doc (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, "
                  "filename TEXT, published_date TEXT, text TEXT, created_at TEXT)")
        try:
            c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS archive_fts USING fts5(title, text, content='archive_doc', "
                      "content_rowid='id')")
        except sqlite3.OperationalError:
            pass                                  # FTS5 missing: archive search falls back to LIKE
        _conn = c
        return c


def reset_for_tests(path: str = ":memory:") -> None:
    global _conn
    with _lock:
        _conn = None
        connect(path)


def q(sql: str, args: tuple = ()) -> list[sqlite3.Row]:
    with _lock:
        return connect().execute(sql, args).fetchall()


def ex(sql: str, args: tuple = ()) -> int:
    with _lock:
        cur = connect().execute(sql, args)
        return cur.lastrowid


# ------------------------------------------------------------------ cases
def case_insert(data: dict) -> int:
    with _lock:
        cid = ex("INSERT INTO cases (data) VALUES (?)", (json.dumps(data),))
        data["id"] = cid
        ex("UPDATE cases SET data=? WHERE id=?", (json.dumps(data), cid))
        return cid


def case_get(cid: int) -> dict | None:
    r = q("SELECT data FROM cases WHERE id=?", (cid,))
    return json.loads(r[0]["data"]) if r else None


def case_put(data: dict) -> None:
    ex("UPDATE cases SET data=? WHERE id=?", (json.dumps(data), data["id"]))


def case_list() -> list[dict]:
    return [json.loads(r["data"]) for r in q("SELECT data FROM cases ORDER BY id DESC")]


def case_delete(cid: int) -> None:
    with _lock:
        for t in TABLES:
            ex(f"DELETE FROM {t} WHERE case_id=?", (cid,))
        ex("DELETE FROM activity WHERE case_id=?", (cid,))
        ex("DELETE FROM cases WHERE id=?", (cid,))


def case_clear(cid: int, keep: tuple = ("cost_ledger",)) -> None:
    """Remove everything recorded for a case except the case row itself (and the spending ledger)."""
    with _lock:
        for t in TABLES:
            if t not in keep:
                ex(f"DELETE FROM {t} WHERE case_id=?", (cid,))


# ------------------------------------------------------------------ rows
def insert(table: str, cid: int, data: dict) -> dict:
    with _lock:
        rid = ex(f"INSERT INTO {table} (case_id, data) VALUES (?, ?)", (cid, "{}"))
        keep = table in KEEP_ID and data.get("id") is not None
        data = dict(data, id=data["id"] if keep else rid, case_id=cid)
        if table in KEEP_ID:
            data["pk"] = rid
        ex(f"UPDATE {table} SET data=? WHERE id=?", (json.dumps(data), rid))
        return data


KEEP_ID = ("evidence", "trip")          # these carry their own per-case id ("E7", trip 1); the row id is "pk"


def _pk(table: str, row: dict) -> int:
    return row["pk"] if table in KEEP_ID else row["id"]


def put(table: str, row: dict) -> None:
    ex(f"UPDATE {table} SET data=? WHERE id=?", (json.dumps(row), _pk(table, row)))


def rows(table: str, cid: int) -> list[dict]:
    return [json.loads(r["data"]) for r in q(f"SELECT data FROM {table} WHERE case_id=? ORDER BY id", (cid,))]


def one(table: str, cid: int) -> dict | None:
    r = q(f"SELECT data FROM {table} WHERE case_id=? ORDER BY id DESC LIMIT 1", (cid,))
    return json.loads(r[0]["data"]) if r else None


def get(table: str, rid: int) -> dict | None:
    r = q(f"SELECT data FROM {table} WHERE id=?", (rid,))
    return json.loads(r[0]["data"]) if r else None


def delete(table: str, row: dict) -> None:
    ex(f"DELETE FROM {table} WHERE id=?", (_pk(table, row),))


def delete_all(table: str, cid: int) -> None:
    ex(f"DELETE FROM {table} WHERE case_id=?", (cid,))


# ------------------------------------------------------------------ key-value (app settings)
def kv_get(k: str, default=None):
    r = q("SELECT v FROM kv WHERE k=?", (k,))
    return json.loads(r[0]["v"]) if r else default


def kv_put(k: str, v) -> None:
    ex("INSERT INTO kv (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, json.dumps(v)))


def lock() -> threading.RLock:
    return _lock
