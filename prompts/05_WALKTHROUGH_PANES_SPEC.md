# 05 · WALKTHROUGH PANES SPEC (the guide chrome around the app)

The product has two layers:

1. **The app** — the compiled React app in `frontend/dist/assets/app.js` + `app.css`. It is the real tool. Do not modify it.
2. **The guide chrome** — a thin overlay in `frontend/dist/walkthrough/` (`rw.js`, `rw.css`, `config.js`, `live-shim.js`). It draws, around the app, the two things the user liked in "Demo 2": the **journey strip on top** (12 steps, agent band, orange "you" pins) and the **diagram pane on the right** ("Behind step N of 12"). It reads the real case (`window.__rwPreview.liveCase()` in the demo; in live mode via `live-shim.js`, which polls `GET /api/cases/{id}` and `/activity`) and lights each box from real signals. It is already written and tested; you do not rebuild it. This file documents what it shows so you can (a) keep the backend honest to it and (b) change it safely if asked.

## How the overlay knows what is happening

- The case bundle: `progress.current`, `progress.done`, `running_jobs`, `jobs[kind].progress.done/total`.
- API calls: the app's fetch wrapper dispatches a `rw-api` CustomEvent `{method, path, status}` after every call (status 200 only is used). A box with `seg: "s:<name>"` lights for about one second when the matching call returns.
- `seg` values: `pre` already done before this step; `you`, `you1`, `you2` the consultant's gate (lit while the step is open and waiting); `j:<job>` lit while that background job runs (boxes with a higher `o` light later, using `jobs[kind].progress.done/total`); `s:<name>` lit for about 1 s on the matching API call; `out` the end box, done when every box above it is done.
- In live mode the Restart button reads "Home", the recap button reads "Back to home", the sample is not auto-started, and the intro dialog shows once per browser session (`sessionStorage["rw-guide-seen"]`). Jumping to a locked step is allowed only on sample cases.

## The roadmap button (top bar)

A small button at the start of the top-bar button group (`#tp-road`), label "Implementation & scalability roadmap" on wide screens (≥1620px) and "Roadmap" on narrower ones, with a small arrow icon. It must not change the layout. It opens `window.RW_CONFIG.roadmapUrl` (`frontend/dist/walkthrough/config.js`, default `roadmap.html`) in a new tab with `noopener`. **If `roadmapUrl` is empty it shows the toast "The roadmap link will be added here."** The roadmap HTML will be supplied later by the user: replace `frontend/dist/roadmap.html` (or point `roadmapUrl` at its URL). Never remove the button; never block the UI on it.

## Journey strip and diagrams (exact content)

## A. The twelve steps of the top strip

| # | Step title (strip) | Agent band text | Your pin text | Pin kind |
|---|---|---|---|---|
| 1 | The ask | Reads files | Paste the ask | filled orange pin: you decide |
| 2 | Question | Drafts ideas | Confirm | filled orange pin: you decide |
| 3 | Targets | Plans research | Lock targets | filled orange pin: you decide |
| 4 | Plan | Writes searches | Check outgoing | filled orange pin: you decide |
| 5 | Gathering | Searches sources | (none) | small dash: nobody needed |
| 6 | Checking | Verifies all | (none) | small dash: nobody needed |
| 7 | Review | Flags doubts | Decide flags | filled orange pin: you decide |
| 8 | Results | Tests ideas | Read | ring with eye icon: you read |
| 9 | Fill gaps | Drafts follow-up | Send, reply | dashed ring: optional |
| 10 | Answer | Writes it up | Read | ring with eye icon: you read |
| 11 | What if | Recalculates | Try sliders | dashed ring: optional |
| 12 | Conclusion | Builds exports | Write yours | filled orange pin: you decide |

Phase labels above the strip: "Frame the question" (steps 1 to 4), "Build the evidence" (steps 5 to 7), "Test and conclude" (steps 8 to 12).

Right-hand pane headings, one per step ("Behind step N of 12" + title): 1 Define the ask; 2 Confirm the question; 3 Set the targets; 4 Plan the research; 5 Gather the evidence; 6 Check the evidence; 7 Review the evidence; 8 Read the results; 9 Fill the gaps; 10 The answer; 11 What if; 12 Your conclusion.

## B. The diagram for every step

Grid: 3 columns (c=0,1,2) and rows (r=0...). `seg` tells which real signal lights the box: `pre` = already done before this step; `you`/`you1`/`you2` = your gate; `j:<job>` = lit while that background job runs (boxes with a higher `o` light later); `s:<name>` = lit for about 1 s when the matching API call returns; `out` = the end box, done when every box above it is done. Box text in the right column is the one-sentence caption shown when the box is active or hovered.

