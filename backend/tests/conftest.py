import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.ai.gemini_client import GeminiError, UploadedFile
from app.config import settings
from app.schemas.analysis import ComparativeAnalysis, ContentAnalysis, DesignAnalysis, StageMetadata
from app.services import jobs
from tests import factories


class FakeGemini:
    """Stands in for GeminiClient: no network, deterministic schema-valid output."""

    model = "fake-gemini-model"
    sdk = "google-genai (mocked)"

    def __init__(self, fail_stage: str | None = None, error: GeminiError | None = None):
        self.fail_stage = fail_stage
        self.error = error or GeminiError("Gemini quota or rate limit exceeded.", kind="quota", status=429)
        self.uploaded: list[str] = []
        self.deleted: list[str] = []
        self.calls: list[str] = []

    def upload_pdf(self, path: Path, display_name: str) -> UploadedFile:
        assert path.is_file()
        name = f"files/{len(self.uploaded) + 1}"
        self.uploaded.append(name)
        return UploadedFile(name=name, uri=f"https://example.invalid/{name}", mime_type="application/pdf")

    def delete_file(self, name: str) -> None:
        self.deleted.append(name)

    def generate_structured(self, *, stage, parts, schema, raw_dir):
        self.calls.append(stage)
        if stage == self.fail_stage:
            raise self.error
        data = {ContentAnalysis: factories.content_analysis, DesignAnalysis: factories.design_analysis, ComparativeAnalysis: factories.comparative_analysis}[schema]()
        meta = StageMetadata(stage=stage, attempts=1, duration_seconds=0.01, finish_reason="STOP", input_tokens=100, output_tokens=200, schema_mode="constrained")
        return data, meta


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "gemini_api_key", "test-key-not-real")
    monkeypatch.setattr(settings, "gemini_model", "fake-gemini-model")
    monkeypatch.setattr(settings, "max_upload_mb", 5)
    return tmp_path / "data"


@pytest.fixture
def fake_gemini():
    holder = {"client": FakeGemini()}
    original = jobs.get_client_factory()
    jobs.set_client_factory(lambda: holder["client"])
    yield holder
    jobs.set_client_factory(original)


@pytest.fixture
def client(data_dir, fake_gemini):
    from app.main import app

    with TestClient(app) as c:
        yield c
    jobs.shutdown()


@pytest.fixture
def pdfs():
    return {"content": factories.make_pdf(2, "Content"), "design": factories.make_pdf(3, "Design")}


def upload(client, content: bytes | None, design: bytes | None, **form):
    files = {}
    if content is not None:
        files["content_pdf"] = ("content.pdf", content, "application/pdf")
    if design is not None:
        files["design_pdf"] = ("design.pdf", design, "application/pdf")
    return client.post("/api/projects", files=files, data=form)


def wait_for(client, project_id: str, timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"/api/projects/{project_id}").json()
        if body["status"] in ("completed", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError("job did not finish")
