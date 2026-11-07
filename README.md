# AI PDF Redesign Studio

A reference-guided document redesign starter: upload an original PDF and a visual-reference PDF, analyse them with a Qwen-compatible API, review a design specification, and generate PDF + editable PPTX outputs.

## Architecture

- `frontend/`: Next.js App Router UI (upload, analysis, preview, export entry points).
- `backend/`: FastAPI API, PyMuPDF extraction, Qwen-compatible multimodal analysis, HTML/CSS PDF renderer, PPTX exporter, integrity checks.
- `examples/mextropic/`: benchmark fixture from the supplied prototype and PDFs. The extracted `content.json` contains 19 categories and 102 assay entries.

## Run locally

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set OPENROUTER_API_KEY in .env (recommended) and optionally QWEN_MODEL
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open http://localhost:3000. Backend docs: http://localhost:8000/docs.

## Qwen configuration

The backend uses the OpenAI-compatible Chat Completions interface. Configure the endpoint and model for the Qwen service/account you use. For DashScope, set `QWEN_BASE_URL` to the compatible-mode endpoint for your region and `QWEN_MODEL` to a vision-capable Qwen model available to your account. Never put the API key in `NEXT_PUBLIC_*` variables.

## Current MVP scope

- Uploads are saved locally under `backend/data/` (development only).
- Original PDF text is extracted with PyMuPDF and assigned stable content IDs.
- Reference pages are rasterized and sent to Qwen for design-system analysis.
- The design JSON is schema-validated and editable in the UI.
- PDF is rendered from HTML/CSS with Playwright; PPTX is generated with python-pptx.
- A deterministic text-integrity report compares extracted source text against the generated PDF text.

## Important limitations

This is the first working vertical slice, not a production-ready document reconstruction engine. Scanned PDFs need OCR; complex tables, charts, equations, and source PDFs with unusual reading order require specialised handling. Qwen output is advisory: the renderer uses validated design tokens and never lets the model rewrite source content. The included Mextropic fixture is for regression testing and is not hardcoded into the generic upload workflow.


## Recommended cloud configuration: OpenRouter + Qwen vision

Use the OpenAI-compatible **versioned API root**, not the website root:

```env
OPENROUTER_API_KEY=sk-or-v1-your_key
QWEN_BASE_URL=https://openrouter.ai/api/v1
QWEN_MODEL=qwen/qwen3-vl-235b-a22b-instruct
DATA_DIR=./data
MAX_UPLOAD_MB=80
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
API_TIMEOUT_SECONDS=180
```

The OpenAI Python SDK appends `/chat/completions`, so do not put that path in `QWEN_BASE_URL`.
The configured model must support image input. Check the current OpenRouter model catalogue before switching model IDs.

Legacy DashScope configuration is still supported with `DASHSCOPE_API_KEY`, its regional compatible-mode `/v1` URL, and a vision-capable Qwen model.

## Troubleshooting "Failed to fetch"

1. Start the backend and confirm `http://localhost:8000/health` returns `{"status":"ok",...}`.
2. Confirm `http://localhost:8000/api/ai-status` reports `configured: true`.
3. Keep the frontend origin in `CORS_ORIGINS`; restart the backend after changing `.env`.
4. Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `frontend/.env.local`, then restart Next.js.
5. A browser "Failed to fetch" usually means the browser could not reach the backend or the request was blocked by CORS. An upstream model error normally appears as an HTTP response from the backend. Inspect the backend terminal for the provider's detailed error.
