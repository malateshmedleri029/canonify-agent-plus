# Developer Guide

How to download, open, run, and extend Canonify Agent+ — locally, in VS Code / Cursor / Visual
Studio. The core runs on the **Python standard library**, so local development needs **no installs**.

> Just want an AI (Opus 4.8) to run the whole thing for you? See [`../RUN_WITH_OPUS.md`](../RUN_WITH_OPUS.md).

## 1. Prerequisites
- **Python 3.9+** (3.11+ recommended). Check: `python3 --version`.
- **Git**.
- An editor: **VS Code** (recommended), **Cursor**, or **Visual Studio**.
- (Optional) `gcloud` + `terraform` only if you deploy to GCP.

## 2. Get the code
```bash
git clone https://github.com/malateshmedleri029/canonify-agent-plus.git
cd canonify-agent-plus
```
In VS Code / Cursor you can also use `Cmd/Ctrl+Shift+P` → **Git: Clone** and paste the URL above.

## 3. Open in your editor
- **VS Code / Cursor:** `code .` (or *File → Open Folder*). Accept the recommended extensions prompt
  (Python, Pylance, Markdown Mermaid, Copilot). The bundled `.vscode/` sets `PYTHONPATH=src`,
  enables the unittest runner, and adds Run/Debug configs and Tasks.
- **Visual Studio:** *File → Open → Folder…* and pick the repo. Use the integrated terminal for the
  commands below.

## 4. Run it locally (no install)
```bash
# tests
python3 -m unittest discover -s tests -v

# canonicalize a messy file (CSV or Excel)
PYTHONPATH=src python3 -m canonify run data/samples/worst_case_messy.csv --tenant acme

# launch the web UI, then open http://localhost:8000
PYTHONPATH=src PORT=8000 python3 -m canonify.webapp
```
On **Windows PowerShell**, set the path first: `$env:PYTHONPATH="src"` then run without the prefix.

### Optional: install as a package
```bash
python3 -m pip install -e .          # gives you the `canonify` command (no PYTHONPATH needed)
python3 -m pip install -e ".[dev]"   # + pytest + pyyaml
python3 -m pip install -e ".[gcp]"   # + Vertex AI / BigQuery / Storage (for --mode gcp)
```

## 5. Debug in VS Code
Press **F5** and choose:
- **Canonify: Web UI** — runs the server with the debugger attached.
- **Canonify: Run a file (CLI)** — prompts for a file path and canonicalizes it.

Or open the Command Palette → *Tasks: Run Task* → pick a Canonify task.

## 6. Using Opus 4.8 in the editor
- **Cursor:** open chat (⌘/Ctrl-L), pick **Opus 4.8** in the model selector, and reference files with
  `@RUN_WITH_OPUS.md`. The repo's `.github/copilot-instructions.md` is auto-respected.
- **VS Code + Copilot Chat:** open Chat, choose Opus 4.8 in the model picker, and say
  *"Read RUN_WITH_OPUS.md and run the project locally."* Copilot reads
  `.github/copilot-instructions.md` for repo conventions.

## 7. Test YOUR own files
- Drop `.csv` / `.xlsx` anywhere and run `... canonify run "<path>" --tenant <name>`, or upload them
  in the web UI.
- Reusing the same `--tenant` triggers the **learning loop**: accepted mappings are remembered, so
  later files score higher. Inspect with `... canonify dict --tenant <name>`.

## 8. Project layout
```
src/canonify/
  io_readers.py     # robust CSV + stdlib .xlsx readers (encoding/delimiter/serial-date)
  preprocess.py     # worst-of-worst cleanup + header detection
  pipeline.py       # orchestrates the agentic loop
  agents/           # mapper, transformer, judge, persister (+ *_gcp sinks)
  rag/              # learned dictionary + SOP retrieval (+ featurestore)
  llm/              # gemini.py (+ model_armor.py security screening)
  webapp.py         # stdlib web UI + JSON API
  web/index.html    # the front end
data/               # canonical_schema.{json,yaml}, sop/, samples/
tests/              # stdlib unittest suite
infra/              # Terraform + bootstrap (GCP)
docs/               # problem statement, MVP plan, architecture (+ E2E), GCP setup, this guide
```

## 9. Extend it
- **New use case / schema:** add `data/<name>_schema.json` and `data/sop/<name>_sop.md`. No engine
  changes — the schema is data. Point the run at it with `--schema data/<name>_schema.json`.
- **New cell transform:** add a branch in `agents/transformer.py` keyed on the field `type`.
- **Tune governance:** edit `thresholds` in the schema (accept / review / sensitive_bonus).
- **Always:** every mapping/transform must carry a confidence + explanation, and sensitive fields
  must never be silently inferred. Keep the core stdlib-only. Run the tests before finishing.

## 10. Push your changes to GitHub

The repo lives at **https://github.com/malateshmedleri029/canonify-agent-plus**.

### First-time setup (authentication — pick ONE)
- **Cursor / VS Code (easiest):** connect your GitHub account in the editor, then use the
  **Source Control** panel (⌃⇧G) — *Commit* → *Sync/Push*. The editor handles auth.
- **GitHub CLI:** `brew install gh && gh auth login` (once). Future pushes just work.
- **Personal Access Token:** create one at <https://github.com/settings/tokens> with the `repo`
  scope; the first `git push` will prompt for it (username = your GitHub handle, password = token).
  On macOS it's then cached in the keychain.

### The everyday loop
```bash
# 1. work on a branch (don't commit straight to main for shared repos)
git checkout -b feature/my-change

# 2. ALWAYS run the tests before committing
python3 -m unittest discover -s tests

# 3. stage + commit
git add -A
git commit -m "feat: describe what you changed"

# 4. push the branch
git push -u origin feature/my-change

# 5. open a Pull Request (from the link git prints, or on GitHub) and let CI run
```

Pushing to `main` directly (if you have rights):
```bash
git checkout main && git pull   # sync first
git add -A && git commit -m "your message" && git push
```

### Notes
- CI (`.github/workflows/ci.yml`) runs the test suite on every push/PR across Python 3.9/3.11/3.12.
- `.gitignore` already excludes `outputs/`, `data/dictionary/`, and Terraform state — never force-add
  them. Never commit secrets or a `.env`.
- If `git push` says *"Repository not found"*, the remote/repo name is wrong or you're not
  authenticated — re-check `git remote -v` and your auth method above.

## 11. Deploy to GCP (optional)
See [`GCP_SETUP.md`](./GCP_SETUP.md). One command: `./infra/scripts/gcp_bootstrap.sh`.
