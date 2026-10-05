# Research Workbench

A live research agent for consultants, for any client, sector or country. The consultant pastes a client's ask. The
agent frames it, sets targets before reading evidence, gathers and grades sources, tests each idea in code, and
writes a traceable summary. The consultant signs off at every important step and writes the conclusion.

- **Run locally:** `pip install -r requirements-dev.txt` then `make run` (or `make demo` for stored answers, no keys). Open http://localhost:8000.
- **Test:** `make test` (no keys, no real AI or search calls). With a server running: `make check` and
  `python tools/sample_check.py http://localhost:8000 --sample sample_02_hospital_expansion`.
- **Deploy:** see [RUNBOOK.md](RUNBOOK.md) (Render, Docker). Demo script: [DEMO.md](DEMO.md).
- **Layout:** `backend/app` (FastAPI, rule engine in `engine/`, model and search clients in `llm/` and `search/`),
  `backend/prompts` (versioned model prompts), `backend/config` (rules, source registry, prices), `backend/samples`
  (two sample packs), `frontend/dist` (the approved, compiled UI, served as-is), `tests/`.
- **What is stored:** cases, uploaded files' text, evidence, decisions, the History log and a spending ledger, in SQLite
  under `DATA_DIR`. Nothing is sent to clients or experts by the app. Delete a case from the home page; on the free
  hosting tier everything is cleared on restart (use Download JSON to keep a case).
- **Keys** live only in environment variables or a git-ignored `.env` (see `.env.example`).
