"""The app's own text never says "partner", and never names the example client (samples and fixtures excluded)."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
APP_TEXT = [ROOT / "backend" / "app", ROOT / "backend" / "prompts", ROOT / "backend" / "config"]


def _files():
    for d in APP_TEXT:
        for p in d.rglob("*"):
            if p.is_file() and p.suffix in (".py", ".md", ".yaml", ".txt", ".json"):
                yield p


def test_no_partner_in_app_text():
    hits = [str(p) for p in _files() if re.search(r"partner", p.read_text(encoding="utf-8"), re.I)]
    assert not hits, hits


def test_example_client_name_only_in_samples():
    hits = [str(p) for p in _files() if re.search(r"Example Client", p.read_text(encoding="utf-8"))]
    assert not hits, hits


def test_no_sample_specific_terms_in_app_code():
    terms = ["credit card", "Nakuru", "hospital", "rbi.org", "CardScope", "crore cards"]
    for p in (ROOT / "backend" / "app").rglob("*.py"):
        t = p.read_text(encoding="utf-8")
        for term in terms:
            assert term.lower() not in t.lower(), (p, term)
