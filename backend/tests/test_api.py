import io
import json
import zipfile

from app.ai.gemini_client import GeminiError
from app.config import settings
from app.services import jobs, storage
from app.services.skill_generator import REQUIRED_FILES, SKILL_NAME, parse_frontmatter
from tests import factories
from tests.conftest import FakeGemini, upload, wait_for


def test_health_reports_config_without_secrets(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["gemini"] == {"configured": True, "api_key_present": True, "model": "fake-gemini-model"}
    assert "test-key-not-real" not in r.text
    assert client.get("/health").status_code == 200


def test_health_when_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    assert client.get("/api/health").json()["gemini"]["configured"] is False


def test_cors_allows_configured_origin(client):
    r = client.options("/api/health", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
    r = client.options("/api/health", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in r.headers


def test_inspect_valid_pdf(client):
    r = client.post("/api/documents/inspect", files={"file": ("a.pdf", factories.make_pdf(4), "application/pdf")})
    assert r.status_code == 200
    assert r.json()["page_count"] == 4
    assert r.json()["filename"] == "a.pdf"


def test_inspect_rejects_bad_files(client):
    cases = {
        b"": "empty",
        b"hello world": "not a PDF",
        b"%PDF-1.7\n garbage garbage": "could not be opened",
    }
    for data, msg in cases.items():
        r = client.post("/api/documents/inspect", files={"file": ("a.pdf", data, "application/pdf")})
        assert r.status_code == 400, data
        assert msg in r.json()["detail"]
    r = client.post("/api/documents/inspect", files={"file": ("a.pdf", factories.make_pdf(encrypted=True), "application/pdf")})
    assert r.status_code == 400 and "password" in r.json()["detail"]
    r = client.post("/api/documents/inspect", files={"file": ("a.txt", factories.make_pdf(), "text/plain")})
    assert r.status_code == 400 and ".pdf" in r.json()["detail"]


def test_missing_content_pdf(client, pdfs):
    r = upload(client, None, pdfs["design"])
    assert r.status_code == 400
    assert r.json()["detail"] == "Content Authority PDF is required."


def test_missing_design_pdf(client, pdfs):
    r = upload(client, pdfs["content"], None)
    assert r.status_code == 400
    assert r.json()["detail"] == "Design Authority PDF is required."


def test_invalid_pdf_creates_no_project(client, pdfs, data_dir):
    r = upload(client, b"not a pdf", pdfs["design"])
    assert r.status_code == 400 and "Content Authority" in r.json()["detail"]
    assert storage.list_project_ids() == []


def test_oversized_pdf(client, pdfs):
    big = b"%PDF-1.7\n" + b"0" * (6 * 1024 * 1024)
    r = upload(client, big, pdfs["design"])
    assert r.status_code == 413
    assert "5 MB" in r.json()["detail"]


def test_invalid_form_options(client, pdfs):
    assert upload(client, pdfs["content"], pdfs["design"], depth="extreme").status_code == 400
    assert upload(client, pdfs["content"], pdfs["design"], outputs="pptx").status_code == 400


def test_gemini_not_configured_returns_503(client, pdfs, monkeypatch):
    monkeypatch.setattr(settings, "gemini_model", "")
    r = upload(client, pdfs["content"], pdfs["design"])
    assert r.status_code == 503
    assert "GEMINI_MODEL" in r.json()["detail"]
    assert storage.list_project_ids() == []


def test_full_workflow(client, pdfs, data_dir, fake_gemini):
    r = upload(client, pdfs["content"], pdfs["design"])
    assert r.status_code == 202
    created = r.json()
    pid = created["id"]
    assert created["status"] in ("queued", "running", "completed")
    assert created["depth"] == "deep"
    assert created["outputs"] == ["skill_zip", "skill_md", "analysis_json"]
    assert created["documents"]["content"]["page_count"] == 2
    assert created["documents"]["design"]["page_count"] == 3

    body = wait_for(client, pid)
    assert body["status"] == "completed", body["error"]
    assert [s["status"] for s in body["stages"]] == ["done"] * 7
    assert body["summary"]["content"]["sections"] == 2
    assert body["summary"]["design"]["colours"] == 3
    assert set(body["downloads"]) == {"skill_zip", "skill_md", "analysis_json"}

    # Gemini saw both PDFs and every remote file was cleaned up.
    fake = fake_gemini["client"]
    assert fake.calls == ["content", "design", "comparative"]
    assert sorted(fake.deleted) == sorted(fake.uploaded) and len(fake.uploaded) == 2

    # Files are stored inside the project directory.
    root = data_dir / "projects" / pid
    for name in ("project.json", "content.pdf", "design.pdf", "analysis.json", f"{SKILL_NAME}.zip"):
        assert (root / name).is_file(), name

    analysis = client.get(f"/api/projects/{pid}/analysis").json()
    assert set(analysis) == {"project", "content_analysis", "design_analysis", "comparative_analysis", "generation_metadata"}
    assert analysis["design_analysis"]["colour_palette"][1]["hex"] == "#079B4B"  # normalised
    assert analysis["generation_metadata"]["model"] == "fake-gemini-model"

    skill = client.get(f"/api/projects/{pid}/skill")
    assert skill.status_code == 200 and skill.headers["content-type"].startswith("text/markdown")
    assert parse_frontmatter(skill.text)["name"] == SKILL_NAME
    dl = client.get(f"/api/projects/{pid}/skill?download=true")
    assert "attachment" in dl.headers["content-disposition"]

    z = client.get(f"/api/projects/{pid}/download/skill")
    assert z.status_code == 200 and z.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(z.content)) as zf:
        assert zf.testzip() is None
        assert sorted(zf.namelist()) == sorted(f"{SKILL_NAME}/{f}" for f in REQUIRED_FILES)
        assert json.loads(zf.read(f"{SKILL_NAME}/analysis.json"))["project"]["id"] == pid

    a = client.get(f"/api/projects/{pid}/download/analysis")
    assert a.status_code == 200 and "attachment" in a.headers["content-disposition"]
    assert a.json()["project"]["id"] == pid


def test_output_selection_is_honoured(client, pdfs):
    pid = upload(client, pdfs["content"], pdfs["design"], outputs="analysis_json", depth="standard").json()["id"]
    body = wait_for(client, pid)
    assert body["status"] == "completed"
    assert set(body["downloads"]) == {"analysis_json"}
    assert client.get(f"/api/projects/{pid}/download/skill").status_code == 404
    assert client.get(f"/api/projects/{pid}/skill").status_code == 404
    assert client.get(f"/api/projects/{pid}/download/analysis").status_code == 200


def test_gemini_failure_is_recorded(client, pdfs, fake_gemini):
    fake_gemini["client"] = FakeGemini(fail_stage="design")
    pid = upload(client, pdfs["content"], pdfs["design"]).json()["id"]
    body = wait_for(client, pid)
    assert body["status"] == "failed"
    assert body["error"]["kind"] == "quota"
    assert body["downloads"] == {} and body["summary"] is None
    statuses = {s["key"]: s["status"] for s in body["stages"]}
    assert statuses["content"] == "done" and statuses["design"] == "failed" and statuses["skill"] == "pending"
    assert client.get(f"/api/projects/{pid}/analysis").status_code == 409
    assert client.get(f"/api/projects/{pid}/download/skill").status_code == 409
    assert fake_gemini["client"].deleted  # remote files still cleaned up


def test_unexpected_error_gives_safe_message(client, pdfs, fake_gemini):
    class Boom(FakeGemini):
        def upload_pdf(self, path, display_name):
            raise KeyError("secret internals")

    fake_gemini["client"] = Boom()
    body = wait_for(client, upload(client, pdfs["content"], pdfs["design"]).json()["id"])
    assert body["status"] == "failed" and body["error"]["kind"] == "internal"
    assert "secret internals" not in body["error"]["message"]


def test_client_config_error_fails_job(client, pdfs, fake_gemini):
    def factory():
        raise GeminiError("GEMINI_API_KEY is not configured on the backend.", kind="config")

    jobs.set_client_factory(factory)
    body = wait_for(client, upload(client, pdfs["content"], pdfs["design"]).json()["id"])
    assert body["status"] == "failed" and body["error"]["kind"] == "config"


def test_unknown_and_traversal_project_ids(client):
    for pid in ("0" * 32, "..", "..%2F..%2Fetc", "abc", "../../config"):
        assert client.get(f"/api/projects/{pid}").status_code == 404


def test_interrupted_jobs_marked_failed(data_dir):
    pid = storage.new_project_id()
    root = storage.create_project_dir(pid)
    storage.write_json_atomic(root / "project.json", {"id": pid, "status": "running", "stages": [{"key": "content", "status": "running"}]})
    assert jobs.recover_interrupted() == 1
    rec = storage.read_project(pid)
    assert rec["status"] == "failed" and rec["error"]["kind"] == "interrupted"
    assert rec["stages"][0]["status"] == "failed"
