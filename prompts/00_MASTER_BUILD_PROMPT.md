# 00 · MASTER BUILD PROMPT — Research Workbench (live, deployable prototype)

You are a senior full-stack engineer and AI-systems architect working in Claude Code. Your job is to turn this pack into a **live, deployable, working prototype** of **Research Workbench**: a research agent that helps a **consultant** do research for **any client, industry, country or function**. The consultant pastes a real client ask. A multi-step agent frames the question, plans the tests, gathers real evidence, grades source credibility, tests ideas against pass lines fixed in advance, and produces a traceable answer. The consultant signs off at every important step. The agent never writes the conclusion.

You have everything you need in this folder. You do not need any other context. Read this file completely, then `CLAUDE.md`, then the documents it points to, in the order given in section 3.

---

## 1. The single most important rule: the output must not change

The product was first built as a scripted demo (**"Demo 2"**, saved as `reference/research_workbench_demo_2.html`; open it in a browser and play it). Its **screens, wording, step order, simplicity and self-explanatory feel are approved and frozen.** The live product must look and read **exactly** like it:

- Same 12 steps, same order, same step titles, same button labels, same plain-English language, same colours and fonts.
- The same **three-pane layout**: a **journey strip along the top** (12 steps, an agent band, orange "you" pins), the **real tool on the left**, and a **"Behind step N of 12" diagram on the right** that lights up from real events.
- **No time-saved tile and no timeline.** Demo 2 does not have one. Do not add one.
- A small **roadmap button** at the top (section 7). Nothing else is added to the UI.
- Do not rewrite, "improve", shorten or reword any text. Do not add a step, remove a step, merge steps, or add a screen.

This is achieved by **not rebuilding the front end**. It is already built and supplied compiled, byte-for-byte as approved, in `frontend/dist/`. Your job is to build the **backend that makes it live**, serve the front end, and deploy it. Every word the user sees comes either from the compiled front end (fixed) or from sentences the backend returns (`reason` messages, verdict explanations, activity lines, job labels). Those backend sentences are recorded in `reference/recorded_backend_states.json` and `prompts/04_API_CONTRACT.md`; reproduce them **character for character** for the cases they cover, and write new ones in exactly the same voice (plain, short, like a helpful colleague) for new situations.

---

## 2. What is in this pack

```
README_START_HERE.md         how the user will run you (not for you)
CLAUDE.md                    your standing instructions (approval checkpoints, secrets, resume protocol)
HOW_TO_START.md              user-facing steps
.env.example  .gitignore
prompts/
  00_MASTER_BUILD_PROMPT.md  this file
  01_BACKEND_BUILD_SPEC.md   the full backend specification (engine rules, state machine, data model, LLM jobs, security, budget, tests, deployment, acceptance). Section 12 (front end) is superseded.
  02_UI_LANGUAGE_SPEC.md     the language and screen rules the front end follows (read it to understand the voice; do NOT rebuild the UI)
  03_COST_PLAN.md            what it costs to run, and the controls
  04_API_CONTRACT.md         every route, body, response, 409 message, job label and activity line the front end expects
  04_CASE_BUNDLE_SCHEMA.md   every path of the GET /api/cases/{id} response, with type and example
  05_WALKTHROUGH_PANES_SPEC.md  the top strip and the right-hand diagram: what each box means
frontend/dist/              THE PRODUCT UI, compiled and approved. index.html, assets/app.js + app.css, walkthrough/ (guide chrome), roadmap.html
reference/
  research_workbench_demo_2.html   the approved single-file demo; the visual and wording reference
  recorded_backend_states.json     19 full case bundles recorded from the original backend on Sample 1, plus samples list, settings, self-check, exports, what-if checks
  offline_api_replica.js           a JavaScript replica of the original server's rules; port its logic to Python
  sample_export.md  sample_export.json   what Export must produce
  screens/                         screenshots of every step of Demo 2 (1440x860)
design/                     tokens.css (colours, fonts) and three original reference files for the explanation
tools/
  mock_api_server.js        stand-in backend (Sample 1 only) that serves frontend/dist: use it to SEE the product before the backend exists
  contract_check.py         drives Sample 1 through all 12 steps against YOUR server and checks shapes, verdicts and gates
  shape_diff.py             compares one of your bundles with a recorded one, key by key
deploy/                     Dockerfile, render.yaml, README (templates)
```

