const { chromium } = require("playwright");  // run: NODE_PATH=<your playwright install>/node_modules node tools/ui_walkthrough.js
const STOP = +(process.argv[2] || 12);
const W = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1440, height: 860 } });
  p.on('console', m => { if (m.type() === 'error' && !m.text().includes('CERT')) console.log('console:', m.text()); });
  p.on('response', r => { if (r.url().includes('/api/') && r.status() >= 400) console.log('API', r.status(), r.request().method(), r.url()); });
  const shot = async (n) => { await W(700); await p.screenshot({ path: `shots/${n}.png` }); console.log('shot', n); };
  const main = () => p.locator('#root');
  const click = async (text, opts = {}) => { const l = main().getByRole('button', { name: text, exact: true }).first(); await l.waitFor({ timeout: opts.timeout || 30000 }); await l.click(); await W(300); };
  const confirmIf = async (name) => { await W(300); for (const n of [name, 'Confirm'].filter(Boolean)) { const c = p.getByRole('button', { name: n, exact: true }); if (await c.count() > (n === name ? 1 : 0)) { await c.last().click(); await W(300); return; } } };
  await p.goto('http://localhost:8000/', { waitUntil: 'networkidle' });
  await p.getByRole('button', { name: 'Start the walkthrough' }).click(); await W(500);
  await click('Try a sample'); await W(800);
  const ch = p.getByRole('button', { name: /Credit card/ }); if (await ch.count()) { await ch.first().click(); await W(800); }
  await shot('s01_describe');
  await click('Check the ask'); await W(2500);
  await shot('s02_confirm');
  if (STOP <= 2) return b.close();
  await click('Confirm question'); await W(3000);
  await shot('s03_targets');
  const cid = await p.evaluate(() => +location.hash.match(/case\/(\d+)/)[1]);
  const api = (m, path, body) => p.evaluate(async ([m, path, body]) => { const r = await fetch('/api' + path, { method: m, headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined }); return [r.status, await r.json().catch(() => null)]; }, [m, path, body]);
  console.log(await api('PUT', `/cases/${cid}/hypotheses`, [{ code: 'H5', removed_reason: 'History of credit cards in India would not change the decision' }]));
  await W(3500);
  await main().getByText("I've checked the targets and the critical ideas").click(); await W(300);
  await click('Lock targets'); await confirmIf('Lock targets'); await W(3000);
  await shot('s04_plan');
  console.log((await main().innerText()).slice(0, 2500));
  if (STOP <= 4) return b.close();
  await main().getByText('Requests', { exact: true }).first().click(); await W(500);
  await shot('s04b_requests');
  console.log((await main().innerText()).slice(0, 2500));
  await main().getByRole('checkbox').last().check(); await W(300);
  await W(300);
  await click('Mark as sent'); await confirmIf('Mark as sent'); await W(1500);
  await shot('s05_gathering');
  await W(6000);
  await shot('s06_checking');
  await click('Continue'); await W(1200);
  await shot('s07_review');
  const items = await api('GET', `/cases/${cid}`);
  const dec = items[1].evidence.filter(e => e.bucket === 'decision' && e.status === 'needs_decision');
  let first = true;
  for (const e of dec) {
    const row = main().getByText(e.claim, { exact: true }).first();
    await row.scrollIntoViewIfNeeded(); await row.click(); await W(400);
    if (first) { await shot('s07c_row_open'); first = false; }
    const tag = e.script_tag || '';
    if (tag === 'reject_no_method') { await main().getByRole('button', { name: 'Reject', exact: true }).first().click(); }
    else {
      const item = tag === 'cross_check' ? 'Use as sense check' : e.origin_type === 'client_file' ? (e.credibility_json.matches_belief ? "Use as client's claim" : "Accept as client's data") : (e.formula_needs_you ? 'Accept and confirm formula' : 'Accept');
      await main().getByRole('button', { name: 'Accept', exact: true }).first().click(); await W(250);
      await p.getByRole('menuitem', { name: item, exact: true }).first().click().catch(async () => { await p.getByRole('button', { name: item, exact: true }).last().click(); });
    }
    await W(700);
  }
  await shot('s07d_decided');
  await main().getByRole('button', { name: 'Matches', exact: true }).first().click(); await W(500);
  for (const e of items[1].evidence.filter(e => e.bucket === 'auto')) { const cb = main().getByLabel(`Seen ${e.id}`); if (!(await cb.isChecked())) { await cb.click(); await W(700); } }
  await main().getByText("I've checked these sources", { exact: true }).first().click(); await W(700);
  await shot('s07e_ready');
  await click('Run tests'); await confirmIf('Run tests'); await W(1500);
  await shot('s08_results');
  const step = async (name, confirm) => { await click(name); if (confirm) await confirmIf(name); await W(1500); };
  await step('Fill the gaps');
  await shot('s09a_fill');
  await step('Draft question'); await W(2500);
  await shot('s09b_drafted');
  await step('Mark as sent', true);
  await main().getByRole('button', { name: 'Use the sample reply', exact: true }).first().click(); await W(500);
  await shot('s09c_reply_ready');
  await step('Add reply'); await W(3000);
  await shot('s09d_replied');
  const r = await api('GET', `/cases/${cid}`);
  for (const e of r[1].evidence.filter(e => e.trip_id && e.status === 'needs_decision')) {
    const acc = main().getByRole('button', { name: 'Accept', exact: true }).first();
    if (!(await acc.isVisible().catch(() => false))) { const row = main().getByText(e.claim, { exact: true }).first(); await row.scrollIntoViewIfNeeded(); await row.click(); await W(400); }
    await acc.scrollIntoViewIfNeeded(); await acc.click(); await W(250);
    await p.getByRole('menuitem', { name: "Accept as client's data", exact: true }).first().click().catch(async () => { await p.getByRole('button', { name: "Accept as client's data", exact: true }).last().click(); });
    await W(800);
  }
  await shot('s09e_decided');
  await step('Test again'); await W(1000);
  await shot('s09f_retested');
  await step('Add it up'); await W(3500);
  await shot('s10_answer');
  await step('Stress-test'); await W(800);
  await shot('s11_whatif');
  const sl = main().locator('input[type=range]').nth(4);
  await sl.focus(); for (let i = 0; i < 6; i++) { await p.keyboard.press('ArrowRight'); await W(80); }
  await W(1200);
  await shot('s11b_slider_moved');
  await step('Write conclusion');
  await shot('s12_conclusion');
  await main().locator('textarea').last().fill('Not achievable at the agreed targets: card growth is well below the 20% a year the launch needs. Test a narrower segment before committing.');
  await step('Save conclusion');
  await shot('s12b_saved');
  console.log((await main().innerText()).slice(0, 2500));
  await b.close();
})();
