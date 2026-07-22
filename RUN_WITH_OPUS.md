# ▶ RUN THIS PROJECT WITH OPUS 4.8 (local only)

**Human:** open this repo in your editor (VS Code, Cursor, or Visual Studio), open the AI chat,
select the **Opus 4.8** model, and paste this one line:

> **"Read `RUN_WITH_OPUS.md` and run the entire project locally, following every step. Report the results."**

Everything below is written for the AI agent. It is designed to run **100% locally with zero
installs** (the core engine is Python standard library only). Do **not** deploy to or call GCP.

---

## AGENT INSTRUCTIONS — follow in order

### 0. Guardrails (do not violate)
- **Local only.** Never run `gcloud`, `terraform`, or anything under `infra/`. Keep `mode=local`.
- **No dependencies required.** Do not `pip install` anything to complete these steps. The engine is
  stdlib-only. (Optional extras exist but are NOT needed here.)
- **Do not edit** source files unless a step fails and the fix is obvious; if you change anything,
  re-run the tests.
- Prefer the exact commands below. On **Windows**, replace the `PYTHONPATH=src` prefix per §A.

### 1. Confirm the toolchain
```bash
python3 --version      # expect Python 3.9+ (3.11+ ideal)
```
If `python3` is missing, try `python`. Use whichever prints a 3.9+ version for all steps.

### 2. Run the test suite (must be green)
```bash
python3 -m unittest discover -s tests -v
```
**Expected:** the final lines contain `OK` and `Ran 34 tests` (count may grow). If you see
`FAILED`, stop and report the failing test name + traceback.

### 3. Canonicalize the bundled "worst-of-worst" samples (prove the engine)
```bash
PYTHONPATH=src python3 -m canonify run data/samples/worst_case_messy.csv --tenant demo
PYTHONPATH=src python3 -m canonify run data/samples/messy_roster.xlsx     --tenant demo
PYTHONPATH=src python3 -m canonify run data/samples/prompt_injection.csv  --tenant demo
```
**What good looks like:**
- `worst_case_messy.csv` → 5 canonical rows; the JSON summary shows `preprocess` removed junk
  rows/columns and found the header below the title rows; an Excel serial date became `2021-01-01`.
- `messy_roster.xlsx` → 4 rows; Excel serial dates rendered as ISO (`1985-03-14`).
- `prompt_injection.csv` → `security_flags` ≥ 2 (Model Armor local screen caught the injections).

Artifacts are written to `outputs/demo/` (canonical CSV + audit/judge/security/preprocess JSON).
Open `outputs/demo/mapped_data.csv` to show the cleaned, canonical result.

### 4. Start the web UI (the front end)
```bash
PYTHONPATH=src PORT=8000 python3 -m canonify.webapp
```
Then tell the human: **open http://localhost:8000**. In the UI they can upload a CSV/Excel file (or
pick a bundled sample), set a tenant, click **Canonicalize**, and browse the tabs: Canonical Data,
Mapping Audit (with confidence bars), Judge Decisions (color-coded), Review Queue, and Security.
Leave the server running; stop it later with Ctrl+C.

### 5. Report back
Summarize: test result, the three sample runs (rows + notable cleanups + security flags), and the
UI URL. Point out where outputs landed (`outputs/<tenant>/`).

---

## A. Windows / PowerShell equivalents
`PYTHONPATH=src X` doesn't work in PowerShell. Instead:
```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
python -m canonify run data/samples/worst_case_messy.csv --tenant demo
$env:PORT="8000"; python -m canonify.webapp
```
(Visual Studio users: right-click the folder → *Open in Terminal*, then use the commands above. Or
use the built-in configs — see `.vscode/launch.json` and `.vscode/tasks.json`.)

## B. Test the human's OWN files (CSV or Excel)
Two easy ways:
1. **UI:** at http://localhost:8000, click *Upload file* and choose any `.csv`/`.xlsx`.
2. **CLI:** put files anywhere and run:
   ```bash
   PYTHONPATH=src python3 -m canonify run "/path/to/your file.xlsx" --tenant myclient
   ```
Re-running more files for the same `--tenant` makes the system *learn*: previously accepted mappings
are reused, so confidence rises and fewer columns need review (`... dict --tenant myclient` shows the
learned dictionary).

## C. If something fails
| Symptom | Fix |
|---|---|
| `No module named canonify` | You forgot `PYTHONPATH=src` (or `$env:PYTHONPATH="src"`). |
| `python3: command not found` | Use `python` instead. |
| Port 8000 in use | Set a different `PORT`, e.g. `PORT=8090`. |
| A test fails | Report the name + traceback; do not "fix" by deleting the test. |

## D. What NOT to do
- Do **not** run `infra/scripts/gcp_bootstrap.sh`, `terraform`, or set `--mode gcp` (needs cloud
  credentials and is out of scope for a local run).
- Do **not** add third-party packages to make it run — if you think you need one, you've taken a
  wrong turn; the stdlib path works.

---

### Definition of done (agent self-check)
- [ ] `python3 -m unittest discover -s tests` prints `OK`.
- [ ] All three sample `run` commands complete and produce files in `outputs/demo/`.
- [ ] The web UI is reachable at http://localhost:8000 and canonicalizes an uploaded file.
- [ ] You reported the summary back to the human.