### Step 1: Define the ask

Idle caption under the diagram: Check the ask, then click **Check the ask**.

| id | kind | label | col,row | seg | order | caption (one sentence) |
|---|---|---|---|---|---|---|
| you | You (orange) | Paste the ask | 0,0 | you | 0 | You paste the client's ask, add their files and list private numbers. |
| files | Data in (teal) | Client files | 2,0 | pre | 0 | Files the client already sent. |
| priv | Plain code (blue) | Privacy filter | 1,1 | j:frame | 0 | Client names and private numbers are masked before anything leaves the firm. |
| ai1 | AI model (purple) | AI reads files | 1,2 | j:frame | 1 | A fast AI model pulls out each figure with the sentence it came from. |
| qc | Plain code (blue) | Quote check | 1,3 | j:frame | 2 | Code checks every quote, word for word. Anything that fails is dropped. |
| ai2 | AI model (purple) | AI frames the ask | 1,4 | j:frame | 3 | A smarter AI model splits the ask into a belief to test and a decision. |
| out | Result/output | Draft question | 1,5 | out | 0 |  |

Arrows: you → priv; files → priv; priv → ai1; ai1 → qc; qc → ai2; ai2 → out.

### Step 2: Confirm the question

Idle caption under the diagram: Read the question, then click **Confirm question**.

| id | kind | label | col,row | seg | order | caption (one sentence) |
|---|---|---|---|---|---|---|
| you | You (orange) | Check wording | 0,0 | you | 0 | You check the question. The client's belief is a claim to test, not a fact. |
| q | Result/output | Question | 2,0 | pre | 0 | The question the AI drafted from your ask. |
| ai | AI model (purple) | AI drafts ideas | 1,1 | j:plan | 0 | A smart AI model writes 2 to 6 testable ideas, each with a target. |
| web | Data in (teal) | Web search | 2,2 | j:plan | 1 | The AI writes a search for each target. The web returns a benchmark. |
| rate | Plain code (blue) | Rate sources | 1,3 | j:plan | 2 | Fixed rules grade each source's quality and date. The AI does not. |
| out | Result/output | Ideas + targets | 1,4 | out | 0 |  |

Arrows: you → ai; q → ai; ai → web (label "search"); web → rate (label "benchmark"); rate → out.

### Step 3: Set the targets

Idle caption under the diagram: Mark the critical ideas, then click **Lock targets**.

| id | kind | label | col,row | seg | order | caption (one sentence) |
|---|---|---|---|---|---|---|
| you | You (orange) | Set pass lines | 0,0 | you | 0 | You mark the critical ideas, drop weak ones and lock the targets. |
| ideas | Result/output | Ideas + targets | 2,0 | pre | 0 | Each idea has a target and the source it came from. |
| lock | Locked (navy) | Lock targets | 1,1 | j:route | 0 | Targets and the quality check freeze. Nothing can change them later. |
| ai | AI model (purple) | AI plans research | 1,2 | j:route | 1 | A fast AI model decides where each answer comes from and writes the searches. |
| files | Data in (teal) | Client files | 2,2 | j:route | 1 | Needs the client has already answered are skipped. |
| clean | Plain code (blue) | Remove private terms | 1,3 | j:route | 2 | Every search and request is cleaned of private terms. |
| out | Result/output | Locked plan | 1,4 | out | 0 |  |

Arrows: you → lock; ideas → lock; lock → ai; files → ai; ai → clean; clean → out.

### Step 4: Plan the research

Idle caption under the diagram: Check what goes out, then click **Mark as sent**.

| id | kind | label | col,row | seg | order | caption (one sentence) |
|---|---|---|---|---|---|---|
| plan | Result/output | Searches + requests | 1,0 | pre | 0 | Searches and requests, already cleaned of private terms. |
| you | You (orange) | Check what goes out | 1,1 | you | 0 | You read every request and untick any source you don't trust. |
| ext | Outside the tool (grey, dashed) | Client + experts | 2,2 | pre | 0 | You send the requests yourself, outside this tool. |
| mark | Plain code (blue) | Mark as sent | 1,2 | s:mark | 0 | Only records your click. The tool sends nothing. |
| out | Result/output | Collection starts | 1,3 | out | 0 |  |

Arrows: plan → you; you → mark; you → ext (label "you send") (dashed); mark → out.

### Step 5: Gather the evidence

Idle caption under the diagram: Nothing to do here. The agent is collecting.