---

## 3. Reading order and precedence

Read in this order: `CLAUDE.md` → this file → `prompts/01_BACKEND_BUILD_SPEC.md` (all of it; it is long and it is the backbone) → `prompts/04_API_CONTRACT.md` → skim `prompts/04_CASE_BUNDLE_SCHEMA.md` → `prompts/05_WALKTHROUGH_PANES_SPEC.md` → `prompts/03_COST_PLAN.md` → `prompts/02_UI_LANGUAGE_SPEC.md` (for voice only). Open `reference/research_workbench_demo_2.html` in a browser (or run the mock, section 8) and click through it once.

**When sources disagree, the higher one wins:**

1. `reference/recorded_backend_states.json` and the compiled front end (they are the facts the UI depends on: URLs, field names, shapes, exact sentences).
2. `prompts/04_API_CONTRACT.md` and `reference/offline_api_replica.js`.
3. `reference/research_workbench_demo_2.html` and `reference/screens/` (what the user sees).
4. `prompts/01_BACKEND_BUILD_SPEC.md` (engine, rules, state machine, data model, LLM jobs, security, budget, deployment, tests).
5. `prompts/02_UI_LANGUAGE_SPEC.md`, `prompts/03_COST_PLAN.md`.
6. The original `design/` references (colours and fonts only).

If you find a real conflict you cannot resolve with this order, choose the option that keeps the UI identical, record it in `PROGRESS.md`, and mention it in your checkpoint report.

---

## 4. What the product is (so you build the right thing)

- **Generic.** No client, sector, country or number may be hard-coded outside `backend/samples/`, `backend/fixtures/` and `design/`. It must work on any consultant use case: a credit-card launch in India (Sample 1), a hospital in Nakuru (Sample 2), or a blank case where the consultant pastes any ask and uploads any files.
- **Two non-human actors.** The **language model** reads, writes and sorts (reframes the ask, drafts ideas, routes needs, writes search queries, extracts figures with quotes, describes sources, proposes links, drafts follow-ups, writes the summary). It **never** decides a verdict, confidence, approval, source tier or recommendation. The **rule engine** is plain deterministic code (no LLM inside): it locks pass lines, strips private data, grades source credibility, de-duplicates, converts units, runs the checklist, picks spot checks, computes all maths, gives every verdict and confidence, applies the adding-up rule and enforces trip limits.
- **Humans.** The consultant is the only user. Client and experts supply files and notes that the consultant uploads or pastes. **Nothing is sent to anyone by the app**; it prepares text and files for the consultant to send.
- **The word "partner"** must not appear in the app's own text (UI, messages, LLM prompts, export templates). The compiled front end already complies; add the scan test from section 16 of the build spec for the backend.
- **The 12 steps** and what each does are in build spec section 9 and in `prompts/05_WALKTHROUGH_PANES_SPEC.md`: 1 Describe the ask · 2 Confirm the question · 3 Set the targets · 4 Plan the research · 5 Gathering evidence · 6 Checking the evidence · 7 Review the evidence · 8 Results · 9 Fill the gaps · 10 The answer · 11 What if... · 12 Your conclusion. Steps 5 and 6 need no person. Steps 1, 2, 3, 4, 7 and 12 are sign-offs. 9 and 11 are optional.

---

## 5. Stack and architecture

- **Backend:** Python 3.11, FastAPI, SQLite (WAL, tables created at startup, no migration framework), `httpx`, `pydantic`, `pyyaml`, `openpyxl`, a pdf text extractor, the official `anthropic` SDK. No Celery, no Redis, no websockets: background jobs are threads or `asyncio` tasks that write progress into the `jobs` table; the browser polls.
- **Front end:** none to build. FastAPI serves `frontend/dist/` at `/` with `index.html` fallback for unknown non-`/api` paths (the app is hash-routed, but keep the fallback). Static files are served with correct types; `walkthrough/` and `roadmap.html` are served as-is.
- **One Docker service**, same origin, `/api` for the API, `/healthz` for health. Bind `0.0.0.0:$PORT`. See build spec section 17 for the full pre-flight list.
- **Modes:** `MODE=fixtures` (stored answers for the samples; no keys needed) and `MODE=live` (real Anthropic and Tavily). With keys missing the app falls back to fixtures and says so in `GET /api/settings` (`notice`) and the self-check. Build spec section 5 has the details.
- **Repository layout:** build spec section 15, **minus** `frontend/src` (not needed). `frontend/dist` is committed (it is a product asset). Keep `.env` out of git.

