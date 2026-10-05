"""Live sources: Tavily web search, the firm archive (keyword search over uploaded documents) and, for sample cases
only, the sample's simulated database. The privacy filter runs again right before every outbound call."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
from urllib.parse import urlsplit

import httpx

from .. import budget, config, db
from ..core import JobError, log, now_iso
from ..engine import privacy
from ..engine.credibility import domain_of
from .simulated import SimulatedSources
from .text_window import window

TAVILY_URL = "https://api.tavily.com/search"
_BLOCKED_HOSTS = ("localhost", "metadata.google.internal")


def ping() -> tuple[bool, str]:
    try:
        r = httpx.post(TAVILY_URL, json={"query": "official statistics", "max_results": 1, "search_depth": "basic"},
                       headers={"Authorization": f"Bearer {config.env('TAVILY_API_KEY')}"}, timeout=15)
    except httpx.HTTPError:
        return False, "The search service can't be reached from the server."
    if r.status_code in (401, 403):
        return False, "The search key was refused."
    if r.status_code == 432 or r.status_code == 433:
        return False, "The search plan's credits are used up."
    if r.status_code >= 400:
        return False, f"The search service answered with an error ({r.status_code})."
    return True, "Search answers."


class LiveSources:
    live = True

    def __init__(self, case: dict):
        self.case = case
        self.sim = SimulatedSources(case) if case.get("sample") else None

    # ------------------------------------------------------------------ web
    def _tavily(self, query: str, limit: int) -> list[dict]:
        files = db.rows("client_file", self.case["id"])
        chk = privacy.check_outbound(query, self.case, files)
        if chk["blocked"]:
            log(self.case["id"], "rule_engine", "query_blocked", self.case.get("current_step", 5),
                f"Blocked a search that contained a private term: {', '.join(chk['blocked'])}")
            return []
        q = chk["sanitised"]
        ck = hashlib.sha256(f"tavily|{q}|{limit}".encode()).hexdigest()
        bypass = bool((self.case.get("settings_json") or {}).get("bypass_cache"))
        hit = None if bypass else db.q("SELECT response_json FROM search_cache WHERE k=?", (ck,))
        if hit:
            data = json.loads(hit[0]["response_json"])
        else:
            budget.check(self.case["id"], "search")
            try:
                r = httpx.post(TAVILY_URL, json={"query": q, "search_depth": "basic", "max_results": max(1, min(limit, 5)),
                                                 "include_answer": False},
                               headers={"Authorization": f"Bearer {config.env('TAVILY_API_KEY')}"}, timeout=20)
            except httpx.HTTPError:
                raise JobError("The search service didn't answer. Press Try again, or stop collecting and keep what arrived.")
            if r.status_code in (401, 403):
                raise JobError("The search key was refused. Open Settings and run the checks to see the fix.")
            if r.status_code >= 400:
                raise JobError("The search service had a problem. Press Try again in a minute.")
            data = r.json()
            budget.record(self.case["id"], "search", "search", search_credits=1.0)
            db.ex("INSERT OR REPLACE INTO search_cache (k, provider, response_json, created_at) VALUES (?,?,?,?)",
                  (ck, "tavily", json.dumps(data), now_iso()))
        out = []
        for res in (data.get("results") or [])[:limit]:
            url = res.get("url") or ""
            text = (res.get("content") or "").strip()
            if len(text) < 200:
                text = fetch_text(url, self.case) or text
            dom = domain_of(url)
            out.append({"title": (res.get("title") or dom)[:200], "url": url, "domain": dom, "publisher": dom,
                        "source_name": dom, "published_date": str(res.get("published_date") or "")[:10],
                        "data_as_of": "", "text": window(text, config.rules()["limits"]["max_page_chars"]),
                        "seed_id": "", "simulated": False, "group": "open_web"})
        return out

    # ------------------------------------------------------------------ firm archive
    def _archive(self, query: str, limit: int) -> list[dict]:
        words = [w for w in re.findall(r"[A-Za-z]{3,}", query)][:8]
        if not words:
            return []
        rows = []
        try:
            rows = db.q("SELECT d.id, d.title, d.filename, d.published_date, d.text FROM archive_fts f JOIN archive_doc d "
                        "ON d.id = f.rowid WHERE archive_fts MATCH ? ORDER BY rank LIMIT ?",
                        (" OR ".join(words), limit))
        except Exception:
            like = f"%{words[0]}%"
            rows = db.q("SELECT id, title, filename, published_date, text FROM archive_doc WHERE text LIKE ? LIMIT ?",
                        (like, limit))
        return [{"title": r["title"], "url": "", "domain": "", "publisher": "Firm research archive",
                 "source_name": "Firm research archive", "published_date": r["published_date"] or "", "data_as_of": "",
                 "text": window(r["text"], config.rules()["limits"]["max_page_chars"]), "seed_id": "",
                 "simulated": False, "group": "firm_archive"} for r in rows]

    # ------------------------------------------------------------------ the interface the pipeline uses
    def search(self, group: str, need_ref: str, query: str = "", limit: int = 4) -> list[dict]:
        if group == "open_web":
            return self._tavily(query, limit)
        if group == "firm_archive":
            found = self._archive(query, limit)
            if self.sim:
                found += self.sim.search(group, need_ref, query, limit)
            return found[:limit]
        if group == "paid_db" and self.sim:
            return self.sim.search(group, need_ref, query, limit)
        return []

    def benchmark(self, idea_code: str, query: str = "") -> list[dict]:
        found = self._tavily(query, 3) if query else []
        return [r for r in found if r["text"]][:1]

    def expert_notes(self) -> list[dict]:
        return self.sim.expert_notes() if self.sim else []


# ------------------------------------------------------------------ guarded page fetcher (search results only)
def _safe_host(host: str) -> bool:
    if not host or host in _BLOCKED_HOSTS or host.endswith(".local") or host.endswith(".internal"):
        return False
    try:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
    except (socket.gaierror, ValueError):
        return False
    return True


def fetch_text(url: str, case: dict, max_bytes: int = 2_000_000) -> str:
    """Fetch a page returned by search: http(s) only, no private or loopback addresses (checked on every redirect),
    10-second timeout, 2 MB cap. Returns plain text, or "" if the page can't be read."""
    if privacy.find_private(url, case, db.rows("client_file", case["id"])):
        return ""
    try:
        for _ in range(4):
            p = urlsplit(url)
            if p.scheme not in ("http", "https") or not _safe_host(p.hostname or ""):
                return ""
            with httpx.stream("GET", url, timeout=10, follow_redirects=False,
                              headers={"User-Agent": "ResearchWorkbench/1.0"}) as r:
                if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                    url = str(httpx.URL(url).join(r.headers["location"]))
                    continue
                if r.status_code >= 400:
                    return ""
                buf = b""
                for chunk in r.iter_bytes():
                    buf += chunk
                    if len(buf) > max_bytes:
                        break
                return html_to_text(buf.decode(r.encoding or "utf-8", errors="replace"))
    except httpx.HTTPError:
        return ""
    return ""


def html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>|</tr>", "\n\n", html)
    text = re.sub(r"<[^>]+>", " ", html)
    import html as _h
    text = _h.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if len(p.strip()) > 40]
    return "\n\n".join(paras)
