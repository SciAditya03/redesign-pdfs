# API Reference

Base URL: `http://localhost:8000`. Interactive docs: `/docs`. Errors return `{"detail": "<message>"}`, and the messages are safe to show to users.

## `GET /api/health`
Never returns secrets. `/health` is an alias.
```json
{"status":"ok","service":"document-intelligence-studio",
 "gemini":{"configured":true,"api_key_present":true,"model":"<GEMINI_MODEL>"},
 "max_upload_mb":50}
```

## `POST /api/documents/inspect`
Validate one PDF without storing it. Multipart field `file`.
`200`: `{"filename","page_count","size_bytes","width_pt","height_pt","text_chars","likely_scanned","title"}`
`400`: missing, not `.pdf`, empty, no `%PDF` header, corrupt, password-protected, or no pages. `413`: over `MAX_UPLOAD_MB`.

## `POST /api/projects`
Create a project and start the analysis. Multipart form:

| Field | Required | Values |
|---|---|---|
| `content_pdf` | yes | PDF file (Content Authority) |
| `design_pdf` | yes | PDF file (Design Authority) |
| `depth` | no | `deep` (default) or `standard` |
| `outputs` | no | comma list of `skill_zip`, `skill_md`, `analysis_json` (default: all) |

`202` returns a Project (below). `400`: a missing file (`"Content Authority PDF is required."`), an invalid PDF, or an invalid option. `413`: too large. `503`: Gemini not configured. No project is created on any error.

## `GET /api/projects/{id}`
```json
{
  "id": "5d69…548f", "status": "queued|running|completed|failed",
  "depth": "deep", "outputs": ["skill_zip","skill_md","analysis_json"],
  "created_at": "…", "updated_at": "…", "started_at": "…", "completed_at": "…",
  "current_stage": "design",
  "stages": [{"key":"validating","label":"Validating documents","status":"done"}, …],
  "documents": {"content": {"filename":"…","page_count":20, …}, "design": {…}},
  "error": null | {"kind":"quota|auth|model_not_found|timeout|truncated|invalid_output|blocked|network|config|interrupted|skill_generation|internal","message":"…"},
  "summary": null | {"content":{…counts}, "design":{…}, "comparative":{…}},
  "downloads": {"skill_zip":"/api/projects/{id}/download/skill", "skill_md":"/api/projects/{id}/skill", "analysis_json":"/api/projects/{id}/download/analysis"}
}
```
Stage keys, in order: `validating`, `preparing`, `content`, `design`, `comparative`, `skill`, `downloads`. Stage status is `pending|running|done|failed`. `downloads` is filled only when `completed`, and only for the selected outputs. `404` for an unknown or malformed id.

## `GET /api/projects/{id}/analysis`
The complete validated `AnalysisResult` JSON: `project`, `content_analysis`, `design_analysis`, `comparative_analysis`, `generation_metadata`. Field definitions are in `backend/app/schemas/analysis.py`. `409` if the project is not completed.

## `GET /api/projects/{id}/skill[?download=true]`
`SKILL.md` as `text/markdown`; with `download=true` it is sent as an attachment. `409` if not completed; `404` if `skill_md` was not selected.

## `GET /api/projects/{id}/download/skill`
`document-redesign-specialist.zip` (`application/zip`). `409` or `404` as above.

## `GET /api/projects/{id}/download/analysis`
`analysis-<id8>.json` attachment. `409` or `404` as above.

## Skill ZIP contents
```
document-redesign-specialist/
  SKILL.md               frontmatter: name, description (validated)
  DESIGN_ANALYSIS.md
  CONTENT_STRUCTURE.md
  REDESIGN_STRATEGY.md
  QUALITY_CHECKLIST.md
  analysis.json
```

## Removed endpoints (previous Qwen/OpenRouter version)
`PUT /api/projects/{id}/design`, `POST /api/projects/{id}/generate`, `GET /api/projects/{id}/download/{pdf|pptx}`, `GET /api/ai-status`. The upload fields `original`/`reference` were renamed to `content_pdf`/`design_pdf`.
