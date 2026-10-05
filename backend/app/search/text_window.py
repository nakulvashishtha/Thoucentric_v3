"""Send only the text around candidate figures to the model (at most max_page_chars), never whole pages."""
from __future__ import annotations

import re


def window(text: str, max_chars: int = 8000) -> str:
    text = text or ""
    if len(text) <= max_chars:
        return text
    hits = [m.start() for m in re.finditer(r"\d[\d,.]*\s*(?:%|per ?cent|million|billion|crore|lakh|months|years)", text)]
    if not hits:
        return text[:max_chars]
    half = max_chars // (2 * min(len(hits), 8))
    spans = []
    for h in hits[:40]:
        a, b = max(0, h - half), min(len(text), h + half)
        if spans and a <= spans[-1][1]:
            spans[-1] = (spans[-1][0], b)
        else:
            spans.append((a, b))
    out, total = [], 0
    for a, b in spans:
        piece = text[a:b]
        if total + len(piece) > max_chars:
            piece = piece[: max_chars - total]
        out.append(piece)
        total += len(piece)
        if total >= max_chars:
            break
    return "\n...\n".join(out)
