/* Research Workbench walkthrough, version 2.
   Top: the whole journey as a swimlane (agent band, your pins). Right: a diagram of the agent's backend for the
   current step, boxes joined by arrows. Left: the real prototype. All three read the same signals the prototype
   already produces (the step in the URL, the case state, background jobs, the activity log). */
(function () {
  "use strict";
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => [...(r || document).querySelectorAll(s)];
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  // Link for the "Implementation and scalability roadmap" button. Paste the page address here (a full link, or a path such as "roadmap.html").
  // While it is empty, the button shows a short note instead of opening anything.
  const CFG = window.RW_CONFIG || {};
  const LIVE = !!CFG.live;
  const ROADMAP_URL = CFG.roadmapUrl || "";
  const R = () => window.__rwPreview;
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  // ------------------------------------------------------------------ icons (24 x 24, stroke only)
  const IC = {
    you: '<path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-7 8a7 7 0 0 1 14 0"/>',
    ai: '<path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8zM18.5 15l.9 2.1 2.1.9-2.1.9-.9 2.1-.9-2.1-2.1-.9 2.1-.9z"/>',
    code: '<path d="M9 7l-5 5 5 5M15 7l5 5-5 5"/>',
    data: '<path d="M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zm0 0v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3.2 3 3.2 15 0 18M12 3c-3.2 3-3.2 15 0 18"/>',
    folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    lock: '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    ext: '<path d="M4 5h16v11H9l-5 4z"/>',
    out: '<path d="M7 3h7l5 5v13H7zM14 3v5h5"/>',
    eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    mark: '<path d="M5 12l4 4 10-10"/>'
  };
  const svgi = (k, w) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${w || 2}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${IC[k]}</svg>`;

  // ------------------------------------------------------------------ the journey: one column per step
  // k: decide = your call, light = read it, opt = optional, none = the agent runs it alone
  const STEPS = [
    { n: 1, t: "The ask", ag: "Reads files", me: "Paste the ask", k: "decide" },
    { n: 2, t: "Question", ag: "Drafts ideas", me: "Confirm", k: "decide" },
    { n: 3, t: "Targets", ag: "Plans research", me: "Lock targets", k: "decide" },
    { n: 4, t: "Plan", ag: "Writes searches", me: "Check outgoing", k: "decide" },
    { n: 5, t: "Gathering", ag: "Searches sources", me: "", k: "none" },
    { n: 6, t: "Checking", ag: "Verifies all", me: "", k: "none" },
    { n: 7, t: "Review", ag: "Flags doubts", me: "Decide flags", k: "decide" },
    { n: 8, t: "Results", ag: "Tests ideas", me: "Read", k: "light" },
    { n: 9, t: "Fill gaps", ag: "Drafts follow-up", me: "Send, reply", k: "opt" },
    { n: 10, t: "Answer", ag: "Writes it up", me: "Read", k: "light" },
    { n: 11, t: "What if", ag: "Recalculates", me: "Try sliders", k: "opt" },
    { n: 12, t: "Conclusion", ag: "Builds exports", me: "Write yours", k: "decide" }
  ];
  const TITLES = { 1: "Define the ask", 2: "Confirm the question", 3: "Set the targets", 4: "Plan the research", 5: "Gather the evidence", 6: "Check the evidence", 7: "Review the evidence", 8: "Read the results", 9: "Fill the gaps", 10: "The answer", 11: "What if", 12: "Your conclusion" };
  const PHASES = [["Frame the question", 1, 4], ["Build the evidence", 5, 7], ["Test and conclude", 8, 12]];
  const JOBCOL = { frame: 1, plan: 2, route: 3, collect: 5, clean: 6, trip_1: 9, trip_reply_1: 9, addup: 10 };
  const JOBMS = { frame: 2200, plan: 2600, route: 2400, collect: 4400, clean: 4400, trip_1: 2200, trip_reply_1: 2400, addup: 2800, advance: 2000 };
  const JOBWORD = { frame: "reading the files and the ask", plan: "drafting ideas and looking up benchmarks", route: "working out where each answer will come from",
    collect: "searching the web, the firm archive and the client files", clean: "reading every source and checking each quote",
    trip_1: "drafting a narrower follow-up question", trip_reply_1: "reading the client's reply", addup: "applying your locked rule and writing the summary", advance: "jumping ahead with the sample's saved answers" };

  // ------------------------------------------------------------------ the backend, one diagram per step
  // t: you | ai | code | data | lock | ext | out.  c: column 0-2.  r: row.  seg says which part of the work a node belongs to,
  // o orders the nodes inside a running job.  soft = optional for you.
  const n = (id, t, l, c, r, seg, say, o) => ({ id, t, l, c, r, seg: seg || "pre", say: say || "", o: o || 0 });
  const FLOW = {
    1: { ask: "Check the ask, then click <b>Check the ask</b>.", nodes: [
      n("you", "you", "Paste the ask", 0, 0, "you", "You paste the client's ask, add their files and list private numbers."),
      n("files", "data", "Client files", 2, 0, "pre", "Files the client already sent.", 0),
      n("priv", "code", "Privacy filter", 1, 1, "j:frame", "Client names and private numbers are masked before anything leaves the firm.", 0),
      n("ai1", "ai", "AI reads files", 1, 2, "j:frame", "A fast AI model pulls out each figure with the sentence it came from.", 1),
      n("qc", "code", "Quote check", 1, 3, "j:frame", "Code checks every quote, word for word. Anything that fails is dropped.", 2),
      n("ai2", "ai", "AI frames the ask", 1, 4, "j:frame", "A smarter AI model splits the ask into a belief to test and a decision.", 3),
      n("out", "out", "Draft question", 1, 5, "out")],
      edges: [["you", "priv"], ["files", "priv"], ["priv", "ai1"], ["ai1", "qc"], ["qc", "ai2"], ["ai2", "out"]] },
    2: { ask: "Read the question, then click <b>Confirm question</b>.", nodes: [
      n("you", "you", "Check wording", 0, 0, "you", "You check the question. The client's belief is a claim to test, not a fact."),
      n("q", "out", "Question", 2, 0, "pre", "The question the AI drafted from your ask."),
      n("ai", "ai", "AI drafts ideas", 1, 1, "j:plan", "A smart AI model writes 2 to 6 testable ideas, each with a target.", 0),
      n("web", "data", "Web search", 2, 2, "j:plan", "The AI writes a search for each target. The web returns a benchmark.", 1),
      n("rate", "code", "Rate sources", 1, 3, "j:plan", "Fixed rules grade each source's quality and date. The AI does not.", 2),
      n("out", "out", "Ideas + targets", 1, 4, "out")],
      edges: [["you", "ai"], ["q", "ai"], ["ai", "web", "search"], ["web", "rate", "benchmark"], ["rate", "out"]] },
    3: { ask: "Mark the critical ideas, then click <b>Lock targets</b>.", nodes: [
      n("you", "you", "Set pass lines", 0, 0, "you", "You mark the critical ideas, drop weak ones and lock the targets."),
      n("ideas", "out", "Ideas + targets", 2, 0, "pre", "Each idea has a target and the source it came from."),
      n("lock", "lock", "Lock targets", 1, 1, "j:route", "Targets and the quality check freeze. Nothing can change them later.", 0),
      n("ai", "ai", "AI plans research", 1, 2, "j:route", "A fast AI model decides where each answer comes from and writes the searches.", 1),
      n("files", "data", "Client files", 2, 2, "j:route", "Needs the client has already answered are skipped.", 1),
      n("clean", "code", "Remove private terms", 1, 3, "j:route", "Every search and request is cleaned of private terms.", 2),
      n("out", "out", "Locked plan", 1, 4, "out")],
      edges: [["you", "lock"], ["ideas", "lock"], ["lock", "ai"], ["files", "ai"], ["ai", "clean"], ["clean", "out"]] },
    4: { ask: "Check what goes out, then click <b>Mark as sent</b>.", nodes: [
      n("plan", "out", "Searches + requests", 1, 0, "pre", "Searches and requests, already cleaned of private terms."),
      n("you", "you", "Check what goes out", 1, 1, "you", "You read every request and untick any source you don't trust."),
      n("ext", "ext", "Client + experts", 2, 2, "pre", "You send the requests yourself, outside this tool."),
      n("mark", "code", "Mark as sent", 1, 2, "s:mark", "Only records your click. The tool sends nothing."),
      n("out", "out", "Collection starts", 1, 3, "out")],
      edges: [["plan", "you"], ["you", "mark"], ["you", "ext", "you send", true], ["mark", "out"]] },
    5: { ask: "Nothing to do here. The agent is collecting.", nodes: [
      n("sent", "you", "You marked sent", 1, 0, "pre", "You marked the requests as sent. Collection started by itself."),
      n("web", "data", "Web", 0, 1, "j:collect", "Only the sources you left ticked.", 0),
      n("arc", "data", "Firm archive", 1, 1, "j:collect", "Past studies, searched in-house. Nothing leaves the firm.", 0),
      n("cli", "data", "Client files", 2, 1, "j:collect", "Figures the client already supplied.", 0),
      n("col", "code", "Collect + file", 1, 2, "j:collect", "Capped and cached. Each item keeps where it came from.", 1),
      n("out", "out", (c) => `${c.found || "–"} items`, 1, 3, "out")],
      edges: [["sent", "web"], ["sent", "arc"], ["sent", "cli"], ["web", "col"], ["arc", "col"], ["cli", "col"], ["col", "out"]] },
    6: { ask: "Nothing to do here. The agent is checking everything.", nodes: [
      n("items", "data", "Collected items", 1, 0, "pre", "Everything gathered from the web, the archive and client files."),
      n("merge", "code", "Merge copies", 1, 1, "j:clean", "Exact copies are skipped. A copy of one study counts once.", 0),
      n("ai", "ai", "AI reads sources", 1, 2, "j:clean", "A fast AI model pulls out each figure with its quote.", 1),
      n("qc", "code", "Quote check", 1, 3, "j:clean", "Every quoted figure must appear word for word in its source.", 2),
      n("rate", "code", "Rate source", 0, 4, "j:clean", "Official, Trusted, Press or Unverified, by fixed rules.", 3),
      n("chk", "code", "9-test check", 2, 4, "j:clean", "Items that pass every test are approved without you.", 3),
      n("out", "out", (c) => (c.auto ? `${c.auto} auto, ${c.decision} flagged` : "Approved + flagged"), 1, 5, "out")],
      edges: [["items", "merge"], ["merge", "ai"], ["ai", "qc"], ["qc", "rate"], ["qc", "chk"], ["rate", "out"], ["chk", "out"]] },
    7: { ask: "Decide the flagged items, then click <b>Run tests</b>.", nodes: [
      n("pre", "out", (c) => (c.auto ? `${c.auto} passed, ${c.decision} flagged` : "Flagged items"), 1, 0, "pre", "The agent approved what passed and flagged the rest for you."),
      n("you", "you", "Decide flagged", 0, 1, "you", "You accept, reject or keep each flagged item. One click each."),
      n("spot", "you", "Spot check", 2, 1, "you", "Optional. Compare one passed item with its source.", 0),
      n("lock", "lock", "Locked targets", 2, 2, "pre", "The targets you locked at step 3."),
      n("tests", "code", "Run tests", 1, 2, "s:tests", "Each idea is compared with its locked target. Same evidence, same result.", 0),
      n("out", "out", "Results", 1, 3, "out")],
      edges: [["pre", "you"], ["pre", "spot", "", true], ["you", "tests"], ["spot", "tests", "", true], ["lock", "tests"], ["tests", "out"]] },
    8: { ask: "Read each result. Then <b>Fill the gaps</b> or <b>Add it up</b>.", nodes: [
      n("ev", "data", "Evidence", 0, 0, "pre", "The evidence you approved."),
      n("lock", "lock", "Locked targets", 2, 0, "pre", "The targets set before any evidence was read."),
      n("rules", "code", "Verdict rules", 1, 1, "pre", "Holds, Fails, Sources disagree or Not enough evidence, by fixed rules."),
      n("conf", "code", "Confidence", 1, 2, "pre", "Strong, Fair or Weak, by how many separate sources agree. A market fact needs two."),
      n("you", "you", "Read results", 1, 3, "you", "You read each result and open the reasoning behind it."),
      n("gaps", "you", "Fill the gaps", 0, 4, "you", "Optional. One narrow follow-up where evidence is thin."),
      n("add", "you", "Add it up", 2, 4, "you", "Go straight to the answer.")],
      soft: ["you", "gaps", "add"],
      edges: [["ev", "rules"], ["lock", "rules"], ["rules", "conf"], ["conf", "you"], ["you", "gaps"], ["you", "add"]] },
    9: { ask: "Draft a follow-up, send it yourself, add the reply.", nodes: [
      n("gap", "out", (c) => `${c.tripIdea} needs more`, 2, 0, "pre", "This idea has too little evidence to call."),
      n("you1", "you", "Ask follow-up", 0, 0, "you1", "You click Draft question for the idea that needs more."),
      n("ai1", "ai", "AI drafts question", 1, 1, "j:trip_1", "A smart AI model drafts one narrow question, checked for private numbers.", 0),
      n("you2", "you", "You send it", 1, 2, "you2", "You send it yourself, outside the tool, then add the reply here."),
      n("cl", "ext", "Client", 2, 2, "pre", "The client answers with a file or a note."),
      n("ai2", "ai", "AI reads reply", 1, 3, "j:trip_reply_1", "A fast AI model pulls out the figures with their quotes.", 0),
      n("chk", "code", "Quote + sample check", 1, 4, "j:trip_reply_1", "Quotes matched, and the sample compared with the target group.", 1),
      n("re", "code", "Re-test one idea", 1, 5, "s:retest", "Only that idea reopens. Everything else stays locked."),
      n("out", "out", "Updated result", 1, 6, "out")],
      soft: ["you1"],
      edges: [["gap", "ai1"], ["you1", "ai1"], ["ai1", "you2"], ["you2", "cl", "", true], ["cl", "ai2", "reply"], ["ai2", "chk"], ["chk", "re"], ["re", "out"]] },
    10: { ask: "Read the answer, then try the <b>Stress-test</b>.", nodes: [
      n("res", "out", "Results", 0, 0, "pre", "The result for every idea."),
      n("rule", "lock", "Locked rule", 2, 0, "pre", "The rule set at step 3. A failed critical idea means Not achievable."),
      n("apply", "code", "Apply the rule", 1, 1, "j:addup", "Code applies the locked rule. The AI doesn't decide the answer.", 0),
      n("ev", "data", "Evidence", 0, 2, "j:addup", "Every sentence must cite the evidence behind it.", 1),
      n("ai", "ai", "AI writes summary", 1, 2, "j:addup", "A smart AI model writes 3 to 5 sentences.", 1),
      n("chk", "code", "Check each line", 1, 3, "j:addup", "A missing citation or a number not in the data? The line is thrown out.", 2),
      n("unk", "ai", "AI lists unknowns", 2, 3, "j:addup", "A fast AI model lists what is still unknown.", 2),
      n("you", "you", "Read answer", 1, 4, "you", "You read the answer and open any evidence behind it."),
      n("out", "out", (c) => (c.overall ? c.overall : "Answer"), 1, 5, "out")],
      soft: ["you"],
      edges: [["res", "apply"], ["rule", "apply"], ["apply", "ai"], ["ev", "ai"], ["ai", "chk"], ["ai", "unk"], ["chk", "you"], ["unk", "you"], ["you", "out"]] },
    11: { ask: "Move a slider and watch the answer change.", nodes: [
      n("you", "you", "Move a slider", 0, 0, "you", "You change a target or an assumption to see what happens."),
      n("lock", "lock", "Locked plan", 2, 0, "pre", "Your locked plan does not change while you explore."),
      n("calc", "code", "Recalculate", 1, 1, "s:whatif", "Every idea and the answer update at once. Nothing is saved.", 0),
      n("live", "out", "Live answer", 1, 2, "s:whatif", "The answer under the value you picked."),
      n("you2", "you", "Make it real", 0, 3, "you", "Optional. You confirm, and the new value becomes the target."),
      n("re", "code", "Reopen + retest", 1, 4, "s:retarget", "Evidence and your decisions are kept. The change is logged.")],
      soft: ["you", "you2"],
      edges: [["you", "calc"], ["lock", "calc", "unchanged", true], ["calc", "live"], ["live", "you2"], ["you2", "re"]] },
    12: { ask: "Write your conclusion. The agent never writes this part.", nodes: [
      n("you", "you", "Write conclusion", 1, 0, "you", "You write the conclusion in your own words."),
      n("save", "code", "Save as written", 1, 1, "s:save", "Saved exactly as you wrote it. The agent adds nothing.", 0),
      n("log", "data", "Action log", 2, 1, "s:save", "Every action by the AI, the code and you is recorded.", 0),
      n("exp", "code", "Build exports", 1, 2, "s:save", "Print, Markdown and JSON are built from the saved case.", 1),
      n("out", "out", "Exports ready", 1, 3, "out")],
      edges: [["you", "save"], ["save", "exp"], ["save", "log"], ["exp", "out"]] }
  };
  const TYPE = {
    you: { c: "#c4570f", b: "#fff0e3", i: "you" }, ai: { c: "#6b46c1", b: "#f1ebff", i: "ai" }, code: { c: "#1d5fc4", b: "#e8f0ff", i: "code" },
    data: { c: "#0f7a73", b: "#e2f5f3", i: "data" }, lock: { c: "#0f2747", b: "#e3e9f3", i: "lock" }, ext: { c: "#5b6a80", b: "#eef2f7", i: "ext" },
    out: { c: "#0f2747", b: "#eef2f7", i: "out" }
  };
  const NODE_ICON = { web: "globe", cli: "folder", files: "folder", arc: "data", items: "data", ev: "data" };

  // ------------------------------------------------------------------ what the case looks like right now
  const caseObj = () => (R() && R().liveCase ? R().liveCase() : null);
  const stepFromHash = () => { const m = location.hash.match(/step\/(\d+)/); return m ? Math.min(12, Math.max(1, +m[1])) : (/case\/\d+/.test(location.hash) ? 1 : 0); };
  const jobT = {}, flashAt = {}, synced = {};
  let caseKey = "";

  function stats(c) {
    const b = c ? c.b : null;
    const o = { found: 0, figs: 0, verified: 0, auto: 0, decision: 0, decided: 0, hn: 0, tripIdea: "One idea", overall: "" };
    if (!b) return o;
    const ev = b.evidence || [];
    o.found = (b.counts && b.progress.done["5"] && b.counts.collected != null) ? b.counts.collected : ev.length;
    ev.forEach((e) => (e.figures_json || []).forEach((f) => { o.figs++; if (f.verified) o.verified++; }));
    if (b.progress.done["6"]) {
      o.auto = ev.filter((e) => e.bucket === "auto" || e.status === "auto_approved").length;
      if (b.review) { o.decision = b.review.decision_total; o.decided = b.review.decided; }
    }
    o.hn = (b.hypotheses || []).filter((h) => !h.removed_reason).length;
    if (b.trips && b.trips[0]) o.tripIdea = b.trips[0].hypothesis_code || o.tripIdea;
    else { const h = (b.hypotheses || []).find((x) => x.verdict && x.verdict.result === "not_enough"); if (h) o.tripIdea = h.code; }
    if (b.overall && b.overall.label) o.overall = b.overall.label;
    return o;
  }
  const jobDone = (b, k) => !!(b.jobs && b.jobs[k] && b.jobs[k].status === "done");
  const isRunning = (b, k) => (b.running_jobs || []).includes(k);
  function ran(seg, c) {
    const b = c.b;
    if (seg.startsWith("j:")) return jobDone(b, seg.slice(2));
    if (seg === "s:mark") return !!b.progress.done["4"];
    if (seg === "s:tests") return !!b.progress.done["7"];
    if (seg === "s:retest") return !!(b.trips && b.trips[0] && b.trips[0].retested_at);
    if (seg === "s:save") return !!(b.conclusion && b.conclusion.saved_at);
    if (seg === "s:retarget") return (c.acts || []).some((a) => /Reopened the targets/.test(a.message || ""));
    return !!synced[caseKey + seg];
  }
  function youState(seg, step, c, soft) {
    const b = c.b, d = b.progress.done;
    if (seg === "you1") return jobDone(b, "trip_1") || isRunning(b, "trip_1") ? "done" : "soft";
    if (seg === "you2") return jobDone(b, "trip_reply_1") || isRunning(b, "trip_reply_1") ? "done" : (jobDone(b, "trip_1") ? "wait" : "idle");
    if (soft) return "soft";
    if ([1, 2, 3, 4, 7, 12].includes(step)) {
      const started = (b.running_jobs || []).some((k) => JOBCOL[k] === step) || FLOW[step].nodes.some((x) => x.seg.startsWith("j:") && jobDone(b, x.seg.slice(2)));
      return d[String(step)] || started ? "done" : "wait";
    }
    return "soft";
  }
  function pipeNow(c) {
    const rj = (c && c.b.running_jobs) || [];
    for (const k of rj) if (JOBCOL[k]) return { step: JOBCOL[k], job: k };
    return { step: stepFromHash(), job: null };
  }
  function track(c) {
    const rj = (c && c.b.running_jobs) || [], now = performance.now();
    Object.keys(jobT).forEach((k) => { if (!rj.includes(k)) delete jobT[k]; });
    rj.forEach((k) => { if (!(k in jobT)) jobT[k] = now; });
  }

  // work out the state of every node: idle, active, done, wait or soft
  function nodeStates(flow, step, c) {
    const now = performance.now(), st = {}, soft = new Set(flow.soft || []);
    const orders = {};
    flow.nodes.forEach((x) => { if (x.seg.startsWith("j:")) (orders[x.seg] = orders[x.seg] || new Set()).add(x.o); });
    flow.nodes.forEach((x) => {
      let s = "idle";
      if (x.seg === "pre") s = "done";
      else if (x.seg === "out") s = null;
      else if (x.seg.startsWith("j:")) {
        const k = x.seg.slice(2);
        if (isRunning(c.b, k)) {
          const list = [...orders[x.seg]].sort((a, b) => a - b), idx = list.indexOf(x.o);
          const pr = (c.b.jobs[k] || {}).progress || {};
          const frac = LIVE && pr.total > 0 ? Math.min(0.999, pr.done / pr.total) : Math.min(0.999, (now - (jobT[k] || now)) / ((LIVE ? (CFG.jobMs || {})[k] : 0) || JOBMS[k] || 2400));
          const cur = Math.min(Math.floor(frac * list.length), list.length - 1);
          s = idx < cur ? "done" : idx === cur ? "active" : "idle";
        } else s = ran(x.seg, c) ? "done" : "idle";
      } else if (x.seg.startsWith("s:")) {
        if (flashAt[caseKey + x.seg] && now - flashAt[caseKey + x.seg] < 900) s = "active";
        else s = ran(x.seg, c) ? "done" : "idle";
      } else if (x.seg.startsWith("you")) {
        s = youState(x.seg, step, c, soft.has(x.id));
        if (x.id === "spot") s = b0(c) && c.b.review && c.b.review.spot_done > 0 ? "done" : "soft";
      }
      st[x.id] = s;
    });
    // the end node finishes once all the work above it has finished
    const work = flow.nodes.filter((x) => !["pre", "out"].includes(x.seg) && !x.seg.startsWith("you") && x.seg !== "s:retarget" && !(step === 11));
    const gates = flow.nodes.filter((x) => x.seg.startsWith("you") && !soft.has(x.id) && x.id !== "spot" && x.seg !== "you1");
    flow.nodes.forEach((x) => {
      if (x.seg !== "out") return;
      st[x.id] = work.length && work.every((w) => st[w.id] === "done") && gates.every((g) => st[g.id] === "done") ? "done" : "idle";
    });
    return st;
  }
  const b0 = (c) => !!c;

  // ------------------------------------------------------------------ the diagram
  const W = 410, NW = 128, NH = 50, PX = [0, 141, 282], TOP = 10;
  let PITCH = 66;
  const val = (x, ctx) => (typeof x === "function" ? x(ctx) : x);
  function wrap(s, max) {
    const words = String(s).split(" "), lines = [""];
    words.forEach((w) => { const cur = lines[lines.length - 1]; if (!cur) lines[lines.length - 1] = w; else if ((cur + " " + w).length <= max) lines[lines.length - 1] = cur + " " + w; else lines.push(w); });
    return lines.slice(0, 2);
  }
  function anchors(a, b) {
    const ax = PX[a.c], ay = TOP + a.r * PITCH, bx = PX[b.c], by = TOP + b.r * PITCH;
    if (a.r === b.r) {
      if (b.c > a.c) return [ax + NW, ay + NH / 2, bx, by + NH / 2, "h"];
      return [ax, ay + NH / 2, bx + NW, by + NH / 2, "h"];
    }
    return [ax + NW / 2, ay + NH, bx + NW / 2, by, "v"];
  }
  function edgePath(a, b) {
    const [x1, y1, x2, y2, dir] = anchors(a, b);
    if (dir === "h") return `M${x1},${y1} L${x2},${y2}`;
    if (x1 === x2) return `M${x1},${y1} L${x2},${y2}`;
    const k = Math.min(22, Math.abs(y2 - y1) / 2);
    return `M${x1},${y1} C${x1},${y1 + k} ${x2},${y2 - k} ${x2},${y2}`;
  }
  function diagram(flow, step, c, sts, ctx) {
    const byId = Object.fromEntries(flow.nodes.map((x) => [x.id, x]));
    const maxR = Math.max(...flow.nodes.map((x) => x.r));
    PITCH = maxR <= 4 ? 82 : maxR === 5 ? 74 : 66;
    const H = TOP + maxR * PITCH + NH + 8;
    let g = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="How the agent works behind this step">
      <defs>${[["idle", "#b9c5d6"], ["done", "#0f2747"], ["active", "#1d5fc4"], ["wait", "#e9771a"]].map(([k, col]) => `<marker id="ah-${k}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1,1 L9,5 L1,9 z" fill="${col}"/></marker>`).join("")}</defs>`;
    flow.edges.forEach(([a, b, lab, dashed]) => {
      const A = byId[a], B = byId[b], sb = sts[b.id !== undefined ? b.id : b];
      let s = sts[b] || "idle";
      const cls = s === "active" ? "active" : s === "done" ? "done" : s === "wait" ? "wait" : "idle";
      const d = edgePath(A, B), [x1, y1, x2, y2] = anchors(A, B);
      g += `<path class="ed e-${cls}${dashed ? " dsh" : ""}" d="${d}" marker-end="url(#ah-${cls})"/>`;
      if (lab) g += `<g class="elab" transform="translate(${(x1 + x2) / 2},${(y1 + y2) / 2})"><rect x="${-lab.length * 2.9 - 5}" y="-8" width="${lab.length * 5.8 + 10}" height="15" rx="7"/><text y="3" text-anchor="middle">${esc(lab)}</text></g>`;
    });
    flow.nodes.forEach((x) => {
      const s = sts[x.id] || "idle", ty = TYPE[x.t], px = PX[x.c], py = TOP + x.r * PITCH;
      const label = val(x.l, ctx), lines = wrap(label, 14), icon = NODE_ICON[x.id] && x.t === "data" ? NODE_ICON[x.id] : ty.i;
      const ty0 = lines.length === 1 ? 29 : 23;
      g += `<g class="nd t-${x.t} s-${s}${x.seg === "out" ? " end" : ""}" data-id="${x.id}" transform="translate(${px},${py})" style="--c:${ty.c};--cb:${ty.b}" tabindex="0">
        <title>${esc(x.say || label)}</title>
        <rect class="ring" x="-3" y="-3" width="${NW + 6}" height="${NH + 6}" rx="14"/>
        <rect class="bg" width="${NW}" height="${NH}" rx="11"/>
        <circle class="ic" cx="20" cy="${NH / 2}" r="12"/>
        <g class="icg" transform="translate(13.5,${NH / 2 - 6.5}) scale(.54)">${svgi(icon, 2.4).replace(/^<svg[^>]*>/, "").replace(/<\/svg>$/, "")}</g>
        <text class="lb" x="38" y="${ty0}">${lines.map((ln, i) => `<tspan x="38" dy="${i ? 12.5 : 0}">${esc(ln)}</tspan>`).join("")}</text>
        ${s === "done" && x.seg !== "pre" ? `<g class="bdg ok" transform="translate(${NW - 8},-4)"><circle r="8"/><g transform="translate(-5,-5) scale(.42)">${svgi("check", 4).replace(/^<svg[^>]*>/, "").replace(/<\/svg>$/, "")}</g></g>` : ""}
        ${s === "active" ? `<g class="bdg run" transform="translate(${NW - 8},-4)"><circle r="8" class="bgc"/><circle r="4.5" class="arc"/></g>` : ""}
        ${s === "wait" ? `<g class="bdg you" transform="translate(${NW - 38},-9)"><rect width="46" height="15" rx="7.5"/><text x="23" y="10.8" text-anchor="middle">Your turn</text></g>` : ""}
        ${s === "soft" ? `<g class="bdg opt" transform="translate(${NW - 36},-9)"><rect width="40" height="15" rx="7.5"/><text x="20" y="10.8" text-anchor="middle">Optional</text></g>` : ""}
      </g>`;
    });
    return g + "</svg>";
  }

  // ------------------------------------------------------------------ right pane
  let paneSig = "", pane, hoverId = "", curFlow = null;
  const ACTOR = { llm: "AI", rule_engine: "Code", consultant: "You", client: "Client", expert: "Expert", system: "System" };
  function buildPane() {
    pane = document.createElement("aside");
    pane.id = "rw-flow";
    pane.setAttribute("aria-label", "What the agent is doing behind the screen");
    pane.innerHTML = `<div class="fl-head"><div><div class="fl-kick" id="fl-kick">Behind the screen</div><h2 id="fl-h">The agent's workflow</h2></div><span class="stat rdy" id="fl-stat">Ready</span></div>
      <div class="fl-map" id="fl-map"></div>
      <div class="fl-cap" id="fl-cap"></div>
      <div class="fl-tick" id="fl-tick"></div>
      <div class="fl-key"><span><i class="k-you"></i>You</span><span><i class="k-ai"></i>AI model</span><span><i class="k-code"></i>Plain code</span>
        <span><i class="k-data"></i>Data in</span><span><i class="k-lock"></i>Locked</span><span><i class="k-ext"></i>Outside the tool</span></div>`;
    document.body.appendChild(pane);
    const fab = document.createElement("button");
    fab.id = "rw-fab"; fab.textContent = "Behind the screen";
    fab.addEventListener("click", () => document.body.classList.toggle("fl-open"));
    document.body.appendChild(fab);
    const map = $("#fl-map");
    map.addEventListener("mouseover", (e) => { const g = e.target.closest(".nd"); if (g && g.dataset.id !== hoverId) { hoverId = g.dataset.id; caption(); } });
    map.addEventListener("mouseleave", () => { hoverId = ""; caption(); });
    map.addEventListener("focusin", (e) => { const g = e.target.closest(".nd"); if (g) { hoverId = g.dataset.id; caption(); } });
  }
  let capCtx = null;
  function caption() {
    if (!capCtx) return;
    const { flow, sts, step, running, job } = capCtx;
    let node = hoverId ? flow.nodes.find((x) => x.id === hoverId) : null;
    if (!node) node = flow.nodes.find((x) => sts[x.id] === "active") || flow.nodes.find((x) => sts[x.id] === "wait");
    const cap = $("#fl-cap");
    if (node && node.say) {
      const ty = TYPE[node.t];
      cap.innerHTML = `<span class="ci t-${node.t}">${svgi(NODE_ICON[node.id] && node.t === "data" ? NODE_ICON[node.id] : ty.i, 2.2)}</span><p>${esc(node.say)}</p>`;
    } else if (running) cap.innerHTML = `<p>The agent is ${esc(JOBWORD[job] || "working")}.</p>`;
    else cap.innerHTML = `<p>${flow.ask}</p>`;
  }
  function logLine(c) {
    const a = ((c && c.acts) || []).filter((x) => x.message).slice(-1)[0];
    return a ? `<i class="lg ${esc(a.actor)}">${esc(ACTOR[a.actor] || a.actor)}</i><span>${esc(a.message)}</span>` : "";
  }
  function renderPane() {
    const c = caseObj();
    if (!c) {
      if (paneSig === "home") return;
      paneSig = "home"; capCtx = null;
      $("#fl-kick").textContent = "Behind the screen"; $("#fl-h").textContent = "The agent's workflow";
      $("#fl-stat").className = "stat rdy"; $("#fl-stat").textContent = "Ready";
      $("#fl-map").innerHTML = `<p class="fl-empty">${LIVE ? "Open a case to see what the agent does behind each screen." : "Start the worked example to see what the agent does behind each screen."}</p>`;
      $("#fl-cap").innerHTML = ""; $("#fl-tick").innerHTML = "";
      return;
    }
    track(c);
    const { step, job } = pipeNow(c);
    if (!step) return;
    const flow = FLOW[step], ctx = stats(c), sts = nodeStates(flow, step, c);
    const running = !!job || isRunning(c.b, "advance");
    const waiting = Object.values(sts).includes("wait");
    const html = diagram(flow, step, c, sts, ctx);
    const sig = [caseKey, step, running, waiting].join("|") + html;
    capCtx = { flow, sts, step, running, job };
    if (sig !== paneSig) {
      paneSig = sig;
      $("#fl-kick").textContent = `Behind step ${step} of 12`;
      $("#fl-h").textContent = TITLES[step];
      const stat = $("#fl-stat");
      if (running) { stat.className = "stat run"; stat.innerHTML = '<i class="sp"></i>Agent working'; }
      else if (waiting) { stat.className = "stat wait"; stat.textContent = "Your turn"; }
      else if (step === 5 || step === 6) { stat.className = "stat ok"; stat.textContent = "Done"; }
      else { stat.className = "stat rdy"; stat.textContent = "Ready"; }
      $("#fl-map").innerHTML = html;
    }
    caption();
    const t = logLine(c);
    if ($("#fl-tick").dataset.t !== t) { $("#fl-tick").dataset.t = t; $("#fl-tick").innerHTML = t; }
  }

  // ------------------------------------------------------------------ top strip
  let top, map, here, lastStripSig = "", lastScore = {};
  function buildTop() {
    top = document.createElement("div");
    top.id = "rw-top";
    const dec = STEPS.filter((s) => s.k === "decide").length, skim = STEPS.filter((s) => s.k === "light" || s.k === "opt").length, auto = STEPS.filter((s) => s.k === "none").length;
    top.innerHTML = `<div class="tp-head">
        <div class="tp-brand"><b>Research Workbench</b><span>An AI research agent for case teams</span></div>
        <div class="tp-sum" title="Of the 12 steps">
          <span class="sum d"><b>${dec}</b>need you</span><span class="sum l"><b>${skim}</b>skim or skip</span><span class="sum a"><b>${auto}</b>run alone</span></div>
        <div class="tp-score" id="tp-score">
          <div class="sc" data-k="found"><b>–</b><span>Sources found</span></div>
          <div class="sc" data-k="quotes"><b>–</b><span>Quotes matched by code</span></div>
          <div class="sc" data-k="auto"><b>–</b><span>Passed on their own</span></div>
          <div class="sc" data-k="call"><b>–</b><span>Needed your call</span></div></div>
        <div class="tp-btns"><button id="tp-road" class="road" title="Implementation and scalability roadmap" aria-label="Implementation and scalability roadmap"><span class="rl">Implementation &amp; scalability roadmap</span><span class="rs">Roadmap</span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17L17 7M9 7h8v8"/></svg></button><button id="tp-guide" title="How to read this page">Guide</button><button id="tp-restart" title="${LIVE ? "Back to the home screen" : "Start the example again"}">${LIVE ? "Home" : "Restart"}</button><button id="tp-compact" title="Show less of the journey">Collapse</button></div></div>
      <div class="tp-scroll"><div class="tp-map" id="tp-map"></div></div><div class="tp-toast" id="tp-toast"></div>`;
    document.body.insertBefore(top, document.body.firstChild);
    map = $("#tp-map");
    let h = '<div class="tp-here" id="tp-here"></div><div></div>';
    PHASES.forEach(([t, a, b]) => { h += `<div class="ph" style="grid-column:${a + 1} / ${b + 2};grid-row:1">${esc(t)}</div>`; });
    h += '<div class="lane" style="grid-row:2"></div>';
    STEPS.forEach((s) => { h += `<div style="grid-column:${s.n + 1};grid-row:2"><button class="tc locked" data-n="${s.n}"><span class="dot">${s.n}</span><span class="tt">${esc(s.t)}</span></button></div>`; });
    h += '<div class="lane ag" style="grid-row:3"><i></i>Agent</div>';
    STEPS.forEach((s) => { h += `<div class="ac" data-n="${s.n}" style="grid-column:${s.n + 1};grid-row:3"><span>${esc(s.ag)}</span></div>`; });
    h += '<div class="lane me" style="grid-row:4"><i></i>You</div>';
    STEPS.forEach((s) => {
      const ico = s.k === "light" ? "eye" : "you";
      h += `<div class="yp k-${s.k}" data-n="${s.n}" style="grid-column:${s.n + 1};grid-row:4"><span class="pin">${s.k === "none" ? "" : svgi(ico, 2.4)}</span><span class="yl">${esc(s.me)}</span></div>`;
    });
    h += '<div class="lane effl" style="grid-row:3">Who acts</div>';
    STEPS.forEach((s) => { h += `<div class="eff ${s.k}" data-n="${s.n}" style="grid-column:${s.n + 1};grid-row:3"></div>`; });
    map.innerHTML = h;
    here = $("#tp-here");
    map.addEventListener("click", (e) => { const b = e.target.closest(".tc, .ac, .yp"); if (b) go(+(b.dataset.n)); });
    $("#tp-road").addEventListener("click", () => { if (ROADMAP_URL) window.open(ROADMAP_URL, "_blank", "noopener"); else toast("The roadmap link will be added here."); });
    $("#tp-guide").addEventListener("click", () => $("#rw-intro").classList.add("on"));
    $("#tp-restart").addEventListener("click", () => startDemo());
    $("#tp-compact").addEventListener("click", () => {
      const on = document.body.classList.toggle("rw-compact");
      $("#tp-compact").textContent = on ? "Expand" : "Collapse";
      sizeUp(); place(stepFromHash());
    });
  }
  function toast(t) {
    const el = $("#tp-toast"); el.textContent = t; el.classList.add("on");
    clearTimeout(toast.t); toast.t = setTimeout(() => el.classList.remove("on"), 2600);
  }
  function place(nn) {
    const t = $(`.tc[data-n="${nn}"]`, map);
    if (!nn || !t) { here.classList.remove("on"); return; }
    const cell = t.parentElement, mr = map.getBoundingClientRect(), cr = cell.getBoundingClientRect();
    here.style.left = (cr.left - mr.left - 4) + "px";
    here.style.width = (cr.width + 8) + "px";
    here.style.top = (cr.top - mr.top - 4) + "px";
    here.classList.add("on");
  }
  function renderTop() {
    const c = caseObj(), hs = stepFromHash(), b = c ? c.b : null;
    const rj = (b && b.running_jobs) || [];
    const working = new Set(rj.map((k) => JOBCOL[k]).filter(Boolean));
    const d = b ? b.progress.done : {}, steps = b ? b.progress.steps : [];
    const sig = [caseKey, hs, [...working].join(), JSON.stringify(d), steps.map((s) => s.state[0]).join(""), b && b.trips && b.trips[0] ? b.trips[0].retested_at : "", b && b.conclusion ? b.conclusion.saved_at : ""].join("|");
    if (sig !== lastStripSig) {
      lastStripSig = sig;
      STEPS.forEach((s) => {
        const st = steps[s.n - 1] ? steps[s.n - 1].state : "locked", isHere = hs === s.n, wk = working.has(s.n);
        const done = b && (s.n === 9 ? !!(b.trips && b.trips[0] && b.trips[0].retested_at) : s.n === 12 ? !!(b.conclusion && b.conclusion.saved_at) : !!d[String(s.n)]);
        const tc = $(`.tc[data-n="${s.n}"]`, map);
        tc.className = "tc " + (isHere ? "here" : done || st === "done" ? "done" : st === "open" ? "open" : "locked");
        tc.querySelector(".dot").innerHTML = (done || st === "done") && !isHere ? svgi("check", 3.2) : String(s.n);
        const ac = $(`.ac[data-n="${s.n}"]`, map);
        ac.className = "ac" + (done && !wk ? " done" : "") + (wk ? " now" : "") + (!b || (st === "locked" && !isHere) ? " far" : "");
        const yp = $(`.yp[data-n="${s.n}"]`, map), pin = yp.querySelector(".pin");
        const youWait = isHere && s.k === "decide" && !done && !working.size;
        yp.className = `yp k-${s.k}` + (youWait ? " wait" : "") + (done && s.k === "decide" ? " fin" : "") + (!b || (st === "locked" && !isHere) ? " far" : "");
        if (s.k === "decide") pin.innerHTML = done ? svgi("check", 3.2) : svgi("you", 2.4);
        $(`.eff[data-n="${s.n}"]`, map).classList.toggle("far", !b || (st === "locked" && !isHere));
      });
      place(hs);
    }
    const s0 = stats(c);
    const set = (k, v, sub) => {
      const el = $(`.sc[data-k="${k}"] b`, top), txt = v == null ? "–" : String(v) + (sub ? `<i> of ${sub}</i>` : "");
      if (lastScore[k] !== txt) { lastScore[k] = txt; el.innerHTML = txt; const p = el.parentElement; p.classList.remove("pop"); void p.offsetWidth; p.classList.add("pop"); }
    };
    if (b && s0.found) { set("found", s0.found); set("quotes", s0.figs ? s0.verified : null, s0.figs || null); set("auto", d["6"] ? s0.auto : null); set("call", d["6"] ? s0.decision : null); }
    else ["found", "quotes", "auto", "call"].forEach((k) => set(k, null));
  }
  function sizeUp() { document.documentElement.style.setProperty("--top-h", Math.ceil(top.getBoundingClientRect().height) + "px"); }

  // ------------------------------------------------------------------ moving around
  async function startDemo() {
    if (LIVE) { location.hash = "#/"; return; }
    try {
      const r = await fetch("/api/samples/sample_01_card_launch/load", { method: "POST" }), j = await r.json();
      caseKey = "c" + j.id + ":";
      Object.keys(synced).forEach((k) => delete synced[k]);
      paneSig = ""; lastStripSig = "";
      location.hash = `#/case/${j.id}/step/1`;
    } catch (e) { location.hash = "#/"; }
  }
  async function go(nn) {
    const c = caseObj();
    if (!c) { await startDemo(); if (nn === 1) return; await wait(450); return go(nn); }
    const st = c.b.progress.steps[nn - 1] ? c.b.progress.steps[nn - 1].state : "locked", id = c.b.case.id;
    if (st !== "locked") {
      if (nn === 10 && !c.b.summary && !isRunning(c.b, "addup")) { try { await fetch(`/api/cases/${id}/addup/run`, { method: "POST" }); } catch (e) { /* the page shows its own wait text */ } }
      location.hash = `#/case/${id}/step/${nn}`; return;
    }
    if (LIVE && !c.b.case.sample) { toast("Finish the earlier steps first. Each step opens when the one before it is done."); return; }
    toast("Jumping ahead with the sample's saved answers");
    await fetch(`/api/cases/${id}/sample/advance?to=${nn}`, { method: "POST" });
    const idle = async () => { for (let i = 0; i < 50; i++) { await wait(200); const cc = caseObj(); if (cc && !(cc.b.running_jobs || []).length) break; } };
    await wait(300); await idle();
    if (nn === 10 && !caseObj().b.summary) { await fetch(`/api/cases/${id}/addup/run`, { method: "POST" }); await wait(300); await idle(); }
    location.hash = `#/case/${id}/step/${nn}`;
  }

  // ------------------------------------------------------------------ intro, recap, text viewer
  function buildIntro() {
    const el = document.createElement("div");
    el.id = "rw-intro";
    el.innerHTML = `<div class="in-card" role="dialog" aria-modal="true" aria-labelledby="in-h">
      <h1 id="in-h">An AI research agent that does the legwork. You make the calls.</h1>
      <p>Case teams lose days finding, reading and checking sources. This tool does that work and stops only where a person has to decide.</p>
      <div class="case"><b>Worked example.</b> A bank wants to launch a credit card in India. The client believes the market grows about 30% a year. The agent tests that belief against evidence.${LIVE ? " Open it with Try a sample, or start a case of your own." : ""}</div>
      <div class="in-map" aria-label="How this page is laid out">
        <div class="in-top"><b><span class="n">1</span>Top: the whole journey</b>Twelve steps. The blue band is the agent. Orange pins are where you step in.</div>
        <div class="in-low">
          <div class="in-app"><b><span class="n">2</span>Left: the tool</b>Click through it like a real user. The orange button at the bottom moves you on.</div>
          <div class="in-agent"><b><span class="n">3</span>Right: behind the screen</b>Boxes and arrows show what the agent does and where the AI is used.</div>
        </div></div>
      <div class="in-key"><span><i style="background:var(--me)"></i>You</span><span><i style="background:var(--ai)"></i>AI model</span><span><i style="background:var(--cd)"></i>Plain code, no AI</span><span><i style="background:var(--da)"></i>Data in</span></div>
      <div class="in-go"><button class="btn primary" id="in-go">Start the walkthrough</button><small>${LIVE ? "Nothing is sent to anyone from this tool." : "All figures are sample data. Nothing is sent to anyone."}</small></div></div>`;
    document.body.appendChild(el);
    let seen = false; try { seen = LIVE && sessionStorage.getItem("rw-guide-seen") === "1"; } catch (e) { /* storage blocked */ }
    if (!seen) el.classList.add("on");
    $("#in-go").addEventListener("click", () => { el.classList.remove("on"); try { sessionStorage.setItem("rw-guide-seen", "1"); } catch (e) { /* storage blocked */ } });
    el.addEventListener("click", (e) => { if (e.target === el) el.classList.remove("on"); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") { el.classList.remove("on"); $("#rw-text").classList.remove("on"); $("#rw-recap").classList.remove("on"); } });
    const tx = document.createElement("div");
    tx.id = "rw-text";
    tx.innerHTML = `<div class="tx-card"><header><b id="tx-name">Export</b><div class="row"><button class="btn small" id="tx-copy">Copy</button><button class="btn small" id="tx-close">Close</button></div></header><pre id="tx-pre"></pre></div>`;
    document.body.appendChild(tx);
    const rc = document.createElement("div"); rc.id = "rw-recap"; document.body.appendChild(rc);
    $("#tx-close").addEventListener("click", () => tx.classList.remove("on"));
    tx.addEventListener("click", (e) => { if (e.target === tx) tx.classList.remove("on"); });
    $("#tx-copy").addEventListener("click", () => {
      const t = $("#tx-pre").textContent, done = () => { $("#tx-copy").textContent = "Copied"; setTimeout(() => ($("#tx-copy").textContent = "Copy"), 1500); };
      const sel = () => { const r = document.createRange(); r.selectNodeContents($("#tx-pre")); const s = getSelection(); s.removeAllRanges(); s.addRange(r); $("#tx-copy").textContent = "Selected"; };
      try { navigator.clipboard.writeText(t).then(done, sel); } catch (e) { sel(); }
    });
    window.__rwShowText = (name, text) => { $("#tx-name").textContent = name; $("#tx-pre").textContent = text; tx.classList.add("on"); };
  }
  function showRecap() {
    const c = caseObj(); if (!c) return;
    const b = c.b, st = stats(c), trips = (b.trips || []).length, el = $("#rw-recap");
    el.innerHTML = `<div class="in-card" role="dialog" aria-modal="true" aria-labelledby="rc-h">
      <h1 id="rc-h">That was the whole journey</h1>
      <p>A client's belief went in. A tested answer, with every figure traced to its source, came out. Here is who did what.</p>
      <div class="rc-grid">
        <div class="rc-col rc-ag"><b>The agent did</b><ul>
          <li><strong>${st.found}</strong> items collected from the web, the firm archive and client files</li>
          <li><strong>${st.verified} of ${st.figs}</strong> quoted figures matched word for word by code</li>
          <li><strong>${st.auto}</strong> items passed the quality check and were approved on their own</li>
          <li><strong>${st.hn}</strong> ideas tested against targets locked up front</li>
          <li>One summary where every sentence cites its evidence</li></ul></div>
        <div class="rc-col rc-me"><b>You did</b><ul>
          <li>Framed the question and locked the targets</li>
          <li>Made a call on <strong>${st.decision}</strong> flagged items</li>
          <li>${trips ? `Sent <strong>${trips}</strong> follow-up question to the client` : "Skipped the follow-up"}</li>
          <li>Wrote the conclusion in your own words</li></ul></div></div>
      <div class="in-go"><button class="btn primary" id="rc-close">Close</button><button class="btn" id="rc-again">${LIVE ? "Back to home" : "Run the example again"}</button></div></div>`;
    el.classList.add("on");
    $("#rc-close").addEventListener("click", () => el.classList.remove("on"));
    $("#rc-again").addEventListener("click", () => { el.classList.remove("on"); startDemo(); });
    el.addEventListener("click", (e) => { if (e.target === el) el.classList.remove("on"); });
  }

  // ------------------------------------------------------------------ wire up
  function events() {
    window.addEventListener("rw-api", (e) => {
      const { path, method, status } = e.detail, k = caseKey;
      if (status >= 400) { tick(); return; }
      const hit = (seg) => { flashAt[k + seg] = performance.now(); synced[k + seg] = true; };
      if (/\/requests\/mark-sent$/.test(path)) hit("s:mark");
      else if (/\/test\/run$/.test(path)) hit("s:tests");
      else if (/\/retest$/.test(path)) hit("s:retest");
      else if (/\/whatif$/.test(path)) hit("s:whatif");
      else if (/\/plan\/retarget$/.test(path)) hit("s:retarget");
      else if (/\/conclusion$/.test(path) && method !== "GET") { hit("s:save"); setTimeout(showRecap, 1400); }
      paneSig = ""; lastStripSig = "";
      tick();
    });
    let lastStep = -1;
    window.addEventListener("hashchange", () => {
      paneSig = ""; lastStripSig = ""; hoverId = ""; tick(); document.body.classList.remove("fl-open");
      const nn = stepFromHash();
      if (nn !== lastStep) { lastStep = nn; window.scrollTo(0, 0); }
    });
    window.addEventListener("resize", () => { sizeUp(); place(stepFromHash()); });
  }
  function syncCase() {
    const m = location.hash.match(/case\/(\d+)/), k = m ? "c" + m[1] + ":" : "";
    if (k !== caseKey) { caseKey = k; Object.keys(synced).forEach((x) => delete synced[x]); paneSig = ""; lastStripSig = ""; }
  }
  function tick() { try { if (LIVE) syncCase(); renderTop(); renderPane(); } catch (e) { if (window.console) console.warn("walkthrough view", e); } }
  function start() {
    document.body.classList.add("rw-ready");
    buildTop(); buildPane(); buildIntro(); events();
    if (window.innerHeight < 700) { document.body.classList.add("rw-compact"); $("#tp-compact").textContent = "Expand"; }
    sizeUp();
    try {
      if (window.self !== window.top) {
        window.print = () => { const m = R() && R().meta && R().meta.exports; if (m) window.__rwShowText("Research summary (printing is not available here, copy it instead)", m.md); };
      }
    } catch (e) { /* cross-origin frame: leave print alone */ }
    (LIVE ? Promise.resolve() : startDemo()).then(() => { sizeUp(); tick(); });
    setInterval(tick, 220);
    if (window.ResizeObserver) new ResizeObserver(() => { sizeUp(); place(stepFromHash()); }).observe(top);
    document.fonts && document.fonts.ready && document.fonts.ready.then(() => { sizeUp(); place(stepFromHash()); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
