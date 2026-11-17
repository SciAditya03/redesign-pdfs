# Implementation Audit — Gemini Document Intelligence Studio

Audit of `SciAditya03/redesign-pdfs` at commit `9f510f1` ("Fixed Version"), performed before any code change on branch `feature/gemini-document-intelligence`.

## 1. Current architecture (as found)

```
backend/            FastAPI, Python ≥3.11
  app/main.py       App, CORS (hard-coded origins), /health, /api/ai-status
  app/config.py     pydantic-settings: OpenRouter/DashScope key, QWEN_* settings, DATA_DIR, MAX_UPLOAD_MB, CORS_ORIGINS
  app/api/routes.py POST /api/projects, GET /api/projects/{id}, PUT …/design, POST …/generate, GET …/download/{pdf|pptx}
  app/ai/qwen_client.py      OpenAI-compatible chat call with up to 6 rasterised reference pages
  app/schemas/design.py      DesignSpec / DesignTokens (flat colour + font tokens)
  app/services/pdf_service.py      PyMuPDF text extraction + page rasterisation
  app/services/content_service.py  Paragraph splitting into hashed content blocks
  app/services/render_service.py   Jinja2 → Playwright PDF, python-pptx PPTX
  app/services/validation_service.py  Substring check of source paragraphs in output PDF
  app/renderer/templates/document.html
frontend/           Next.js 14 App Router, React 18, plain CSS (globals.css), no component library, no tests
  app/page.tsx      Single client component: two <input type=file>, analyse, edit 4 tokens, generate, download
  app/upload/page.tsx  Re-export of the home page
examples/mextropic/ Benchmark fixture (original.pdf, content.json, Claude-redesigned benchmark PDF, images)
tests/test_mextropic_fixture.py  Checks fixture JSON counts (19 categories / 102 items)
docker-compose.yml, backend/Dockerfile (installs Playwright Chromium), frontend/Dockerfile
```

### Existing workflow
1. Upload original + reference PDF in one synchronous request.
2. Extract original text with PyMuPDF; rasterise the first 6 reference pages at 1.25×.
3. Send JPEGs to Qwen (OpenRouter) and parse a small `DesignSpec`. On any error, silently fall back to hard-coded starter tokens (`#191F5B`, Poppins, …).
4. User edits 4 tokens, then the backend renders a generic text-flow PDF (Playwright) and PPTX.
5. Text-containment validation report.

## 2. What works and what doesn't

| Area | State |
|---|---|
| PyMuPDF extraction, page counts, scanned-page heuristic | Works; reusable for upload validation |
| Project-per-UUID directory storage | Works; reusable pattern |
| pydantic-settings config | Works; reusable |
| Next.js shell + CSS tokens | Works; visual language reusable, layout must be rebuilt |
| Mextropic fixture + test | Works; unrelated to new flow, keep |
| Qwen analysis | Sees only 6 low-res screenshots; never sees the PDF itself; tiny schema |
| Fallback to starter tokens on AI failure | **Invents design data** — violates "never invent analysis results" |
| Rendering pipeline | Generic single-template text flow; replaced by Claude executing the Skill |
| CORS | `CORS_ORIGINS` setting is ignored; origins are hard-coded in `main.py` |
| Upload limits | Whole file read into memory before the size check; only the extension is checked (no `%PDF` signature, no parse, no encryption check) |
| Path safety | `project_dir()` accepts any string as an id (path traversal such as `..` is possible) |
| Long requests | Analysis runs inside the POST request: slow model calls hit browser/proxy timeouts |
| Failure records | A project directory is created before validation; failed uploads leave half-written projects |
| `.gitignore` | Ignores `.env.example` and `.env.local.example`, so the README's setup steps reference files that don't exist in the repo |
| Tests | One fixture test; no API tests; no frontend tests |

## 3. Required changes

