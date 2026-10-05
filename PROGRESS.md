# Progress

**Current:** Checkpoint 5 done (deployment package). Next: the user deploys (RUNBOOK.md), then checkpoint 6 fixes. The user asked for all checkpoints without approval stops.

| Checkpoint | Status |
|---|---|
| 1 Rule engine + unit tests | Done |
| 2 Database, state machine, API, fixtures, Sample 1 | Done: contract_check 72/73 (73rd needs Sample 2, checkpoint 4); deep compare matches the recording |
| 3 Real UI end to end + screenshots | Done: all 12 steps through the browser; docs/checkpoint3 side-by-sides |
| 4 Live layer + Sample 2 | Done: contract_check 73/73; sample_check passes both samples; live paths tested with stand-ins |
| 5 Deployment package | Done: image built and run here; 74/74 contract checks in the container; 49 MB memory |
| 6 Fixes from live testing | Not started |

**Decisions**
- Storage: one SQLite table per record type, fields kept as JSON; links and the current verdict live inside their evidence/idea rows.
- Sample 1 pack generated from reference/recorded_backend_states.json, so stored answers match the original exactly.
- Fixed one recorded glitch: the consultant-tier reason no longer repeats its prefix.
- Demo data mode: a file or idea the sample has no stored answer for degrades gracefully (no figures / a plain question).
- FIXTURE_PACE (default 0.12 s per item) paces stored answers so steps 5 and 6 visibly progress.

- The frozen front end rejects an item with no reason (its reason picker is switched off), so the backend accepts that.
- The frozen guide CSS hides every banner, so failures were silent. frontend/dist/live-errors.css (linked in index.html)
  shows error banners only; the frozen assets/ and walkthrough/ files are untouched.

- Live model: JSON-schema structured output, no temperature (current Sonnet rejects it), effort low/medium, one retry,
  cache by hash, ledger per call. Self-check checks models via the Models API (no generation cost).
- Added a Kenya (KE) source-quality pack to source_registry.yaml for Sample 2.

**Known issues:** none open.

**Commands:** `make install` · `make demo` (app on :8000, demo data) · `make test` · `make check` · `python tools/sample_check.py http://localhost:8000 --sample sample_02_hospital_expansion`
