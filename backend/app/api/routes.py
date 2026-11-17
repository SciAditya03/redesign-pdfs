from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, Response

from app.config import settings
from app.services import jobs, storage
from app.services.analysis_service import initial_stages, load_analysis
from app.services.pdf_service import PdfValidationError, inspect_pdf
from app.services.skill_generator import OUTPUT_KEYS, SKILL_NAME

router = APIRouter(prefix="/api")

_CHUNK = 1024 * 1024


# ---------------------------------------------------------------- helpers

def _clean_filename(name: str | None, fallback: str) -> str:
    """Display-only filename: basename, no control characters, bounded length. Never used as a path."""
    base = re.split(r"[\\/]", name or "")[-1]
    base = "".join(ch for ch in unicodedata.normalize("NFC", base) if unicodedata.category(ch)[0] != "C").strip()
    return (base or fallback)[:200]


async def _read_limited(upload: UploadFile, label: str) -> bytes:
    limit = settings.max_upload_bytes
    buf = bytearray()
    while True:
        chunk = await upload.read(_CHUNK)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > limit:
            raise HTTPException(413, f"{label} exceeds the {settings.max_upload_mb} MB upload limit.")
    return bytes(buf)


async def _validated_pdf(upload: Optional[UploadFile], label: str) -> tuple[bytes, dict, str]:
    if upload is None or not upload.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{label} PDF is required.")
    filename = _clean_filename(upload.filename, f"{label.lower().replace(' ', '-')}.pdf")
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{label} must be a .pdf file.")
    data = await _read_limited(upload, label)
    try:
        info = inspect_pdf(data, label)
    except PdfValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return data, info.to_dict(), filename


def _parse_outputs(raw: str | None) -> list[str]:
    if raw is None or not raw.strip():
        return list(OUTPUT_KEYS)
    outputs = [x.strip() for x in raw.split(",") if x.strip()]
    bad = [x for x in outputs if x not in OUTPUT_KEYS]
    if bad or not outputs:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid outputs {bad}. Allowed: {', '.join(OUTPUT_KEYS)}.")
    return list(dict.fromkeys(outputs))


def _public(record: dict) -> dict:
    pid = record["id"]
    artifacts = record.get("artifacts") or {}
    downloads = {}
    if record.get("status") == "completed":
        if "skill_zip" in artifacts:
            downloads["skill_zip"] = f"/api/projects/{pid}/download/skill"
        if "skill_md" in artifacts:
            downloads["skill_md"] = f"/api/projects/{pid}/skill"
        if "analysis_json" in artifacts:
            downloads["analysis_json"] = f"/api/projects/{pid}/download/analysis"
    return {
        "id": pid,
        "status": record["status"],
        "depth": record["depth"],
        "outputs": record["outputs"],
        "created_at": record["created_at"],
        "updated_at": record.get("updated_at"),
        "started_at": record.get("started_at"),
        "completed_at": record.get("completed_at"),
        "current_stage": record.get("current_stage"),
        "stages": record["stages"],
        "documents": record["documents"],
        "error": record.get("error"),
        "summary": record.get("summary"),
        "downloads": downloads,
    }


def _load(project_id: str) -> tuple[dict, Path]:
    try:
        root = storage.project_path(project_id)
        return storage.read_project(project_id), root
    except storage.ProjectNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.") from None


def _require_artifact(record: dict, key: str, label: str) -> str:
    if record["status"] != "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Analysis is {record['status']}; {label} is not available.")
    rel = (record.get("artifacts") or {}).get(key)
    if not rel:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} was not selected as an output for this project.")
    return rel


# ---------------------------------------------------------------- routes

@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "document-intelligence-studio",
        "gemini": {
            "configured": settings.gemini_configured,
            "api_key_present": bool(settings.gemini_api_key.strip()),
            "model": settings.gemini_model or None,
        },
        "max_upload_mb": settings.max_upload_mb,
    }


@router.post("/documents/inspect")
async def inspect_document(file: Optional[UploadFile] = File(None)):
    """Validate a single PDF and return its page count. Nothing is stored."""
    _, info, filename = await _validated_pdf(file, "File")
    return {"filename": filename, **info}


@router.post("/projects", status_code=status.HTTP_202_ACCEPTED)
async def create_project(
    content_pdf: Optional[UploadFile] = File(None),
    design_pdf: Optional[UploadFile] = File(None),
    depth: str = Form("deep"),
    outputs: Optional[str] = Form(None),
):
    if depth not in ("standard", "deep"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "depth must be 'standard' or 'deep'.")
    selected = _parse_outputs(outputs)
    content_data, content_info, content_name = await _validated_pdf(content_pdf, "Content Authority")
    design_data, design_info, design_name = await _validated_pdf(design_pdf, "Design Authority")
    if not settings.gemini_configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Gemini is not configured on the backend. Set GEMINI_API_KEY and GEMINI_MODEL in backend/.env and restart.",
        )

    pid = storage.new_project_id()
    root = storage.create_project_dir(pid)
    try:
        (root / "content.pdf").write_bytes(content_data)
        (root / "design.pdf").write_bytes(design_data)
        stages = initial_stages()
        stages[0]["status"] = "done"  # validation happened above
        now = storage.now_iso()
        record = {
            "id": pid,
            "status": "queued",
            "depth": depth,
            "outputs": selected,
            "created_at": now,
            "updated_at": now,
            "current_stage": None,
            "stages": stages,
            "documents": {
                "content": {"filename": content_name, **content_info},
                "design": {"filename": design_name, **design_info},
            },
            "error": None,
            "summary": None,
            "artifacts": {},
        }
        storage.write_json_atomic(root / "project.json", record)
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise
    jobs.submit(pid)
    return _public(record)


@router.get("/projects/{project_id}")
def get_project(project_id: str):
    record, _ = _load(project_id)
    return _public(record)


@router.get("/projects/{project_id}/analysis")
def get_analysis(project_id: str):
    record, root = _load(project_id)
    if record["status"] != "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Analysis is {record['status']}.")
    return JSONResponse(load_analysis(root))


@router.get("/projects/{project_id}/skill")
def get_skill_md(project_id: str, download: bool = False):
    record, root = _load(project_id)
    rel = _require_artifact(record, "skill_md", "SKILL.md")
    text = (root / rel).read_text(encoding="utf-8")
    headers = {"Content-Disposition": 'attachment; filename="SKILL.md"'} if download else None
    return Response(text, media_type="text/markdown; charset=utf-8", headers=headers)


@router.get("/projects/{project_id}/download/skill")
def download_skill(project_id: str):
    record, root = _load(project_id)
    rel = _require_artifact(record, "skill_zip", "The Skill ZIP")
    return FileResponse(root / rel, media_type="application/zip", filename=f"{SKILL_NAME}.zip")


@router.get("/projects/{project_id}/download/analysis")
def download_analysis(project_id: str):
    record, root = _load(project_id)
    rel = _require_artifact(record, "analysis_json", "The analysis JSON")
    return FileResponse(root / rel, media_type="application/json", filename=f"analysis-{project_id[:8]}.json")