1. **Replace the Qwen/OpenRouter integration** with the official `google-genai` SDK. Upload both original PDFs through the Gemini Files API (multimodal PDF understanding, not screenshots).
2. **Retire the render pipeline** (Playwright, python-pptx, Jinja2 template, text-containment validator, paragraph content model). In the new architecture, Claude performs the redesign by following the generated Skill. Keeping a second, weaker renderer would confuse users and keep ~300 MB of Chromium in the Docker image. The code remains in git history (`main`, `9f510f1`).
3. **Introduce a three-stage analysis** (content authority → design authority → comparative strategy). Each stage has its own Pydantic schema, uses schema-constrained JSON output, is validated locally, gets one repair retry, and saves its raw responses.
4. **Background jobs with status polling**, using an in-process thread pool and a `project.json` status file. No Redis or Celery. Jobs interrupted by a restart are marked failed on startup.
5. **Skill generator** producing `SKILL.md` (valid YAML frontmatter), 4 supporting Markdown files, `analysis.json`, and a ZIP rooted at `document-redesign-specialist/`.
6. **Hardened uploads**: streamed size limit, `%PDF-` signature, PyMuPDF parse, encryption rejection, empty-file rejection, a page count, and no project created until both files pass.
7. **Strict project-id validation** (UUID hex only) to prevent path traversal.
8. **CORS from settings**; a `/api/health` endpoint that never returns secrets.
9. **Frontend rebuilt** as the Document Intelligence Studio: drag-and-drop upload cards with instant server-side inspection (page count), configuration, real stage progress, results dashboard, and downloads.
10. **Tests**: pytest API and service tests with a mocked Gemini; Vitest + Testing Library for the UI.
11. **Docs**: README, ARCHITECTURE, API_REFERENCE, TEST_REPORT; tracked `.env.example` files.

## 4. Files

**Modify:** `backend/app/config.py`, `backend/app/main.py`, `backend/app/api/routes.py`, `backend/app/services/pdf_service.py`, `backend/requirements.txt`, `backend/pyproject.toml`, `backend/Dockerfile`, `frontend/app/page.tsx`, `frontend/app/layout.tsx`, `frontend/app/globals.css`, `frontend/package.json`, `.gitignore`, `README.md`, `docker-compose.yml`.

**New:** `backend/app/ai/gemini_client.py`, `backend/app/ai/prompts.py`, `backend/app/schemas/analysis.py`, `backend/app/services/storage.py`, `backend/app/services/analysis_service.py`, `backend/app/services/skill_generator.py`, `backend/app/services/jobs.py`, `backend/scripts/list_gemini_models.py`, `backend/scripts/live_gemini_check.py`, `backend/tests/*`, `backend/.env.example`, `frontend/.env.local.example`, `frontend/lib/*`, `frontend/components/*`, `frontend/tests/*`, `frontend/vitest.config.mts`, `docs/*.md`.

**Remove (superseded):** `backend/app/ai/qwen_client.py`, `backend/app/schemas/design.py`, `backend/app/services/render_service.py`, `backend/app/services/validation_service.py`, `backend/app/services/content_service.py`, `backend/app/renderer/templates/document.html`.

**Keep unchanged:** `examples/mextropic/**`, `tests/test_mextropic_fixture.py`, `frontend/app/upload/page.tsx`.

## 5. Dependency changes

- Backend add: `google-genai`. Remove: `openai`, `playwright`, `python-pptx`, `jinja2`, `Pillow`. Dev: `pytest`, `httpx`.
- Frontend dev add: `vitest`, `@vitejs/plugin-react`, `jsdom`, `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`. No runtime additions.

## 6. Integration risks

- **Model IDs change often.** Google's docs list several current IDs and disagree with each other, so no model is hard-coded. `GEMINI_MODEL` is required, and `scripts/list_gemini_models.py` lists the models available to the key.
- **Schema size.** Large nested response schemas can be rejected by the API. Splitting the analysis into three schemas keeps each one small. If the API rejects a schema, the client retries in plain JSON mode and validation still happens locally.
- **Output truncation** on very large documents (`MAX_TOKENS`) is detected and reported, never silently patched.
- **Files API** files expire after 48 h; they are deleted after each job.
- **API contract change.** The upload form fields are renamed (`content_pdf`, `design_pdf`), and the design-edit, generate and PDF/PPTX download endpoints are removed. Old frontends will break; the frontend changes in the same branch.
- **In-process jobs** are lost on restart. This is acceptable for a single-instance local tool and documented.

## 7. Implementation sequence

1. Config, storage, PDF validation.
2. Pydantic analysis schemas and prompts.
3. Gemini client (upload, generate, retries, repair, cleanup).
4. Analysis orchestration, job runner, Skill generator.
5. API routes and health.
6. Backend tests (mocked Gemini).
7. Frontend rebuild and frontend tests.
8. Integration run (both servers, CORS, a real upload against a stubbed Gemini).
9. Documentation and test report.
