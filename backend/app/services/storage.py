"""Project-isolated file storage.

Layout:  {DATA_DIR}/projects/{project_id}/
    project.json           status record (written atomically)
    content.pdf            Content Authority upload
    design.pdf             Design Authority upload
    raw/                   raw Gemini responses (debugging)
    analysis.json          validated combined analysis
    skill/document-redesign-specialist/…   generated Skill files
    document-redesign-specialist.zip
"""

import json
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings

_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_lock = threading.Lock()


class ProjectNotFound(LookupError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_project_id() -> str:
    return uuid.uuid4().hex


def is_valid_project_id(project_id: str) -> bool:
    return bool(_ID_RE.fullmatch(project_id or ""))


def project_path(project_id: str) -> Path:
    """Resolve a project directory. Only 32-char hex ids are accepted, so no path traversal is possible."""
    if not is_valid_project_id(project_id):
        raise ProjectNotFound(project_id)
    path = settings.projects_dir / project_id
    if not (path / "project.json").is_file():
        raise ProjectNotFound(project_id)
    return path


def create_project_dir(project_id: str) -> Path:
    if not is_valid_project_id(project_id):
        raise ValueError("invalid project id")
    path = settings.projects_dir / project_id
    path.mkdir(parents=True, exist_ok=False)
    return path


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def read_project(project_id: str) -> dict:
    path = project_path(project_id)
    return json.loads((path / "project.json").read_text(encoding="utf-8"))


def update_project(project_id: str, **changes: Any) -> dict:
    with _lock:
        path = project_path(project_id)
        record = json.loads((path / "project.json").read_text(encoding="utf-8"))
        record.update(changes)
        record["updated_at"] = now_iso()
        write_json_atomic(path / "project.json", record)
        return record


def list_project_ids() -> list[str]:
    if not settings.projects_dir.is_dir():
        return []
    return [p.name for p in settings.projects_dir.iterdir() if is_valid_project_id(p.name) and (p / "project.json").is_file()]
