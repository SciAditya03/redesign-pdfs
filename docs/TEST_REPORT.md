# Test Report

Date: 2026-11-18 · Branch `feature/gemini-document-intelligence` · Windows 11, Python 3.13.7, Node 24.12.0, google-genai 3.4.0.

Every result below comes from a run in this session. **No live Gemini API call has been made yet** (no API key was available), so Gemini was mocked or stubbed.

## Summary

| Suite | Command | Result |
|---|---|---|
| Backend unit and API tests (Gemini mocked) | `cd backend; .venv\Scripts\python.exe -m pytest` | **46 passed** |
| Existing fixture test | `backend\.venv\Scripts\python.exe -m pytest tests` (repo root) | **1 passed** |
| Frontend component tests | `cd frontend; npm test` | **11 passed** |
| Frontend type check | `npx tsc --noEmit` | passed |
| Frontend production build | `npm run build` | passed |
| Browser integration (real servers, stubbed Gemini) | see below | passed |
| **Live Gemini analysis** | `scripts/live_gemini_check.py` | **not run: no API key yet** |

## Backend (`backend/tests/`)

- **API** (`test_api.py`, 18 tests): health without secret leakage; health when unconfigured; CORS allow and deny; inspect valid, empty, non-PDF, corrupt, encrypted and wrong-extension files; missing content PDF; missing design PDF; invalid PDF creates no project; oversized PDF → 413; invalid depth and outputs; unconfigured Gemini → 503 with no project created; **full workflow** (202 → all 7 stages `done` → analysis JSON → SKILL.md frontmatter → ZIP with exactly the 6 required files → analysis download; files in `DATA_DIR/projects/<id>/`; both remote Gemini files deleted); output selection honoured; Gemini failure mid-pipeline recorded correctly (failed stage, no downloads, 409 on artifacts, remote cleanup); unexpected exception hides internals; client config error; unknown and path-traversal ids → 404; interrupted-job recovery.
- **Gemini client** (`test_gemini_client.py`, 16 tests, SDK network layer faked): schema-constrained config and metadata; fenced JSON; one repair retry with the validation errors; persistent invalid output fails without filling in data; `MAX_TOKENS` → truncated; safety block; 429/503 retried; quota after retries; 401/403/404/400 mapped without retry and without leaking the key; schema rejection → JSON-only fallback; timeout retry then error; Files API waits for `ACTIVE`; delete failure tolerated.
- **Skill generator** (`test_skill_generator.py`, 12 tests): exact frontmatter; required guidance present; architecture ordered; pipe escaping in tables (this found and fixed a bug where a `|` in an uploaded filename broke the SKILL.md roles table); null HEX shown as "not inferable"; ZIP structure and verification; invalid outputs rejected; frontmatter validator rejects 5 malformed cases; page-range formatting.

## Frontend (`frontend/tests/studio.test.tsx`, 11 tests, `fetch` mocked)

Both upload cards and backend status; upload validation enabling start; server-side and local errors (corrupt, non-PDF, empty; local rejections make no request); replace and remove; start disabled when Gemini is unconfigured; backend offline; **full run**: FormData fields (`content_pdf`, `design_pdf`, `depth`, `outputs`), real stage progress, results tabs rendering backend data, the three download links; inputs locked while running; failed analysis shows its error with no downloads; upload rejection (413) shown; no outputs selected disables start. No React warnings were emitted.

## Browser integration check

Run with the real FastAPI backend and stubbed Gemini (`python -m tests.e2e_server`, 1.5 s per stage) on port 8001, and `npm run dev` with `NEXT_PUBLIC_API_URL=http://localhost:8001`, in the desktop app's browser. Inputs: `examples/mextropic/original.pdf` (content) and `claude_redesign_benchmark.pdf` (design, 5.3 MB).

- Port 3000 was taken by another local app, so Next.js used **3002**. The browser request was correctly blocked until `CORS_ORIGINS` included `http://localhost:3002`; after that, CORS preflight returned the matching `access-control-allow-origin`.
- Both uploads were validated by the backend: **20 pages** and **27 pages** shown.
- Mid-run progress captured as `3/7 stages · Analysing design authority · in progress`; it then completed at `7/7`.
- All three downloads fetched from the page: SKILL.md `text/markdown` 200, analysis.json `application/json` 200, ZIP `application/zip` 200. The ZIP on disk passed `testzip()` and contained the 6 required files with valid frontmatter.
- At 375 px width there was no horizontal page overflow (`scrollWidth == innerWidth`).

## Not yet verified

1. **Live Gemini analysis**: needs `GEMINI_API_KEY` and `GEMINI_MODEL`. Run `scripts/live_gemini_check.py` (above). This will confirm that the chosen model accepts the three response schemas, that real output passes validation, and how long Deep analysis takes on real documents.
2. Docker images were updated but not built in this session.
3. Not tested: macOS/Linux, or browsers other than the desktop app's Chromium.
