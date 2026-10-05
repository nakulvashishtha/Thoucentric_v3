"""Turn uploaded files into plain text where every line carries its locator, so a quoted figure can be checked
at the exact place it came from. csv and xlsx cells become [B4] or [Sheet!B4]; text lines become [line 3];
pdf pages become [page 2]; web text becomes para 1, para 2..."""
from __future__ import annotations

import csv
import io
import re

MAX_CHARS = 200_000
ALLOWED = (".csv", ".xlsx", ".txt", ".pdf", ".md")


class ParseError(Exception):
    pass


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return str(int(v)) if v == int(v) else repr(v)
    return str(v).strip()


def _col(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def parse(filename: str, data: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".csv"):
        text = data.decode("utf-8-sig", errors="replace")
        out = []
        for r, row in enumerate(csv.reader(io.StringIO(text)), 1):
            cells = [f"[{_col(c)}{r}] {v.strip()}" for c, v in enumerate(row) if v.strip()]
            if cells:
                out.append(" | ".join(cells))
        return "\n".join(out)[:MAX_CHARS]
    if name.endswith(".xlsx"):
        import openpyxl
        try:
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception as e:
            raise ParseError("We couldn't read this spreadsheet. Save it again as .xlsx or .csv and try again.") from e
        out = []
        for ws in wb.worksheets:
            out.append(f"## Sheet: {ws.title}")
            for row in ws.iter_rows():
                cells = []
                for c in row:
                    v = c.value
                    if v is None or _cell(v) == "":
                        continue
                    if isinstance(v, (int, float)) and "%" in (c.number_format or ""):
                        s = _cell(round(v * 100, 6)) + "%"
                    else:
                        s = _cell(v)
                    cells.append(f"[{ws.title}!{c.coordinate}] {s}")
                if cells:
                    out.append(" | ".join(cells))
            if sum(len(x) for x in out) > MAX_CHARS:
                break
        wb.close()
        return "\n".join(out)[:MAX_CHARS]
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            out = []
            for i, page in enumerate(reader.pages, 1):
                t = re.sub(r"[ \t]+", " ", page.extract_text() or "").strip()
                if t:
                    out.append(f"[page {i}] " + t.replace("\n", " "))
                if sum(len(x) for x in out) > MAX_CHARS:
                    break
        except Exception as e:
            raise ParseError("We couldn't read this PDF. If it is a scan, add a text version instead.") from e
        if not out:
            raise ParseError("This PDF has no readable text. If it is a scan, add a text version instead.")
        return "\n".join(out)[:MAX_CHARS]
    text = data.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    return "\n".join(f"[line {i}] {l.rstrip()}" for i, l in enumerate(lines, 1) if l.strip())[:MAX_CHARS]


def pasted(text: str) -> str:
    lines = (text or "").splitlines()
    return "\n".join(f"[line {i}] {l.rstrip()}" for i, l in enumerate(lines, 1) if l.strip())[:MAX_CHARS]


_LOC = re.compile(r"\[((?:line|page) \d+|(?:[^\]!]+!)?[A-Z]{1,3}\d+)\] ")


def segments(text: str, web: bool = False) -> dict[str, str]:
    """locator -> text at that place. Web text has no tags: paragraphs become para 1, para 2..."""
    segs: dict[str, str] = {}
    if web or not _LOC.search(text or ""):
        paras = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
        if len(paras) == 1:
            paras = [p.strip() for p in (text or "").split("\n") if p.strip()] if "\n" in text and not web else paras
        for i, p in enumerate(paras, 1):
            segs[f"para {i}"] = p
        return segs
    parts = _LOC.split(text)
    # parts: [before, loc1, text1, loc2, text2, ...]
    for i in range(1, len(parts) - 1, 2):
        segs[parts[i]] = parts[i + 1].split(" | ")[0].strip().rstrip("\n").strip()
    return segs


def numbers_in(text: str) -> list[float]:
    out = []
    for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", text or ""):
        raw = m.group(0).rstrip(",")
        try:
            out.append(float(raw.replace(",", "")))
        except ValueError:
            pass
    return out


def verify(fig: dict, segs: dict[str, str]) -> tuple[bool, str]:
    """A figure is verified only if its value appears in the quote and the quote appears at the stated place."""
    loc = (fig.get("locator") or "").strip()
    quote = (fig.get("quote_span") or "").strip()
    if not quote:
        return False, "no quote given"
    where = segs.get(loc)
    if where is None:
        hit = [k for k, v in segs.items() if _norm(quote) in _norm(v)]
        if not hit:
            return False, f"quote not found at {loc or 'the stated place'}"
        loc, where = hit[0], segs[hit[0]]
    if _norm(quote) not in _norm(where):
        hit = [k for k, v in segs.items() if _norm(quote) in _norm(v)]      # quoted word for word, at another place
        if not hit:
            return False, f"quote not found at {loc}"
        loc, where = hit[0], segs[hit[0]]
    nums = numbers_in(quote)
    vals = [fig.get(k) for k in ("value", "low", "high") if fig.get(k) is not None]
    if not vals or not all(any(abs(float(v) - n) < 1e-6 or abs(float(v) - n) <= 0.005 * abs(n) for n in nums)
                           for v in vals):
        return False, f"the number isn't in the quote at {loc}"
    return True, f"found at {loc}"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("’", "'").strip().lower())