---

## 6. Build plan and approval checkpoints

Follow `CLAUDE.md`: commit and **STOP** after each checkpoint, report in at most 15 lines (what was built, test results, exact commands to run and view it, anything simulated, defaults chosen), and wait for the user to type **approve**. Never start the next checkpoint on your own. Plan in at most 40 lines at the start; do not re-plan.

| # | Build | Proof you must show |
|---|---|---|
| **1** | **Engine** (build spec section 8): verdict, checklist, credibility, convert, dedup, privacy, trips, spotcheck, whatif. Port `verdictOf`, `classify`, `fmt`, `withUnit`, `figText`, `join`, `evalFormula`, `whatIf`, `retarget`, `sliderRange` from `reference/offline_api_replica.js` **exactly**; keep every sentence. Config files `rules.yaml`, `source_registry.yaml`, `prices.yaml` (values in `bundle.rules.thresholds` and `meta.settings.rules_yaml`). Unit tests first. | test output; the Sample 1 verdict table (H1 Not supported / Strong, H2 Not enough evidence → Supported / Fair after a trip, H3 Supported / Fair, H4 Supported / Weak, overall Not achievable); `meta.whatif_checks` all reproduced |
| **2** | **Database, state machine, jobs, activity log, the whole API** exactly as `04_API_CONTRACT.md` (every route, every 409 gate and message), fixture LLM and fixture search, **Sample 1** with its stored answers, `/healthz`, serving `frontend/dist`. | `python tools/contract_check.py http://localhost:8000` passes **with gates on**; `tools/shape_diff.py` reports no missing or mismatched keys for each stage; the app opens in a browser and Sample 1 can be loaded |
| **3** | **Make the real UI work end to end in fixtures mode** (this completes Stage 1): drive Sample 1 through all 12 steps in a real browser (Playwright is acceptable) and compare each step with `reference/screens/step_NN_*.png` and `reference/research_workbench_demo_2.html` (same texts, same states, same diagram boxes lighting). Passcode, History drawer (activity + CSV), export md/json/printable page, import, reset, delete, settings, 401 flow, upload of a csv/xlsx/txt, blank-case flow showing the plain failure and retry when no key is set. Fix whatever is on the **backend** side; never edit `app.js`. | screenshots of every step next to the reference; the list of any differences and their cause |
| **4** | **Live layer** (Stage 2 of the build spec, items 1 to 6): live Anthropic client with JSON-schema validation and versioned prompts in `backend/prompts/`, live Tavily search and page text, pdf parsing, firm-archive keyword search, **privacy sanitiser on every outbound call**, quote check, budgets and caps (`DAILY_SPEND_CAP`, `MAX_LLM_CALLS_PER_CASE`, search credits), passcode, `GET /api/selfcheck` with the exact red-item fixes, **Sample 2 (hospital, unrelated domain) running all 12 steps in fixtures mode with no code change** (`contract_check` must have a `--sample` option or a twin script you add). All tested with mocked clients. **No real LLM or search calls in tests.** | tests passing; the self-check output; Sample 1 and Sample 2 both completing |
| **5** | **Deployment package**: `Dockerfile`, `render.yaml`, `.env.example`, pinned `requirements.txt`, `RUNBOOK.md` (click-by-click), `DEMO.md`, pre-flight (build spec section 17). Start from `deploy/`. The user deploys; you do not. | pre-flight checklist results; the container (or local production server) answering `/healthz` and `/api/session`, and serving `/` |
| **6** | Fixes from the user's live testing. Optional extras (Sample 3, search-refinement loop, Word export) only if the user asks. | final report, build spec section 19 |

Credit discipline, secrets and money rules are in `CLAUDE.md` and build spec section 0: smallest tool that works, write engine tests before UI-facing code, never print or commit keys, never make real LLM or search calls during the build, never deploy.

---

## 7. The guide chrome, live mode and the roadmap button

The overlay in `frontend/dist/walkthrough/` is what draws the top strip and the right-hand diagram. It is **already tested** against the offline replica and the mock. In the live app:

