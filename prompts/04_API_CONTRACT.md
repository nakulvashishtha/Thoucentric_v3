# 04 · API CONTRACT (what the compiled front end calls)

The compiled front end in `frontend/dist/` is the product UI. It already calls the routes below, expects the response shapes below, and shows the wording below. **Build the backend to this contract.** Three machine-readable sources back it up, and they win over this prose if they ever differ:

1. `reference/recorded_backend_states.json` — 19 full `GET /api/cases/{id}` responses (the "bundle") recorded from the original backend on Sample 1, plus `meta` (samples list, settings, self-check, blank bundles, exports, what-if checks, a sample reply file).
2. `reference/offline_api_replica.js` — a working JavaScript replica of the server's rules (verdict wording, what-if, stress-test retarget, review counts, 409 messages). Port its logic faithfully into the Python engine; keep its wording character for character.
3. `prompts/04_CASE_BUNDLE_SCHEMA.md` — every path in the bundle with its type and an example value.

Then run `tools/contract_check.py` (see master prompt) against your server; it must pass with **gates on**.

## 1. Conventions

- Base path `/api`. JSON in, JSON out. Same origin (no CORS). Cookies are sent (`credentials: same-origin`).
- Success with nothing to return: `200 {"ok": true}`.
- **Every refusal is JSON `{"reason": "<sentence for the consultant>", "required": ["<short item>", ...]}`** with status 400 (bad input), 401 (passcode), 404, or **409 (a gate is not met)**. The UI shows `reason` verbatim, so the sentence is product copy. `required` may be an empty list.
- `401` on any route (when a passcode is configured and the visitor has no valid cookie) makes the UI show the sign-in screen. Wording: `Enter the passcode to continue.`
- Long work (read-ask/frame, plan, route, collect, clean, trips, addup, advance) runs as a **background job**. The POST returns quickly; the browser then polls `GET /api/cases/{id}` once a second **while `running_jobs` is non-empty**. Each job is stored in `bundle.jobs[kind]` as `{id, kind, status ("running"|"done"|"failed"), error, progress{...}, started_at, finished_at}`. A failed job puts a plain-English `error` the UI shows with a retry button. Never block an HTTP request for more than a few seconds.
- A case in a locked step must refuse: `409` with a `reason` such as `Finish "Review the evidence" first`. Gates are enforced server-side, never only in the UI.
- All timestamps are ISO-8601 UTC strings.

## 2. Routes

`{id}` = case id (integer). `{eid}` = evidence id like `E7`. `{ref}` = need reference like `N3`.

### App level
| Method and path | Body | Result |
|---|---|---|
| `GET /session` | none | `{required: bool, signed_in: bool}` (never 401). `required` is true when `ADMIN_PASSCODE` is set. |
| `POST /login` | `{passcode}` | `200 {ok:true}` and an HttpOnly, SameSite=Lax cookie (Secure over https); wrong passcode `401 {reason:"That passcode isn't right. Check it and try again."}` |
| `GET /settings` | none | `{mode, notice, keys{ANTHROPIC_API_KEY,TAVILY_API_KEY,ADMIN_PASSCODE,MODEL_FAST,MODEL_SMART: bool}, app{mode, fast_demo, larger_text, double_check}, spend{case_usd,today_usd,daily_cap_usd,calls,max_calls,search_credits,max_search_credits,reached[],warn[]}, rules_yaml}` (see `meta.settings`). Never return key values. |
| `PUT /settings` | any subset of `app` fields (`mode`, `fast_demo`, `larger_text`, `double_check`) | the settings object. Switching `double_check` while a case is in step 7 writes an activity line (see activity catalogue). |
| `GET /selfcheck` | none | `{items:[{key,label,ok (true/false/null),detail,fix}]}` — checks: database writable, passcode set, mode, `MODEL_FAST` works, `MODEL_SMART` works, search key works, plus any others in the original; each red item carries the exact fix sentence. See `meta.selfcheck` for the exact items and wording. Live checks make one tiny call each. |
| `GET /samples` | none | `[{name,title,description,country,industry}]` — `sample_01_card_launch` and `sample_02_hospital_expansion` (see `meta.samples`). |
| `POST /samples/{name}/load` | none | `{id}` of a new case loaded at step 1 with the sample's files and ask. |
| `GET /samples/{name}/replies/{h}` | none | the sample reply file (binary) the UI offers for download at step 9. |
| `GET /archive` · `POST /archive` (multipart: `file`, `title`, `published_date`) · `DELETE /archive/{id}` | | the firm archive (past work the agent may search); list items `{id,title,filename,published_date}`. |
| `GET /cases` | none | `[{id,title,client_name,sample,mode,current_step,updated_at,status}]` newest first. |
| `POST /cases` | none | `{id}` of a blank new case titled "New case"; activity `case_created` "Started a case". |
| `POST /cases/import` | multipart `file` = JSON export from `export?format=json` | `{id}`; restores a case (free hosting loses data on restart). |

