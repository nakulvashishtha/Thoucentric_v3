# Progress

**Current:** Checkpoint 2 done (backend and API). The user asked for all checkpoints without approval stops.

| Checkpoint | Status |
|---|---|
| 1 Rule engine + unit tests | Done |
| 2 Database, state machine, API, fixtures, Sample 1 | Done: contract_check 72/73 (73rd needs Sample 2, checkpoint 4); deep compare matches the recording |
| 3 Real UI end to end + screenshots | Next |
| 4 Live layer + Sample 2 | Not started |
| 5 Deployment package | Not started |
| 6 Fixes from live testing | Not started |

**Decisions**
- Storage: one SQLite table per record type, fields kept as JSON; links and the current verdict live inside their evidence/idea rows.
- Sample 1 pack generated from reference/recorded_backend_states.json, so stored answers match the original exactly.
- Fixed one recorded glitch: the consultant-tier reason no longer repeats its prefix.
- Demo data mode: a file or idea the sample has no stored answer for degrades gracefully (no figures / a plain question).
- FIXTURE_PACE (default 0.12 s per item) paces stored answers so steps 5 and 6 visibly progress.

**Known issues:** none open.

**Commands:** `make install` · `make demo` (app on :8000, demo data) · `make test` · `make check` (contract check against a running server)
