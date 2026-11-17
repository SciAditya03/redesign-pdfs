"""Analysis pipeline: Gemini content → design → comparative, then Skill generation.

Progress is persisted to project.json at every stage boundary, so the status the frontend shows is
the real backend state.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable

from app.ai import prompts
from app.ai.gemini_client import GeminiClient, GeminiError, UploadedFile
from app.schemas.analysis import (
    AnalysisResult,
    ComparativeAnalysis,
    ContentAnalysis,
    DesignAnalysis,
    GenerationMetadata,
    ProjectInfo,
    SourceDocument,
)
from app.services import storage
from app.services.skill_generator import SkillGenerationError, build_outputs

log = logging.getLogger("app.analysis")

STAGES: list[tuple[str, str]] = [
    ("validating", "Validating documents"),
    ("preparing", "Preparing PDFs"),
    ("content", "Analysing content authority"),
    ("design", "Analysing design authority"),
    ("comparative", "Performing comparative analysis"),
    ("skill", "Generating Claude Skill"),
    ("downloads", "Preparing downloads"),
]

ClientFactory = Callable[[], GeminiClient]


def initial_stages() -> list[dict]:
    return [{"key": k, "label": label, "status": "pending"} for k, label in STAGES]


def _set_stage(project_id: str, key: str, status: str) -> None:
    record = storage.read_project(project_id)
    stages = record["stages"]
    for s in stages:
        if s["key"] == key:
            s["status"] = status
    storage.update_project(project_id, stages=stages, current_stage=key if status == "running" else record.get("current_stage"))


def _start(project_id: str, key: str) -> None:
    _set_stage(project_id, key, "running")


def _done(project_id: str, key: str) -> None:
    _set_stage(project_id, key, "done")


def summarise(analysis: AnalysisResult) -> dict:
    ca, da, cmp = analysis.content_analysis, analysis.design_analysis, analysis.comparative_analysis
    return {
        "content": {
            "title": ca.document_metadata.title,
            "document_type": ca.document_metadata.document_type,
            "page_count": ca.document_metadata.page_count,
            "sections": len(ca.sections),
            "tables": len(ca.tables),
            "figures": len(ca.figures),
            "terms": len(ca.terminology),
            "preservation_risks": len(ca.preservation_risks),
            "manual_verification": len(ca.manual_verification),
        },
        "design": {
            "colours": len(da.colour_palette),
            "components": len(da.components),
            "archetypes": len(da.page_archetypes),
            "type_levels": len(da.typography.hierarchy),
        },
        "comparative": {
            "mappings": len(cmp.content_to_design_mapping),
            "architecture_pages": len(cmp.proposed_architecture),
            "quality_requirements": len(cmp.quality_requirements),
        },
    }


def run_analysis(project_id: str, client_factory: ClientFactory) -> None:
    """Run the full pipeline for one project. Never raises; failures are recorded in project.json."""
    root = storage.project_path(project_id)
    record = storage.read_project(project_id)
    storage.update_project(project_id, status="running", started_at=storage.now_iso(), error=None)
    uploaded: list[UploadedFile] = []
    client: GeminiClient | None = None
    try:
        depth = record["depth"]
        docs = record["documents"]
        content_doc, design_doc = docs["content"], docs["design"]
        raw_dir = root / "raw"

        _start(project_id, "preparing")
        client = client_factory()
        content_file = client.upload_pdf(root / "content.pdf", content_doc["filename"])
        uploaded.append(content_file)
        design_file = client.upload_pdf(root / "design.pdf", design_doc["filename"])
        uploaded.append(design_file)
        _done(project_id, "preparing")

        stages_meta = []

        _start(project_id, "content")
        content, meta = client.generate_structured(
            stage="content",
            parts=[content_file.as_part(), prompts.content_prompt(depth, content_doc["filename"], content_doc["page_count"])],
            schema=ContentAnalysis,
            raw_dir=raw_dir,
        )
        stages_meta.append(meta)
        storage.write_json_atomic(root / "stage-content.json", content.model_dump(mode="json"))
        _done(project_id, "content")

        _start(project_id, "design")
        design, meta = client.generate_structured(
            stage="design",
            parts=[design_file.as_part(), prompts.design_prompt(depth, design_doc["filename"], design_doc["page_count"])],
            schema=DesignAnalysis,
            raw_dir=raw_dir,
        )
        stages_meta.append(meta)
        storage.write_json_atomic(root / "stage-design.json", design.model_dump(mode="json"))
        _done(project_id, "design")

        _start(project_id, "comparative")
        comparative, meta = client.generate_structured(
            stage="comparative",
            parts=[
                content_file.as_part(),
                design_file.as_part(),
                prompts.comparative_prompt(depth, content.model_dump(mode="json"), design.model_dump(mode="json")),
            ],
            schema=ComparativeAnalysis,
            raw_dir=raw_dir,
        )
        stages_meta.append(meta)
        _done(project_id, "comparative")

        _start(project_id, "skill")
        analysis = AnalysisResult(
            project=ProjectInfo(
                id=project_id,
                depth=depth,
                created_at=record["created_at"],
                documents=[
                    SourceDocument(role="content_authority", filename=content_doc["filename"], page_count=content_doc["page_count"], size_bytes=content_doc["size_bytes"]),
                    SourceDocument(role="design_authority", filename=design_doc["filename"], page_count=design_doc["page_count"], size_bytes=design_doc["size_bytes"]),
                ],
            ),
            content_analysis=content,
            design_analysis=design,
            comparative_analysis=comparative,
            generation_metadata=GenerationMetadata(
                model=client.model,
                sdk=client.sdk,
                started_at=storage.read_project(project_id)["started_at"],
                completed_at=storage.now_iso(),
                stages=stages_meta,
            ),
        )
        # Round-trip validation of the combined document before anything is saved as final.
        analysis = AnalysisResult.model_validate(json.loads(analysis.model_dump_json()))
        storage.write_json_atomic(root / "analysis.json", analysis.model_dump(mode="json"))
        outputs = build_outputs(analysis, record["outputs"], root)
        _done(project_id, "skill")

        _start(project_id, "downloads")
        missing = [k for k, rel in outputs.items() if not (root / rel).is_file()]
        if missing:
            raise SkillGenerationError(f"Generated outputs missing on disk: {missing}")
        _done(project_id, "downloads")

        storage.update_project(
            project_id,
            status="completed",
            completed_at=storage.now_iso(),
            current_stage=None,
            artifacts=outputs,
            summary=summarise(analysis),
        )
        log.info("Project %s completed", project_id)
    except GeminiError as exc:
        _fail(project_id, kind=exc.kind, message=str(exc))
    except SkillGenerationError as exc:
        _fail(project_id, kind="skill_generation", message=str(exc))
    except Exception as exc:  # unexpected: log the traceback server-side, show a safe message
        log.exception("Project %s failed unexpectedly", project_id)
        _fail(project_id, kind="internal", message=f"Unexpected server error ({type(exc).__name__}). See backend logs.")
    finally:
        if client is not None:
            for f in uploaded:
                client.delete_file(f.name)


def _fail(project_id: str, kind: str, message: str) -> None:
    log.warning("Project %s failed (%s): %s", project_id, kind, message)
    try:
        record = storage.read_project(project_id)
        stages = record["stages"]
        for s in stages:
            if s["status"] == "running":
                s["status"] = "failed"
        # A failed job must never look complete: drop any partial artifacts from the record.
        storage.update_project(
            project_id,
            status="failed",
            stages=stages,
            error={"kind": kind, "message": message},
            artifacts={},
            summary=None,
            completed_at=storage.now_iso(),
        )
    except Exception:  # pragma: no cover
        log.exception("Could not record failure for %s", project_id)


def load_analysis(root: Path) -> dict:
    return json.loads((root / "analysis.json").read_text(encoding="utf-8"))
