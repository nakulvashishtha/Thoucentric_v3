# Research Workbench: build pack for Claude Code

This folder is everything Claude Code needs to build the **live, deployable prototype** of Research Workbench, with the output exactly as in the approved demo (Demo 2).

**To start:** open `HOW_TO_START.md`.

## What is inside
- `prompts/00_MASTER_BUILD_PROMPT.md`: the master instruction (Claude Code reads this first).
- `prompts/01` to `05`: the backend specification, language rules, cost plan, API contract, case schema and the guide-pane spec.
- `frontend/dist/`: the approved, compiled product screens plus the guide chrome (top journey strip and right-hand "Behind step N" diagram) and the small Roadmap button. Claude Code serves this and does not change it.
- `reference/`: the approved demo, the 19 recorded case states, a replica of the original server's rules, sample exports and screenshots of every step.
- `tools/`: a stand-in server to preview the product (`node tools/mock_api_server.js`), and two checkers Claude Code uses to prove its backend matches.
- `design/`, `deploy/`, `CLAUDE.md`, `.env.example`, `.gitignore`.

## Three things to know
1. **Same output as Demo 2.** The screens and wording are fixed. Claude Code builds only the backend, the live AI and search layer, and the deployment.
2. **You approve every checkpoint.** It stops after each one and waits for you to type `approve`.
3. **Roadmap button.** It opens `frontend/dist/roadmap.html` (a placeholder). Drop your real roadmap page in under the same name when you have it.