| id | kind | label | col,row | seg | order | caption (one sentence) |
|---|---|---|---|---|---|---|
| sent | You (orange) | You marked sent | 1,0 | pre | 0 | You marked the requests as sent. Collection started by itself. |
| web | Data in (teal) | Web | 0,1 | j:collect | 0 | Only the sources you left ticked. |
| arc | Data in (teal) | Firm archive | 1,1 | j:collect | 0 | Past studies, searched in-house. Nothing leaves the firm. |
| cli | Data in (teal) | Client files | 2,1 | j:collect | 0 | Figures the client already supplied. |
| col | Plain code (blue) | Collect + file | 1,2 | j:collect | 1 | Capped and cached. Each item keeps where it came from. |
| out | Result/output | (dynamic, see below) | 1,3 | out | 0 |  |

Arrows: sent → web; sent → arc; sent → cli; web → col; arc → col; cli → col; col → out.

### Step 6: Check the evidence

Idle caption under the diagram: Nothing to do here. The agent is checking everything.

| id | kind | label | col,row | seg | order | caption (one sentence) |
|---|---|---|---|---|---|---|
| items | Data in (teal) | Collected items | 1,0 | pre | 0 | Everything gathered from the web, the archive and client files. |
| merge | Plain code (blue) | Merge copies | 1,1 | j:clean | 0 | Exact copies are skipped. A copy of one study counts once. |
| ai | AI model (purple) | AI reads sources | 1,2 | j:clean | 1 | A fast AI model pulls out each figure with its quote. |
| qc | Plain code (blue) | Quote check | 1,3 | j:clean | 2 | Every quoted figure must appear word for word in its source. |
| rate | Plain code (blue) | Rate source | 0,4 | j:clean | 3 | Official, Trusted, Press or Unverified, by fixed rules. |
| chk | Plain code (blue) | 9-test check | 2,4 | j:clean | 3 | Items that pass every test are approved without you. |
| out | Result/output | (dynamic, see below) | 1,5 | out | 0 |  |

Arrows: items → merge; merge → ai; ai → qc; qc → rate; qc → chk; rate → out; chk → out.

### Step 7: Review the evidence

Idle caption under the diagram: Decide the flagged items, then click **Run tests**.

| id | kind | label | col,row | seg | order | caption (one sentence) |
|---|---|---|---|---|---|---|
| pre | Result/output | (dynamic, see below) | 1,0 | pre | 0 | The agent approved what passed and flagged the rest for you. |
| you | You (orange) | Decide flagged | 0,1 | you | 0 | You accept, reject or keep each flagged item. One click each. |
| spot | You (orange) | Spot check | 2,1 | you | 0 | Optional. Compare one passed item with its source. |
| lock | Locked (navy) | Locked targets | 2,2 | pre | 0 | The targets you locked at step 3. |
| tests | Plain code (blue) | Run tests | 1,2 | s:tests | 0 | Each idea is compared with its locked target. Same evidence, same result. |
| out | Result/output | Results | 1,3 | out | 0 |  |

Arrows: pre → you; pre → spot (dashed); you → tests; spot → tests (dashed); lock → tests; tests → out.

### Step 8: Read the results

Idle caption under the diagram: Read each result. Then **Fill the gaps** or **Add it up**.

| id | kind | label | col,row | seg | order | caption (one sentence) |
|---|---|---|---|---|---|---|
| ev | Data in (teal) | Evidence | 0,0 | pre | 0 | The evidence you approved. |
| lock | Locked (navy) | Locked targets | 2,0 | pre | 0 | The targets set before any evidence was read. |
| rules | Plain code (blue) | Verdict rules | 1,1 | pre | 0 | Holds, Fails, Sources disagree or Not enough evidence, by fixed rules. |
| conf | Plain code (blue) | Confidence | 1,2 | pre | 0 | Strong, Fair or Weak, by how many separate sources agree. A market fact needs two. |
| you | You (orange) | Read results | 1,3 | you | 0 | You read each result and open the reasoning behind it. |
| gaps | You (orange) | Fill the gaps | 0,4 | you | 0 | Optional. One narrow follow-up where evidence is thin. |
| add | You (orange) | Add it up | 2,4 | you | 0 | Go straight to the answer. |

Arrows: ev → rules; lock → rules; rules → conf; conf → you; you → gaps; you → add.
Optional boxes (badge "Optional"): you, gaps, add.

### Step 9: Fill the gaps

Idle caption under the diagram: Draft a follow-up, send it yourself, add the reply.

