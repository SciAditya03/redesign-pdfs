"""In-process background jobs (thread pool) — no Redis/Celery needed for a single-instance local tool.

Jobs do not survive a restart; on startup any project left queued/running is marked failed so it never
appears to be in progress or complete when it isn't.
"""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor

from app.ai.gemini_client import GeminiClient
from app.config import settings
from app.services import storage
from app.services.analysis_service import ClientFactory, run_analysis

log = logging.getLogger("app.jobs")

_executor: ThreadPoolExecutor | None = None
_client_factory: ClientFactory = GeminiClient


def set_client_factory(factory: ClientFactory) -> None:
    """Override how Gemini clients are created (used by tests)."""
    global _client_factory
    _client_factory = factory


def get_client_factory() -> ClientFactory:
    return _client_factory


def start() -> None:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=max(1, settings.job_workers), thread_name_prefix="analysis")


def shutdown() -> None:
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=False, cancel_futures=True)
        _executor = None


def submit(project_id: str) -> Future:
    start()
    assert _executor is not None
    factory = _client_factory
    return _executor.submit(run_analysis, project_id, factory)


def recover_interrupted() -> int:
    count = 0
    for pid in storage.list_project_ids():
        try:
            rec = storage.read_project(pid)
        except Exception:
            continue
        if rec.get("status") in ("queued", "running"):
            stages = rec.get("stages", [])
            for s in stages:
                if s.get("status") == "running":
                    s["status"] = "failed"
            storage.update_project(
                pid,
                status="failed",
                stages=stages,
                error={"kind": "interrupted", "message": "The backend restarted before this analysis finished. Start a new analysis."},
                artifacts={},
                summary=None,
            )
            count += 1
    if count:
        log.warning("Marked %d interrupted project(s) as failed", count)
    return count
