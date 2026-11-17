"""Run the real analysis pipeline once against the live Gemini API, without the web server.

Usage (from backend/):
    python scripts/live_gemini_check.py CONTENT.pdf DESIGN.pdf [--depth standard|deep]

This makes billable Gemini API calls. Output goes to DATA_DIR/projects/<id>/.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.gemini_client import GeminiClient  # noqa: E402
from app.config import settings  # noqa: E402
from app.services import storage  # noqa: E402
from app.services.analysis_service import initial_stages, run_analysis  # noqa: E402
from app.services.pdf_service import inspect_pdf  # noqa: E402
from app.services.skill_generator import OUTPUT_KEYS  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("content")
    ap.add_argument("design")
    ap.add_argument("--depth", choices=["standard", "deep"], default="standard")
    args = ap.parse_args()
    if not settings.gemini_configured:
        print("Set GEMINI_API_KEY and GEMINI_MODEL in backend/.env first.", file=sys.stderr)
        return 1

    pid = storage.new_project_id()
    root = storage.create_project_dir(pid)
    docs = {}
    for role, src in (("content", args.content), ("design", args.design)):
        data = Path(src).read_bytes()
        info = inspect_pdf(data, role)
        (root / f"{role}.pdf").write_bytes(data)
        docs[role] = {"filename": Path(src).name, **info.to_dict()}
    stages = initial_stages()
    stages[0]["status"] = "done"
    storage.write_json_atomic(root / "project.json", {
        "id": pid, "status": "queued", "depth": args.depth, "outputs": list(OUTPUT_KEYS),
        "created_at": storage.now_iso(), "stages": stages, "documents": docs,
        "error": None, "summary": None, "artifacts": {},
    })
    print(f"Project {pid}: running {args.depth} analysis with {settings.gemini_model} …")
    run_analysis(pid, GeminiClient)
    rec = storage.read_project(pid)
    print(json.dumps({k: rec.get(k) for k in ("status", "error", "summary", "artifacts")}, indent=2))
    print(f"Files: {root.resolve()}")
    return 0 if rec["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