| id | kind | label | col,row | seg | order | caption (one sentence) |
|---|---|---|---|---|---|---|
| gap | Result/output | (dynamic, see below) | 2,0 | pre | 0 | This idea has too little evidence to call. |
| you1 | You (orange) | Ask follow-up | 0,0 | you1 | 0 | You click Draft question for the idea that needs more. |
| ai1 | AI model (purple) | AI drafts question | 1,1 | j:trip_1 | 0 | A smart AI model drafts one narrow question, checked for private numbers. |
| you2 | You (orange) | You send it | 1,2 | you2 | 0 | You send it yourself, outside the tool, then add the reply here. |
| cl | Outside the tool (grey, dashed) | Client | 2,2 | pre | 0 | The client answers with a file or a note. |
| ai2 | AI model (purple) | AI reads reply | 1,3 | j:trip_reply_1 | 0 | A fast AI model pulls out the figures with their quotes. |
| chk | Plain code (blue) | Quote + sample check | 1,4 | j:trip_reply_1 | 1 | Quotes matched, and the sample compared with the target group. |
| re | Plain code (blue) | Re-test one idea | 1,5 | s:retest | 0 | Only that idea reopens. Everything else stays locked. |
| out | Result/output | Updated result | 1,6 | out | 0 |  |

Arrows: gap → ai1; you1 → ai1; ai1 → you2; you2 → cl (dashed); cl → ai2 (label "reply"); ai2 → chk; chk → re; re → out.
Optional boxes (badge "Optional"): you1.

### Step 10: The answer

Idle caption under the diagram: Read the answer, then try the **Stress-test**.

| id | kind | label | col,row | seg | order | caption (one sentence) |
|---|---|---|---|---|---|---|
| res | Result/output | Results | 0,0 | pre | 0 | The result for every idea. |
| rule | Locked (navy) | Locked rule | 2,0 | pre | 0 | The rule set at step 3. A failed critical idea means Not achievable. |
| apply | Plain code (blue) | Apply the rule | 1,1 | j:addup | 0 | Code applies the locked rule. The AI doesn't decide the answer. |
| ev | Data in (teal) | Evidence | 0,2 | j:addup | 1 | Every sentence must cite the evidence behind it. |
| ai | AI model (purple) | AI writes summary | 1,2 | j:addup | 1 | A smart AI model writes 3 to 5 sentences. |
| chk | Plain code (blue) | Check each line | 1,3 | j:addup | 2 | A missing citation or a number not in the data? The line is thrown out. |
| unk | AI model (purple) | AI lists unknowns | 2,3 | j:addup | 2 | A fast AI model lists what is still unknown. |
| you | You (orange) | Read answer | 1,4 | you | 0 | You read the answer and open any evidence behind it. |
| out | Result/output | (dynamic, see below) | 1,5 | out | 0 |  |

Arrows: res → apply; rule → apply; apply → ai; ev → ai; ai → chk; ai → unk; chk → you; unk → you; you → out.
Optional boxes (badge "Optional"): you.

### Step 11: What if

Idle caption under the diagram: Move a slider and watch the answer change.

| id | kind | label | col,row | seg | order | caption (one sentence) |
|---|---|---|---|---|---|---|
| you | You (orange) | Move a slider | 0,0 | you | 0 | You change a target or an assumption to see what happens. |
| lock | Locked (navy) | Locked plan | 2,0 | pre | 0 | Your locked plan does not change while you explore. |
| calc | Plain code (blue) | Recalculate | 1,1 | s:whatif | 0 | Every idea and the answer update at once. Nothing is saved. |
| live | Result/output | Live answer | 1,2 | s:whatif | 0 | The answer under the value you picked. |
| you2 | You (orange) | Make it real | 0,3 | you | 0 | Optional. You confirm, and the new value becomes the target. |
| re | Plain code (blue) | Reopen + retest | 1,4 | s:retarget | 0 | Evidence and your decisions are kept. The change is logged. |

Arrows: you → calc; lock → calc (label "unchanged") (dashed); calc → live; live → you2; you2 → re.
Optional boxes (badge "Optional"): you, you2.

### Step 12: Your conclusion

Idle caption under the diagram: Write your conclusion. The agent never writes this part.

| id | kind | label | col,row | seg | order | caption (one sentence) |
|---|---|---|---|---|---|---|
| you | You (orange) | Write conclusion | 1,0 | you | 0 | You write the conclusion in your own words. |
| save | Plain code (blue) | Save as written | 1,1 | s:save | 0 | Saved exactly as you wrote it. The agent adds nothing. |
| log | Data in (teal) | Action log | 2,1 | s:save | 0 | Every action by the AI, the code and you is recorded. |
| exp | Plain code (blue) | Build exports | 1,2 | s:save | 1 | Print, Markdown and JSON are built from the saved case. |
| out | Result/output | Exports ready | 1,3 | out | 0 |  |

Arrows: you → save; save → exp; save → log; exp → out.

