# Runbook: put Research Workbench online (Render, about 20 minutes, no coding)

You need: a GitHub account (the code is already in `nakulvashishtha/Thoucentric_v3`), a Render account (render.com, sign in
with GitHub), an Anthropic API key (platform.claude.com) and a Tavily key (tavily.com, free plan). **Never paste a key into a
chat, a file in the repository, or an email.** You type keys only into Render's Environment page.

## 1. Get the two keys (5 minutes)
1. **Anthropic:** platform.claude.com → sign in → *Settings → Billing*: add a small credit (10 USD is plenty for rehearsals)
   and set a **monthly spend limit** (for example 25 USD). Keep auto-reload **off**. Then *API keys → Create key*, name it
   `workbench-demo`, copy it somewhere private for the next 10 minutes.
2. **Model names:** in the Console open *Models* and confirm the exact IDs. Use the current Haiku for `MODEL_FAST`
   (for example `claude-haiku-4-5`) and the current Sonnet for `MODEL_SMART` (for example `claude-sonnet-5-5`).
3. **Tavily:** tavily.com → sign up → copy the API key from the dashboard (the free plan gives 1,000 searches a month;
   a case uses about 10 to 15).

## 2. Create the service on Render (5 minutes)
1. render.com → **New + → Blueprint**. Connect GitHub and choose the repository `Thoucentric_v3`.
   - The code is on branch `claude/theocentric-competition-product-42frzm`. Either pick that branch in Render, or merge it
     into `main` first on GitHub (*Pull requests → New → merge*).
2. Render reads `render.yaml` and shows one web service, `research-workbench`, built from the `Dockerfile`. Click **Apply**.
3. It asks for the three secret values. Paste them: `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, and `ADMIN_PASSCODE`
   (any phrase you choose; everyone who opens the app needs it). The other settings are filled in already:
   `MODEL_FAST=claude-haiku-4-5`, `MODEL_SMART=claude-sonnet-5-5`, `MODE=live`, `DAILY_SPEND_CAP=5`,
   `MAX_LLM_CALLS_PER_CASE=150`, `DATA_DIR=/app/data`. Change the two model names if the Console showed different IDs.
4. Wait for the first deploy (3 to 6 minutes). The log ends with `Uvicorn running on http://0.0.0.0:...`.

*Without the Blueprint:* **New + → Web Service** → the repository → Runtime **Docker** → Instance type **Free** →
*Advanced → Health Check Path* `/healthz` → add the environment variables above by hand → **Create Web Service**.

## 3. Check it (2 minutes)
1. Open `https://<your-service>.onrender.com/healthz`. It shows `{"ok":true}`.
2. Open `https://<your-service>.onrender.com`. Click **Start the walkthrough**, type the passcode, click **Open workbench**.
3. **Settings → Run checks.** Every line should be green. Anything red shows the exact fix, for example:
   - *AI model in MODEL_FAST works* is red → the model name is wrong. Correct it in Render → *Environment* → **Save changes**
     (Render restarts the app by itself), then run the checks again.
   - *Search key works* is red → paste the Tavily key again without spaces.
   - *Passcode is set* is red → add `ADMIN_PASSCODE`.
4. **Smoke test:** click **Try a sample** (credit card, India) and use **Settings → Skip to step** 12. Then do one live
   blank case: **Start a case**, fill the five fields, paste a real ask, click **Check the ask**, and walk it to step 12.
   Steps 5 and 6 should finish in about a minute and a half. Settings shows what the case cost (about 0.50 USD).

## 4. Hosting and cost (put this in the calendar)
- **Rehearsals: Free instance.** It sleeps after 15 minutes idle and the first visit then takes about a minute to wake.
  It has **no disk: cases are lost when it restarts or redeploys.** Samples reload instantly; to keep a live case, use
  **Download JSON** on step 12 and **Import a case** on the home page later.
- **Open the URL 5 minutes before you present** so it is awake. Optional: a free uptime pinger (for example
  UptimeRobot, every 10 minutes on `/healthz`) keeps it awake.
- **Pitch week: switch to Starter** (Render → *Settings → Instance type*, about 7 USD a month) so it never sleeps.
  Do **not** buy a persistent disk. After the event, suspend or delete the service and delete both API keys.
- AI cost is about 0.50 USD per live case; the app stops at `DAILY_SPEND_CAP` (5 USD a day) and 150 AI calls per case,
  and shows a red banner. Raise the cap in *Environment* on rehearsal days if you need to.

## 5. On the day
- **Reset a case:** Settings → *Reset case* (samples go back to step 1). **Delete:** the home page list.
- **History:** the History drawer in a case → **Export CSV**.
- **If the AI or search service is slow or failing:** open a sample case. It is **Demo data mode**, which uses stored
  answers and needs no keys. If a live sample case fails twice, a red banner offers **Use demo data** for that case. Say
  so openly. To force the whole app into demo data, set `MODE=fixtures` in Render → Environment.
- **Roadmap button:** replace `frontend/dist/roadmap.html` with your roadmap page (keep the name), commit and push;
  Render redeploys. Or set `roadmapUrl` in `frontend/dist/walkthrough/config.js` to a full web address.

## 6. Run it on your own computer (optional)
Python 3.11+: `pip install -r requirements-dev.txt`, copy `.env.example` to `.env` and fill it in (or leave it empty for
demo data), then `make run` and open http://localhost:8000. `make test` runs the tests (no keys, no real calls).

## Alternatives to Render (not tested)
- **Railway:** New Project → Deploy from GitHub repo (it finds the Dockerfile) → add the same variables → Generate Domain.
  Free trial credit, then usage-based.
- **Fly.io:** install `flyctl`, run `fly launch` in the repository (it uses the Dockerfile), `fly secrets set` for the
  keys, then `fly deploy`. Needs a card; a small machine costs a few dollars a month.
