#!/usr/bin/env node
/* A stand-in backend for developing and testing the front end before the real backend exists.
   It serves frontend/dist and answers /api from the states recorded on the original backend (Sample 1 only),
   by running reference/offline_api_replica.js inside Node. It is an ORACLE for response shapes and wording, not the product:
   it cannot handle a blank case, real uploads or any case other than Sample 1.
   Run:  node tools/mock_api_server.js [port]      then open http://localhost:8765  (default port 8765) */
const http = require("http"), fs = require("fs"), path = require("path");
const root = path.resolve(__dirname, "..");
const port = +(process.argv[2] || process.env.PORT || 8765);
const dist = path.join(root, "frontend", "dist");
const data = fs.readFileSync(path.join(root, "reference", "recorded_backend_states.json"), "utf8");

// give the browser-style replica the few globals it expects
const hash = { v: "" };
global.window = global;
global.document = { getElementById: () => ({ textContent: data }), addEventListener() {}, querySelector() { return null; } };
global.location = { get hash() { return hash.v; } };
global.sessionStorage = { getItem() { return null; }, setItem() {}, clear() {} };
global.CustomEvent = class { constructor(t, o) { this.type = t; this.detail = o && o.detail; } };
global.dispatchEvent = () => true;
global.File = global.File || class {};
global.FormData = global.FormData || class {};
let src = fs.readFileSync(path.join(root, "reference", "offline_api_replica.js"), "utf8");
src = src.replace("window.__rwPreview = {", "window.__handle = handle; window.__rwPreview = {");
global.fetch = async () => { throw new Error("no network in the mock"); };
(0, eval)(src);
const handle = global.__handle;

const types = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".png": "image/png", ".svg": "image/svg+xml", ".json": "application/json" };
function parseBody(req, buf) {
  const ct = req.headers["content-type"] || "";
  if (!buf.length) return undefined;
  if (ct.includes("application/json")) return JSON.parse(buf.toString("utf8"));
  if (ct.includes("multipart/form-data")) {                    // good enough for the mock: field names, and the filename of a file part
    const o = {}, text = buf.toString("latin1");
    for (const m of text.matchAll(/name="([^"]+)"(?:; filename="([^"]*)")?\r\n(?:Content-Type:[^\r\n]*\r\n)?\r\n([\s\S]*?)\r\n--/g)) {
      if (m[2] !== undefined) o.filename = m[2]; else o[m[1]] = m[3];
    }
    return o;
  }
  return undefined;
}
http.createServer((req, res) => {
  const url = new URL(req.url, "http://x");
  if (url.pathname.startsWith("/api/")) {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      let r;
      try { r = handle(req.method, req.url, parseBody(req, Buffer.concat(chunks))); }
      catch (e) { r = { status: 500, body: { reason: String(e.message || e), required: [] } }; }
      if (r.binary) { res.writeHead(200, { "content-type": "application/octet-stream" }); res.end(Buffer.from(r.binary, "base64")); return; }
      if (r.text !== undefined) { res.writeHead(r.status, { "content-type": "text/plain; charset=utf-8" }); res.end(r.text); return; }
      res.writeHead(r.status, { "content-type": "application/json" }); res.end(JSON.stringify(r.body));
    });
    return;
  }
  let p = path.join(dist, url.pathname === "/" ? "index.html" : decodeURIComponent(url.pathname));
  if (!p.startsWith(dist) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); res.end("Not found"); return; }
  res.writeHead(200, { "content-type": types[path.extname(p)] || "application/octet-stream" }); res.end(fs.readFileSync(p));
}).listen(port, () => console.log(`Mock API and front end on http://localhost:${port}`));
