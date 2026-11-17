# Document Intelligence Studio

Upload two PDFs: a **Content Authority** (the document whose content must be preserved) and a **Design Authority** (the visual reference). Google Gemini analyses both original PDFs and the app packages the result as a **Claude Skill**. You then upload that Skill to Claude with the two PDFs, and Claude performs the redesign.

```
Content PDF ─┐                                              ┌─ SKILL.md
             ├─► Gemini (multimodal PDF analysis) ─► Skill ─┼─ DESIGN_ANALYSIS.md, CONTENT_STRUCTURE.md,
Design PDF ──┘   content → design → comparative     generator  REDESIGN_STRATEGY.md, QUALITY_CHECKLIST.md
                                                            └─ analysis.json      → ZIP for Claude
```

Gemini is the analysis engine; Claude is the redesign engine. The web app does not render the redesigned PDF itself.

## Features

- Two role-specific upload cards with drag and drop, instant server-side validation (PDF signature, corrupt, encrypted, empty, size), page count, replace and remove.
- Analysis depth: **Deep** (default; every page inventoried, with page-cited evidence) or **Standard**.
- Output selection: Skill ZIP, standalone `SKILL.md`, analysis JSON (all selected by default).
- Three-stage Gemini analysis with schema-constrained JSON, local Pydantic validation, one controlled repair retry, and raw responses saved for debugging. Nothing is invented: unknown values stay `null` and are flagged.
- Background jobs with real stage-by-stage progress (no simulated percentages).
- A results dashboard (content, design, strategy) and working downloads.
- The API key stays on the server and is never returned by any endpoint.

## Requirements

- Python 3.11+ (tested with 3.13)
- Node.js 18.17+ (tested with 24)
- A Google Gemini API key ([Google AI Studio](https://aistudio.google.com/apikey))

## Setup (Windows PowerShell)

### 1. Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env          # set GEMINI_API_KEY
python scripts\list_gemini_models.py   # pick a model from this list
notepad .env          # set GEMINI_MODEL to that model name
uvicorn app.main:app --reload --port 8000
```

Check it: <http://localhost:8000/api/health> should show `"configured": true`. API docs: <http://localhost:8000/docs>.

### 2. Frontend

```powershell
cd frontend
npm install
Copy-Item .env.local.example .env.local
npm run dev
```

Open the URL Next.js prints (normally <http://localhost:3000>). **If port 3000 is busy, Next.js picks 3001, 3002 and so on. Add that origin to `CORS_ORIGINS` in `backend/.env` and restart the backend**, or free port 3000.

macOS/Linux: use `source .venv/bin/activate` and `cp` instead of `Copy-Item`.

## Configuration

`backend/.env` (see [`backend/.env.example`](backend/.env.example)):

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `GEMINI_API_KEY` | yes | — | Gemini API key (server-side only) |
| `GEMINI_MODEL` | yes | — | Model ID. There is deliberately no default, because IDs change often; run `scripts/list_gemini_models.py` |
| `GEMINI_TIMEOUT_SECONDS` | no | 600 | Per-request timeout |
| `GEMINI_MAX_RETRIES` | no | 3 | Retries on 408/429/5xx, timeouts and network errors |
| `GEMINI_MAX_OUTPUT_TOKENS` | no | 65536 | Output cap per stage; lower it if your model's limit is smaller |
| `DATA_DIR` | no | `./data` | Project storage (`DATA_DIR/projects/<id>/`) |
| `MAX_UPLOAD_MB` | no | 50 | Per-file limit (the Gemini Files API allows 50 MB) |
| `CORS_ORIGINS` | no | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated frontend origins |
| `JOB_WORKERS` | no | 2 | Concurrent analyses |

`frontend/.env.local`: `NEXT_PUBLIC_API_URL=http://localhost:8000`. Never put the Gemini key in a `NEXT_PUBLIC_*` variable.

## Using the Studio

1. Drop the **content** PDF on card 01 and the **design** PDF on card 02. Each card shows the file size and page count once the backend has validated it.
2. Choose the depth and outputs, then click **Start analysis**. Deep analysis of long documents can take several minutes.
3. Review the Content, Design and Strategy tabs.
4. Download **Complete Claude Skill ZIP**. In Claude, add the Skill, upload both original PDFs, and ask Claude to redesign the content document.

## Tests

```powershell
cd backend;  .venv\Scripts\python.exe -m pip install -r requirements-dev.txt;  .venv\Scripts\python.exe -m pytest
cd frontend; npm test
```

Gemini is mocked in automated tests, so they need no API key. To try the UI without a key, run `python -m tests.e2e_server` in `backend/` (a stub Gemini on port 8001) and point `NEXT_PUBLIC_API_URL` at it.

**Live check (makes billable Gemini calls):**

```powershell
cd backend
.venv\Scripts\python.exe scripts\live_gemini_check.py ..\examples\mextropic\original.pdf ..\examples\mextropic\claude_redesign_benchmark.pdf --depth standard
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Header shows **Backend offline** | Start the backend; check `NEXT_PUBLIC_API_URL`; restart `npm run dev` after editing `.env.local`. |
| Backend is up but the browser can't reach it | The page's origin (including the port) must be in `CORS_ORIGINS`. Restart the backend after any change. |
| **Gemini not configured** | Set both `GEMINI_API_KEY` and `GEMINI_MODEL`, then restart. |
| "model … not found" | Run `scripts/list_gemini_models.py` and use a listed name. |
| Rate limit / quota | Wait and retry, or check your Gemini plan's limits. |
| "exceeded the output limit" | Use Standard depth, or raise `GEMINI_MAX_OUTPUT_TOKENS` if your model allows it. |
| "did not match the required structure" | Raw responses are in `DATA_DIR/projects/<id>/raw/`. Retry, or try a stronger model. |
| "Analysis interrupted" | The backend restarted mid-job. Start a new analysis. |

## Known limitations

- Jobs run in-process. A backend restart cancels running jobs (they are marked failed). Single instance only.
- No authentication. Project IDs are unguessable, but this is a local or trusted-network tool.
- Uploaded PDFs and results stay in `DATA_DIR` until you delete them.
- Colour HEX values and font names are inferred from rendering, and are marked as estimates or with a confidence level.
- Very long or dense documents may hit the model's output limit at Deep depth.
- Password-protected PDFs are rejected.

## More documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/API_REFERENCE.md](docs/API_REFERENCE.md)
- [docs/IMPLEMENTATION_AUDIT.md](docs/IMPLEMENTATION_AUDIT.md)
- [docs/TEST_REPORT.md](docs/TEST_REPORT.md)

`examples/mextropic/` holds a benchmark pair: the original catalogue and a Claude-redesigned version. It is useful as sample input, and is not used by the application.
