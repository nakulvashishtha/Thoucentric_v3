/* Gives the walkthrough chrome (top journey strip and right-hand diagram) the same signals the offline demo had,
   using the real backend. It does not change the app. It:
   1. wraps fetch() so every /api call dispatches a "rw-api" event {method, path, status} after the answer arrives;
   2. keeps the latest case bundle (GET /api/cases/{id}) and activity list (GET /api/cases/{id}/activity) of the case in the address;
   3. polls both on its own (1 s while a job runs, 3 s otherwise), so the chrome stays live even when the app is not polling;
   4. exposes window.__rwPreview.liveCase() -> {b: bundle, acts: activity} or null, which rw.js reads. */
(function () {
  "use strict";
  const realFetch = window.fetch.bind(window);
  const cases = {};
  let stopped = false;
  const caseId = () => { const m = location.hash.match(/case\/(\d+)/); return m ? +m[1] : null; };
  const entry = (id) => (cases[id] = cases[id] || { b: null, acts: [] });

  window.fetch = async function (input, init) {
    const url = typeof input === "string" ? input : input.url;
    const res = await realFetch(input, init);
    if (url.startsWith("/api")) {
      const method = ((init && init.method) || "GET").toUpperCase();
      const path = url.replace(/^\/api/, "").split("?")[0];
      if (res.status === 401) stopped = true;
      try { window.dispatchEvent(new CustomEvent("rw-api", { detail: { method, path, status: res.status } })); } catch (e) { /* no listener */ }
      if (method === "GET" && /^\/cases\/\d+$/.test(path) && res.ok) res.clone().json().then((b) => { entry(b.case.id).b = b; }).catch(() => {});
      if (method !== "GET") setTimeout(refresh, 250);
    }
    return res;
  };

  async function refresh() {
    const id = caseId();
    if (!id || stopped) return;
    try {
      const [rb, ra] = await Promise.all([realFetch(`/api/cases/${id}`, { credentials: "same-origin" }), realFetch(`/api/cases/${id}/activity`, { credentials: "same-origin" })]);
      if (rb.status === 401) { stopped = true; return; }
      if (rb.ok) entry(id).b = await rb.json();
      if (ra.ok) { const a = await ra.json(); if (Array.isArray(a)) entry(id).acts = a; }
    } catch (e) { /* offline for a moment: try again on the next tick */ }
  }
  (function loop() {
    const id = caseId(), c = id && cases[id];
    const busy = !!(c && c.b && (c.b.running_jobs || []).length);
    refresh().finally(() => setTimeout(loop, busy ? 1000 : 3000));
  })();
  window.addEventListener("hashchange", () => { stopped = false; refresh(); });

  window.__rwPreview = {
    liveCase() { const id = caseId(); return id && cases[id] && cases[id].b ? cases[id] : null; },
    meta: { exports: null }
  };
})();