- `walkthrough/config.js` sets `window.RW_CONFIG = {live: true, roadmapUrl: "roadmap.html"}`. In live mode the overlay reads the real case through `GET /api/cases/{id}` (polled by `live-shim.js` and by the app) and `GET /api/cases/{id}/activity`, and lights diagram boxes from real job progress and real API events. Keep `jobs[kind].progress.done/total`, `running_jobs`, `progress.current/done` and the activity rows truthful so the boxes light at the right time. If a box lights wrongly, the fix is in the backend data, not in the overlay.
- The **roadmap button** is a small button at the start of the top-bar buttons, label "Implementation & scalability roadmap" on wide screens and "Roadmap" on narrow ones. It opens `roadmapUrl` in a new tab. The roadmap page itself will be provided later by the user: `frontend/dist/roadmap.html` is a placeholder. **Do not write a roadmap page.** Make sure the server serves `roadmap.html` and any file the user later drops into `frontend/dist/` (do not hard-code a file list). If `roadmapUrl` is empty the button shows a short toast, "The roadmap link will be added here."
- Do not change `rw.js`, `rw.css` or `app.js`. If you believe a change is needed, stop and tell the user why at the next checkpoint.

---

## 8. Verification tools (use them at every checkpoint from 2)

1. **See the product before the backend exists:** `node tools/mock_api_server.js 8765` then open `http://localhost:8765`. It serves `frontend/dist` and answers `/api` from the recordings (Sample 1 only). It is an oracle, not the product; it fakes jobs with timers.
2. **Check your backend against the original:** `python tools/contract_check.py http://localhost:8000 [--passcode CODE]` drives Sample 1 over HTTP through all 12 steps, compares shapes with the recorded bundles and asserts the verdicts and the 409 gates. Run with `--no-gates` only against the mock. The mock passes 67 of 67 checks with `--no-gates`; your server must pass **with gates on**.
3. **Diff one bundle:** `python tools/shape_diff.py recorded.json yours.json` lists missing, extra and mismatched keys. Dynamic maps and free text are already treated as opaque.
4. **Visual check:** screenshots in `reference/screens/`. Compare each step.

---

## 9. Acceptance criteria (report Pass or Fail with evidence)

1. All 12 steps run on Sample 1 in fixtures mode, through the real UI, with the same words and verdicts as Demo 2.
2. Sample 2 runs all 12 steps in fixtures mode with no code change; it shows a different domain on every screen and no Sample 1 text leaks.
3. `contract_check.py` passes with gates on; the 409 messages match `04_API_CONTRACT.md` exactly.
4. Server-side gates: calling a later step's endpoint early is refused with 409 `{reason, required}`; the plan cannot change after lock; a third return trip needs a recorded reason; items from client files and expert notes are never auto-approved.
5. The LLM never decides a verdict, confidence, approval, tier or recommendation (test it: the engine produces them with the LLM mocked to return nonsense for those fields).
6. The privacy sanitiser runs before every outbound LLM or search call; a test shows a client name and a private number are masked.
7. Every summary sentence cites evidence ids and passes the citation check; otherwise the template summary is used.
8. Budget caps stop spending and show the plain notice; the self-check shows every misconfiguration as a red item with the exact fix.
9. A blank case with no key shows the plain failure and a retry (no stack trace, no jargon).
10. Passcode: all `/api` routes except `/session` and `/login` return 401 without the cookie; the UI shows the sign-in screen.
11. Export md and json match the shape of `reference/sample_export.*`; the printable page is the UI's own print view.
12. The top strip, the right-hand diagram and the roadmap button appear and work; no time tile exists; the roadmap button opens `roadmap.html` and does not shift the layout.
13. `/healthz` is fast and calls nothing external; the app binds `0.0.0.0:$PORT`; the database path comes from `DATA_DIR`; memory stays under 512 MB.
14. No secret in git, logs or output. `.env` is ignored. The word "partner" does not appear in the app's own text.
15. **User-run only (needs keys):** a live smoke run on a blank case after deployment.

---

## 10. Final report (at most 25 lines)

What was built; test counts; the acceptance table (Pass/Fail with evidence); anything simulated; defaults you chose; known gaps; the exact steps the user does next (keys, GitHub, Render, self-check, live smoke run, roadmap file).
