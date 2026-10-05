# How to start the build in Claude Code (no coding knowledge needed)

You will unzip this folder, open it in Claude Code, paste one message, and then approve each step before the next one begins.

## What you need
- A Claude subscription (Pro, Max, Team or Enterprise) or a Claude Console account, to run Claude Code itself.
- Python 3.11 or newer and Node.js 20 or newer on your computer, so you can run the app and look at it. If something is missing, Claude Code will tell you and can guide the install.
- Later (Checkpoint 5 onwards): an Anthropic API key (Claude Console), a Tavily key (tavily.com), a GitHub account and a Render account. **Checkpoints 1 to 3 need none of these.**

## 1. Install Claude Code (one time)
- Mac, Linux or WSL: `curl -fsSL https://claude.ai/install.sh | bash`
- Windows PowerShell: `irm https://claude.ai/install.ps1 | iex`
- Check: open a new terminal and run `claude --version`.

## 2. Set up the folder
1. Unzip `research-workbench-build-pack.zip`. You get a folder called `research-workbench-build-pack`.
2. Open a terminal in that folder (`cd` into it).
3. **Optional, 30 seconds, no backend needed:** to see the finished look first, run `node tools/mock_api_server.js 8765` and open http://localhost:8765. Stop it with Ctrl+C.
4. Start Claude Code by typing `claude`. The first time, it opens your browser so you can log in.

## 3. Paste this first message
```
Read CLAUDE.md, then prompts/00_MASTER_BUILD_PROMPT.md completely, then follow its reading order. Follow the approval protocol in CLAUDE.md. Start with Checkpoint 1 only (the rule engine and its tests). Do not start Checkpoint 2 until I type "approve". The front end in frontend/dist is final: do not change it.
```

## 4. How each approval works
1. Claude Code builds the checkpoint, then stops and tells you what it built, the test results and how to look at it.
2. You check it. From Checkpoint 2 you can open the app in your browser at the address it prints (usually http://localhost:8000).
3. Type **approve** to continue, or describe what is wrong and it will fix it and report again.
4. After you approve, type `/clear` to start the next checkpoint with a fresh, cheaper context. `CLAUDE.md` and `PROGRESS.md` let it pick up where it left off.
5. If you hit your usage limit, wait. Later run `claude -c` (continue) or start a new session in the same folder.

## 5. The checkpoints
| Checkpoint | You will see | Needs keys? |
|---|---|---|
| 1 | The rule engine with passing tests and the Sample 1 verdict table | No |
| 2 | The backend running; the checking tool passes; the app opens and loads Sample 1 | No |
| 3 | The real app working through all 12 steps on Sample 1, step by step against the approved screens (**Stage 1 complete**) | No |
| 4 | The live AI and search layer (tested with stand-ins), plus the second sample | No (built with stand-ins) |
| 5 | The deployment package and runbook (**Stage 2 complete**) | You add keys when you deploy |
| 6 | Fixes from your live testing | Yes, live |

## 6. Keys (Checkpoint 5 onwards, never before)
- Copy `.env.example` to a new file called `.env` and fill it in yourself in a text editor. **Never paste a key into the chat.** `.env` is ignored by git.
- Anthropic key and model names: platform.claude.com. Search key: tavily.com.
- On Render you enter the same values in the service's Environment settings; the runbook shows where.

## 7. Deploying (Checkpoint 5 gives you the runbook)
Push the folder to a new GitHub repository, create a Render web service from it using the Dockerfile, add the environment variables, open the app and press **Run checks** in its settings. Every problem shows as a red item with the fix. Then try one live case.

## 8. The roadmap button
The small **Roadmap** button at the top opens `frontend/dist/roadmap.html`. When you have the real roadmap page, replace that file with it (keep the name `roadmap.html`) and redeploy. Or edit `frontend/dist/walkthrough/config.js` and put a full web address in `roadmapUrl`. No code change is needed.

## 9. Tips
- Claude Code may ask permission to run commands. Press `Shift+Tab` to change the mode. The approval protocol makes it stop after each checkpoint either way.
- If a checkpoint goes wrong you can go back: each approved checkpoint is saved as a git tag `checkpoint-N-approved`.
- Ask Claude Code anything in plain words, for example "how do I open the app?"
