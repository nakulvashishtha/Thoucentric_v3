# Research Workbench: project instructions for Claude Code

## What this project is
A live, domain-agnostic research agent for consultants. **The front end is already built and approved** (`frontend/dist/`, compiled, frozen). You build the **backend** that makes it live, serve the front end, and prepare the deployment. The full instruction is **`prompts/00_MASTER_BUILD_PROMPT.md`**. Read it completely at the start of every session, then follow its reading order.

**The output must stay exactly the same as the approved demo** (`reference/research_workbench_demo_2.html`): same screens, same wording, same 12 steps. Never edit `frontend/dist/assets/*` or `frontend/dist/walkthrough/*`. Never add a time-saved tile. Never reword a sentence the backend returns for a case that is recorded in `reference/recorded_backend_states.json`.

**Precedence when documents disagree:** recorded states and compiled front end → `prompts/04_API_CONTRACT.md` + `reference/offline_api_replica.js` → Demo 2 and `reference/screens/` → `prompts/01_BACKEND_BUILD_SPEC.md` → `prompts/02_UI_LANGUAGE_SPEC.md`, `03_COST_PLAN.md` → `design/`. (Section 12 of the build spec, the front end, is superseded.) The approval protocol, resume protocol and secrets rules below add to all of them.

## Approval protocol (the user wants to review and stop you at each step)
- Build in the six checkpoints defined in section 6 of the master prompt (1 engine · 2 backend and API · 3 real UI end to end in fixtures mode · 4 live layer · 5 deployment package · 6 fixes).
- After each of checkpoints 1 to 5: commit with the message `Checkpoint N: <summary>`, then **STOP**. Report in at most 15 lines: what was built, test results, the exact commands to run and view it locally, anything simulated, any default you chose. Then wait.
- Continue only when the user types **approve**. If they give feedback, fix it, re-report and wait again. After approval, create the git tag `checkpoint-N-approved` and update `PROGRESS.md`.
- Never start the next checkpoint on your own, never skip a checkpoint, never batch two.

## Resume protocol (saves credits)
- Keep **`PROGRESS.md`** (at most 30 lines): current checkpoint, status of each, decisions made, known issues, commands to run the app and the tests. Update it at every checkpoint.
- At the start of a new session, read this file, `PROGRESS.md` and `prompts/00_MASTER_BUILD_PROMPT.md`, then continue from the last approved checkpoint. Re-read the other prompt files only when you need a section. Do not re-read the whole repository.
- After the user approves a checkpoint, tell them they can run `/clear` to start the next one with a fresh, cheaper context.

## Secrets and money
- Never print, log, commit or ask for API keys. Keys live in a git-ignored `.env`. You may check which variable names are present, never their values.
- Checkpoints 1 to 3 need no keys. Never make real LLM or search calls during the build or in tests; use fixtures and mocked clients.
- Do not deploy anything. Checkpoint 5 only prepares the deployment package; the user deploys.
- Follow the cost controls in section 14 of `prompts/01_BACKEND_BUILD_SPEC.md` and `prompts/03_COST_PLAN.md`.

## Working rules
- Write engine code and its unit tests before anything that depends on it. Run tests after each module.
- Check yourself with `tools/contract_check.py` and `tools/shape_diff.py` from checkpoint 2 on (usage in the master prompt, section 8).
- Use the smallest tool that works. Do not add libraries, features or documentation the prompts do not ask for.
- Fix root causes. If the same error persists after 3 attempts, stop, record it in `PROGRESS.md` and tell the user.
- Keep the app generic: no client, sector, country or number hard-coded outside `backend/samples/`, `backend/fixtures/` and `design/`. The word "partner" must not appear in the app's own text.
- The roadmap page is supplied later by the user. Do not write one. Serve whatever is in `frontend/dist/`.
- Initialise git on the first step. Keep `.env` in `.gitignore`; `frontend/dist/` is committed.
