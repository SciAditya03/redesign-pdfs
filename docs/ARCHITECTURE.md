# Architecture

## Components

```
frontend/ (Next.js 14, React 18, plain CSS)
  app/page.tsx              → <Studio/>
  components/Studio.tsx     state, health check, upload inspection, job start, polling
  components/UploadCard.tsx drag & drop, validation feedback, replace/remove
  components/ConfigPanel.tsx depth + outputs
  components/ProgressPanel.tsx real backend stages
  components/Results.tsx    content / design / strategy tabs
  components/Downloads.tsx  links to backend download endpoints
  lib/api.ts                typed API client + analysis types

backend/ (FastAPI)
  app/main.py               app, CORS from settings, lifespan (job pool, crash recovery)
  app/config.py             pydantic-settings (GEMINI_*, DATA_DIR, MAX_UPLOAD_MB, CORS_ORIGINS, JOB_WORKERS)
  app/api/routes.py         HTTP endpoints, upload streaming + validation
  app/services/pdf_service.py      PyMuPDF validation (signature, parse, encryption, pages)
  app/services/storage.py          project dirs, atomic project.json, id validation
  app/services/jobs.py             ThreadPoolExecutor + interrupted-job recovery
  app/services/analysis_service.py the 7-stage pipeline
  app/ai/gemini_client.py          google-genai: Files API, structured generation, retries, repair
  app/ai/prompts.py                system instruction + stage prompts
  app/schemas/analysis.py          Pydantic schemas (stage schemas + combined AnalysisResult)
  app/services/skill_generator.py  Markdown rendering, frontmatter validation, ZIP build/verify
```

## Request flow

1. **Inspect** (optional, per file): `POST /api/documents/inspect` validates one PDF and returns its page count. Nothing is stored.
2. **Create**: `POST /api/projects` streams both uploads with a size cap, validates them, checks that Gemini is configured, and only then creates `DATA_DIR/projects/<32-hex id>/`. It writes `project.json` (status `queued`), submits the job and returns `202`.
3. **Job** (`analysis_service.run_analysis`) moves through these stages, writing `project.json` at every boundary:
   | Stage | Work |
   |---|---|
   | validating | done synchronously in step 2 |
   | preparing | upload both PDFs to the Gemini Files API; wait until `ACTIVE` |
   | content | Gemini call with the content PDF → `ContentAnalysis` |
   | design | Gemini call with the design PDF → `DesignAnalysis` |
   | comparative | Gemini call with **both** PDFs and both validated analyses → `ComparativeAnalysis` |
   | skill | assemble and re-validate `AnalysisResult`, write `analysis.json`, render the Skill files, build and verify the ZIP |
   | downloads | confirm every requested artifact exists |
   Remote Gemini files are deleted in `finally`, whatever the outcome.
4. **Poll**: the frontend calls `GET /api/projects/{id}` every 2 s; on `completed` it fetches `/analysis` for the dashboard.

## Why three Gemini calls

- Each schema stays small enough for constrained decoding (large nested schemas can be rejected).
- Each stage gets the document in its proper role. The design call never sees the content PDF, so design text cannot leak into the content inventory.
- The stages give genuine progress, and errors can be traced to a stage.
- The comparative stage reasons over validated JSON plus the PDFs, rather than re-deriving everything.

## Structured output and validation

- `response_mime_type="application/json"` with `response_schema=<Pydantic class>` (converted by the SDK).
- Every schema field is required; unknowns must be explicit `null` or `[]`, so defaults never invent data.
- Output is validated with Pydantic. On failure, the client sends one repair turn quoting the validation errors. If that also fails, the job fails with `invalid_output`. Each raw attempt is saved to `raw/<stage>-attemptN.txt`.
- If the API rejects the schema (HTTP 400 mentioning "schema"), the client retries in JSON-only mode with the JSON Schema in the prompt, and still validates locally.
- `MAX_TOKENS`, safety blocks and empty responses are reported as errors and never patched.

## Error handling

| Source | Behaviour |
|---|---|
| 408/429/5xx, timeouts, network | exponential backoff with jitter, `GEMINI_MAX_RETRIES` attempts |
| 401/403 | `auth`; 404 → `model_not_found`; 429 after retries → `quota` |
| Unexpected exception | logged with traceback server-side; the user sees a generic message (no internals) |
| Failure at any stage | `status=failed`, the running stage is marked `failed`, `artifacts={}` and `summary=null`, so a failed job never looks complete |
| Backend restart | projects left `queued`/`running` are marked `failed` (`interrupted`) on startup |

## Security

- The Gemini key is read only by the backend. `/api/health` reports presence, never the value; errors never include it.
- Project IDs must match `^[0-9a-f]{32}$` before any path is built, which prevents path traversal. Uploaded filenames are display-only, are never used as paths, and are stripped of control characters.
- Uploads are streamed with a hard size cap, checked for the `%PDF-` signature, parsed, and rejected if encrypted.
- CORS allows only `CORS_ORIGINS`, methods GET/POST, and no credentials.

## Storage layout

```
DATA_DIR/projects/<id>/
  project.json  content.pdf  design.pdf
  stage-content.json  stage-design.json  analysis.json
  raw/<stage>-attemptN.txt
  skill/document-redesign-specialist/{SKILL.md, …}
  document-redesign-specialist.zip
```