### One case
| Method and path | Body | Behaviour |
|---|---|---|
| `GET /cases/{id}` | | the **bundle** (shape in the schema file). Recomputes `review` counts when in step 7. |
| `PUT /cases/{id}` | any of `client_name, country, industry, function, raw_ask, title, client_aliases, private_numbers, ai_reads_client_files` | saves case fields (`ai_reads_client_files` lives in `case.settings_json`). |
| `DELETE /cases/{id}` | | deletes the case. |
| `POST /cases/{id}/reset` | | sample: reload at step 1; blank: back to empty. Activity `Reset the case to step 1`. |
| `GET /cases/{id}/activity` | `?format=csv` optional | list of `{id,ts,actor,event_type,step,message,case_id}`; CSV columns `id,time,actor,step,event,message`. |
| `GET /cases/{id}/export?format=md|json` | | text download named `<Case_title>.md|.json`; any other format `400 "Choose Markdown, JSON or the printable page."` (the printable page is the UI's own print view). Compare with `reference/sample_export.md` and `.json`. |
| `POST /cases/{id}/files` | multipart `file` + `kind` (`initial`, `trip`...) **or** JSON/form `text` + `kind` + optional `filename` | stores a client file or pasted note (csv, xlsx, txt, pdf); activity `file_uploaded` ("Added the file X", actor `client`). If AI reading is on and the case is blank, extraction runs later in `read-ask`. |
| `PUT /cases/{id}/files/{fid}/figures` | `{figures:[{value:number, unit, locator}, ...]}` (the full list for that file) | consultant-typed figures with a locator, when AI reading is off. |
| `POST /cases/{id}/read-ask` | | **Step 1.** Starts job `frame`: privacy filter → fast model reads files and returns figures with quotes → quote check (verbatim, failures dropped) → smart model frames the ask. Progress `{"label":"Framing the question","done":n,"total":3}`. On a blank case with no key a failure is stored as `jobs.frame.status:"failed"` with a plain `error`. Activity: `read_ask`, `file_read`, `quotes_verified`, `frame_proposed`. |
| `PUT /cases/{id}/frame` | one or more of `client_belief, decision, case_measure_name, case_measure_definition` | edits the question (the UI sends one key on blur); activity "Edited the question". |
| `POST /cases/{id}/frame/confirm` | | **Step 2.** Confirms the frame, starts job `plan` ("Fetching pass-line benchmarks", done/total): drafts 2 to 6 ideas, fetches a benchmark for each, grades the source by fixed rules. Activity `frame_confirmed`, `ideas_drafted`, `benchmark_graded`, `query_checked`. |
| `PUT /cases/{id}/hypotheses` | an array of partial rows `[{code, ...changed fields}]`, e.g. `{code:"H5", removed_reason:"..."}` to remove an idea (a reason is required) | edits ideas before locking (text, pass line, removal with reason). Activity `plan_edited`. |
| `POST /cases/{id}/plan/lock` | `{ticked: true}` | **Step 3 sign-off.** Without `ticked`: `409 "Tick the box to confirm the targets first."` On success locks targets, critical ideas and quality check, starts job `route` ("Writing search queries", done/total). Activity `plan_locked`. |
| `POST /cases/{id}/plan/retarget` | `{kind: "pass_line"|"assumption", key, value}` | **Step 11 stress test** — see section 4. Before step 8 is done: `409 "Run the tests first."` with `required:["Run tests"]`. |
| `POST /cases/{id}/plan/retry` · `POST /cases/{id}/needs/retry` | | re-run a failed `plan` or `route` job. |
| `PUT /cases/{id}/needs/{ref}/query` | `{query}` | consultant edits one search wording; the privacy check runs again. |
| `PUT /cases/{id}/source-plan` | `[{id, included, removed_reason}]` or new rows `{source_name, domain, stated_tier}` | include/remove sources; a consultant-added source is stored with `stated_by_consultant: true`. Activity "Edited the sources". |
| `POST /cases/{id}/requests/mark-sent` | `{reviewed: true}` | **Step 4 sign-off.** Without it: `409 "Tick \"I've checked what goes out\" first."` On success starts the `collect` job, then `clean`, with no further input (steps 5 and 6 are agent-only). Activity `requests_marked_sent` ("…The tool sent nothing itself."), `reviewed_outbound`. |
| `POST /cases/{id}/collect/start` · `POST /cases/{id}/collect/stop` · `POST /cases/{id}/clean/run` | | start or retry gathering; stop finishes with what has arrived and moves on to cleaning; `clean/run` retries a failed clean. |
| `POST /cases/{id}/evidence/{eid}/decision` | `{action, reason, confirm_formula?}` | action ∈ `approve`, `keep_client_reported`, `keep_belief`, `keep_cross_check`, `reject`. See section 3 for the rules and 409 wording. |
| `PUT /cases/{id}/evidence/{eid}/links` | `[{role, hypothesis_code, ...}]` | consultant edits which idea an item supports (`supports_test` / `cross_check`...). |
| `POST /cases/{id}/review/seen/{eid}` | `{send_to_review?: bool}` | marks an auto-passed item as looked at; with `send_to_review` moves it to "Needs your call". |
| `POST /cases/{id}/review/spot-check/{eid}` | `{matches: bool}` or `{skip: true}` | quick double-check result; a "does not match" moves the item to "Needs your call" and appends a failed check "Quick double-check". |
| `POST /cases/{id}/review/confirm-sources` | `{ticked}` | sets/clears `case.settings_json.sources_reviewed_at`. |
| `POST /cases/{id}/test/run` | | **Step 7 sign-off → Step 8.** If not ready: `409 "Finish the review first: <missing items joined by "; ">."` with `required` = the missing list. Runs the rule engine (verdicts and confidence for every idea, in code). |
| `POST /cases/{id}/trips` | `{hypothesis: "H2", override: bool, override_reason: string}` (one call per idea needing a follow-up) | **Step 9.** Starts job `trip_1` ("Drafting a narrower question"); returns `{trip_id}`. Free limit 2 trips, a third needs a recorded reason (config `trips.free`, `max_with_override`). |
| `PUT /cases/{id}/trips/{tid}` | `{question}` | consultant edits the follow-up question. |
| `POST /cases/{id}/trips/{tid}/mark-sent` | | records `marked_sent_at`; the tool sends nothing. Activity "Marked request N for Hx as sent. The tool sent nothing itself." |
| `POST /cases/{id}/trips/{tid}/reply` | multipart `file` (a pasted reply arrives as `POST /cases/{id}/files` with fields `kind` and `text`) | starts job `trip_reply_{tid}` ("Linking and checking the reply"): extract, quote-check, link to ideas, run the checklist. New items have `trip_id` set. |
| `POST /cases/{id}/trips/{tid}/sample-mix` | `{sample:{dimension:number,...}, target:{dimension:number,...}}` or `{not_applicable:true}` | records whether the reply's sample mix matches (max 10 percentage-point difference). |
| `POST /cases/{id}/retest` | `{hypothesis: "H2"}` (one call per idea) | re-runs the verdicts after a trip. With undecided new items: `409 "Make a call on the new evidence first: E28, E29."` and `required` = those ids. |
| `POST /cases/{id}/addup/run` | | **Step 10.** Starts job `addup` ("Listing what is still unknown", then "Writing the summary"): applies the locked adding-up rule in code, then the smart model writes a summary where **every sentence cites evidence ids** and passes a citation check; if that fails, a plain template summary is built from the verdicts (`summary.source:"template"` vs `"llm"`). |
| `GET /cases/{id}/unknowns` | | `summary.unknowns` list. |
| `POST /cases/{id}/whatif` | `{assumptions:{name:value}, pass_lines:{code:value}}` | **Step 11.** Pure recalculation, nothing saved. Response in section 4. |
| `PUT /cases/{id}/conclusion` | `{text}` | **Step 12.** Empty text: `400 "Write your conclusion in the box first."` Saves `{case_id,text,saved_at}`, marks step 12 done. Activity "Saved your conclusion". |
| `POST /cases/{id}/sample/advance?to=N` | | sample cases only: replay the recorded answers through the normal endpoints up to step N (job kind `advance`); activity `Skipped ahead to step N using the sample's recorded answers (sample data)`. |
| `POST /cases/{id}/use-demo-data` · `POST /cases/{id}/fresh-answers` | | switch a case between recorded answers and live answers (used by the mode switch). |
| `GET /cases/{id}/jobs/{jid}` | | one job. |

## 3. Step gating, review rules and evidence decisions

**Steps and states** (`progress.steps[n]`): `{n,title,phase,signoff,state,locked_reason,current}` with `state` ∈ `done | open | locked`. Titles and phases are fixed:

| n | title | phase | signoff |
|---|---|---|---|
| 1 | Describe the ask | 0 | yes |
| 2 | Confirm the question | 0 | yes |
| 3 | Set the targets | 0 | yes |
| 4 | Plan the research | 1 | yes |
| 5 | Gathering evidence | 1 | no |
| 6 | Checking the evidence | 1 | no |
| 7 | Review the evidence | 1 | yes |
| 8 | Results | 2 | no |
| 9 | Fill the gaps | 2 | yes |
| 10 | The answer | 2 | no |
| 11 | What if... | 2 | no |
| 12 | Your conclusion | 2 | yes |

`locked_reason` examples: `Finish "Review the evidence" first`, `Finish "Results" first`, `Finish "The answer" first`. `progress.current` is the step the consultant should do next; `progress.done` is a map `{"1":true,...}`; `progress.reopened` lists steps reopened by a stress test.

**Evidence buckets (step 7):** `auto` (passed every check; the consultant must still look at its source), `decision` (needs the consultant's call), `reference`, `duplicate`, `pending` (asked of the client or an expert, not yet received). Items from `client_file` and `expert_note` are never auto-approved. Status codes and labels: `auto_approved` "Passed the quality check" · `approved` "Accepted by you" · `needs_decision` "Needs your call" · `client_reported` "From the client" · `belief_under_test` "Client's claim" · `cross_check` "Sense check only" · `rejected` "Rejected".

**Decision action → status:** approve→approved · keep_client_reported→client_reported · keep_belief→belief_under_test · keep_cross_check→cross_check (links with role `supports_test` become `cross_check`) · reject→rejected. Records `decided_by:"consultant"`, `decision_reason`, `seen_by_consultant:true`.

**Calculated figures:** when the item contains a `calculated` figure whose derivation is not `formula_confirmed`, approving it (action approve or keep_client_reported) marks the formula as confirmed ("(formula checked)"). If `formula_needs_you` is true (the calculation combines figures from different sources or uses an assumption) and `confirm_formula` is not sent, refuse: `409 Use "Accept and confirm formula" for E7: its calculation combines figures from different sources or uses an assumption.` With `confirm_formula` the note is "(formula confirmed by you)".

**Review counts** (`bundle.review`, step 7, recomputed on every GET) — only items without `trip_id`:
`auto_total, auto_seen, decision_total, decided (decision items whose status is no longer needs_decision), spot_total, spot_done, sources_box (sources_reviewed_at set), double_check (app setting, default true)`, plus `missing[]` and `ready`:
- `Decide {n} more item(s)` — "item" plural when n ≠ 1
- `Look at {n} more source(s)`
- `Tick "I've checked these sources"`
`ready` is true when `missing` is empty. `test/run` returns the 409 above when not ready.

## 4. What-if and the stress test (the engine's verdict rules)

`POST /whatif` and `plan/retarget` use the same verdict function. **Port `verdictOf`, `classify`, `fmt`, `withUnit`, `figText`, `join`, `evalFormula`, `whatIf` and `retarget` from `reference/offline_api_replica.js` exactly** (they reproduce the original server's numbers and sentences; `meta.whatif_checks` lists expected results to unit-test against).

**Response of `/whatif`:** `{ideas:[{code,text,must_have,unit,comparator,line,locked_line,result,confidence,why,evidence_ids,changed}], overall, overall_label, rule_applied, overall_changed, locked_plan_unchanged:true}`.
- `result` ∈ `holds | fails | conflicting | not_enough` → display words **Supported / Not supported / Sources disagree / Not enough evidence**.
- `confidence` ∈ `high | medium | low | none` → **Strong / Fair / Weak**.
- `overall` ∈ `achievable | consultant_decides | not_achievable` → **Achievable / Needs your decision / Not achievable**.
- Adding-up rule text: *If any must-have idea fails: not achievable at the agreed pass line. Else if any must-have idea is conflicting or has not enough evidence: the consultant decides. Else: achievable.* The sentence for each outcome is in `whatIf()`.

**`/plan/retarget`** (stress test made real): validates (`That slider isn't available. Refresh the page and try again.` / `Keep the value inside the slider's range.` / `Move the slider first. This value is already your target.`), reopens the plan at step 3 (activity lines in `retarget()`), changes the target, locks again keeping reviewed evidence, recomputes every verdict in code (`version+1`), clears steps 10 to 12, starts a fresh `addup` job (`progress.current` back to 8). Slider ranges: `sliderRange()`.

## 5. Where the sample numbers come from

Sample 1 must give, in fixtures mode and in the recorded bundle: H1 Not supported / Strong; H2 Not enough evidence at first, then Supported / Fair after the follow-up trip; H3 Supported / Fair; H4 Supported / Weak; overall **Not achievable**. `tools/contract_check.py` asserts this.

## 6. Job kinds and their progress labels (shown on screen)

| kind | label(s) | progress shape |
|---|---|---|
| `frame` | Framing the question | `{label, done, total}` (3) |
| `plan` | Fetching pass-line benchmarks | `{label, done, total}` |
| `route` | Writing search queries | `{label, done, total}` |
| `collect` | Collecting → Finished | `{label, groups:{open_web, firm_archive, paid_db, client_file, expert_note: {label, done, total, state}}, pending:[{id,need,text,from}]}`; group `state` ∈ `waiting | searching | receiving | done`; group labels: "Open web", "Firm archive", "Paid or simulated databases", "Client files", "Expert notes" |
| `clean` | Reading sources → Running the checklist | `{label, done, total, stage: "read"|"checklist"}` |
| `trip_N` | Drafting a narrower question | `{label}` |
| `trip_reply_N` | Linking and checking the reply | `{label}` |
| `addup` | Listing what is still unknown → Writing the summary | `{label}` |
| `advance` | (sample skip-ahead) | |

## 7. Activity catalogue (the History drawer)

Every state change writes one activity row: `{event_type, actor, step, message}`. Actors: `consultant`, `client`, `llm`, `rule_engine`, `system`. The table lists every event type seen on the original backend with an example message from Sample 1; keep the sentence patterns. (Rows written by the offline replica use `event_type:"preview"`; the real backend must use the proper types.)

| event_type | actor | step | Example message (Sample 1) |
|---|---|---|---|
| `case_created` | `consultant` | 1 | Started a case from a sample |
| `file_read` | `llm` | 1 | Read board_note.txt and found 1 figures |
| `file_uploaded` | `client` | 1 | Added the file board_note.txt |
| `quotes_verified` | `rule_engine` | 1 | Found 1 of 1 figures word for word in board_note.txt |
| `read_ask` | `consultant` | 1 | Asked for the ask to be checked |
| `sample_loaded` | `system` | 1 | Loaded a sample case. Its data is simulated. |
| `frame_confirmed` | `consultant` | 2 | Confirmed the question. The client's belief is now a claim to test, not a fact. |
| `frame_proposed` | `llm` | 2 | Drafted the question: what the client believes, the decision they face, and how to compare numbers |
| `benchmark_graded` | `rule_engine` | 3 | Found a benchmark for the H1 target. Source quality: Trusted; date: 2025-12 (10 months old) |
| `ideas_drafted` | `llm` | 3 | Drafted 5 ideas to test, each with a target |
| `plan_edited` | `consultant` | 3 | Edited the ideas: removed H5 (History of credit cards in India would not change the decision) |
| `plan_locked` | `consultant` | 3 | Locked the targets for 4 ideas. Targets, critical ideas and the quality check can no longer change. |
| `query_checked` | `rule_engine` | 3 | Checked the benchmark search for H1. It contains no private terms. |
| `locators_checked` | `rule_engine` | 4 | Checked that every cited place in the client's files exists |
| `needs_routed` | `llm` | 4 | Listed 9 things to find out and checked which ones the client's files already answer |
| `outbound_sanitised` | `rule_engine` | 4 | Removed the client's name and private numbers from every search and request |
| `requests_marked_sent` | `consultant` | 4 | Marked the client request and expert questions as sent. The tool sent nothing itself. |
| `reviewed_outbound` | `consultant` | 4 | Checked the answers, the sources and what goes out |
| `client_files_used` | `client` | 5 | Added the 3 client files you already had as evidence |
| `collect_finished` | `system` | 5 | Finished collecting. Checking the evidence now. |
| `collect_started` | `rule_engine` | 5 | Started collecting evidence from the chosen sources |
| `expert_notes_received` | `expert` | 5 | Received 2 expert notes (sample data, simulated) |
| `group_collected` | `rule_engine` | 5 | Open web: collected 9 items |
| `pending` | `rule_engine` | 5 | Still waiting for E28 from the client: Sign-up cost per active card and monthly margin per active card from the client's pilot. |
| `checklist_run` | `rule_engine` | 6 | Ran the quality check: 6 passed, 10 need your call |
| `copies_found` | `rule_engine` | 6 | Found 4 exact copies before reading, so they weren't read twice |
| `deduplicated` | `rule_engine` | 6 | Traced 5 copies to their original source. Each original counts once. |
| `derived` | `rule_engine` | 6 | Worked out 1 figure(s) for E7: (10.8 ÷ 5.53)^(1/5) − 1 = 14.3%. It's checked when you accept the item. |
| `sources_read` | `llm` | 6 | Read 21 sources and pulled out each figure with its quote |
| `spot_check_picked` | `rule_engine` | 6 | Picked 1 of the 6 items that passed for an optional quick double-check: E14 (seed 2) |
| `decision` | `consultant` | 7 | Kept as a sense check only: E7 |
| `run_tests` | `consultant` | 7 | Ran the tests. Links between evidence and ideas are now locked. |
| `seen` | `consultant` | 7 | Looked at the source of E14 |
| `sources_reviewed` | `consultant` | 7 | Confirmed the sources have been checked |
| `spot_check` | `consultant` | 7 | Double-checked E14: it matches its source |
| `verdict` | `rule_engine` | 8 | H1: Not supported, confidence Strong. 12 to 18% a year and 13.8% a year miss the target of at least 20% a year by more than the close-call margin, and 2 separate sources  |
| `followup_checked` | `rule_engine` | 9 | Checked the follow-up question for private numbers |
| `followup_drafted` | `llm` | 9 | Drafted a follow-up question for H2 |
| `sample_mix` | `rule_engine` | 9 | Compared the reply's sample with the target group: the mix matches |
| `test_again` | `consultant` | 9 | Tested H2 again with the new evidence |
| `trip_links_reopened` | `rule_engine` | 9 | Reopened H2 for the reply. Everything else stays locked. |
| `trip_reply` | `client` | 9 | The client's reply arrived as E29 (pilot_costs.xlsx) |
| `trip_sent` | `consultant` | 9 | Marked request 1 for H2 as sent. The tool sent nothing itself. |
| `added_up` | `rule_engine` | 10 | Added up the results using the locked rule: Not achievable. Critical idea H1 is not supported by the evidence gathered so far, so the case does not hold at the agreed thr |
| `addup_requested` | `consultant` | 10 | Asked for the answer to be added up |
| `summary_written` | `llm` | 10 | Drafted the summary. Every sentence cites its evidence and passed the checks. |
| `unknowns_listed` | `llm` | 11 | Listed 3 things that are still unknown |
