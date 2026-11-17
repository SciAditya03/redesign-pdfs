"""GeminiClient logic with the SDK's network layer replaced by fakes (no API calls)."""

import json
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors as genai_errors
from google.genai import types

from app.ai.gemini_client import GeminiClient, GeminiError
from app.schemas.analysis import ComparativeAnalysis
from tests import factories


def _resp(text: str, finish=types.FinishReason.STOP):
    return SimpleNamespace(
        text=text,
        candidates=[SimpleNamespace(finish_reason=finish)],
        usage_metadata=SimpleNamespace(prompt_token_count=11, candidates_token_count=22),
        prompt_feedback=None,
    )


class FakeModels:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def make_client(monkeypatch):
    monkeypatch.setattr(GeminiClient, "_sleep_backoff", staticmethod(lambda *a, **k: None))

    def _make(script, **kw):
        c = GeminiClient(api_key="test-key", model="test-model", max_retries=kw.get("max_retries", 3))
        fake = FakeModels(script)
        c._client = SimpleNamespace(models=fake)
        return c, fake

    return _make


VALID = factories.comparative_analysis().model_dump_json()


def _run(c, tmp_path):
    return c.generate_structured(stage="comparative", parts=["prompt"], schema=ComparativeAnalysis, raw_dir=tmp_path / "raw")


def test_requires_configuration():
    with pytest.raises(GeminiError) as e:
        GeminiClient(api_key="", model="m")
    assert e.value.kind == "config"
    with pytest.raises(GeminiError) as e:
        GeminiClient(api_key="k", model="  ")
    assert e.value.kind == "config"


def test_success_uses_schema_and_records_metadata(make_client, tmp_path):
    c, fake = make_client([_resp(VALID)])
    obj, meta = _run(c, tmp_path)
    assert isinstance(obj, ComparativeAnalysis)
    assert meta.attempts == 1 and meta.schema_mode == "constrained" and meta.finish_reason == "STOP"
    assert meta.input_tokens == 11 and meta.output_tokens == 22
    cfg = fake.calls[0]["config"]
    assert cfg.response_mime_type == "application/json" and cfg.response_schema is ComparativeAnalysis
    assert fake.calls[0]["model"] == "test-model"
    assert (tmp_path / "raw" / "comparative-attempt1.txt").read_text(encoding="utf-8") == VALID


def test_code_fenced_json_is_accepted(make_client, tmp_path):
    c, _ = make_client([_resp(f"```json\n{VALID}\n```")])
    obj, _ = _run(c, tmp_path)
    assert obj.redesign_strategy.overview


def test_invalid_output_is_repaired_once(make_client, tmp_path):
    broken = json.loads(VALID)
    del broken["redesign_strategy"]
    c, fake = make_client([_resp(json.dumps(broken)), _resp(VALID)])
    obj, meta = _run(c, tmp_path)
    assert meta.attempts == 2
    repair_turn = fake.calls[1]["contents"]
    assert [t.role for t in repair_turn] == ["user", "model", "user"]
    assert "redesign_strategy" in repair_turn[2].parts[0].text
    # Both raw responses are preserved for debugging.
    assert (tmp_path / "raw" / "comparative-attempt1.txt").exists()
    assert (tmp_path / "raw" / "comparative-attempt2.txt").exists()


def test_persistently_invalid_output_fails_without_inventing(make_client, tmp_path):
    c, _ = make_client([_resp('{"nope": 1}'), _resp("not json")])
    with pytest.raises(GeminiError) as e:
        _run(c, tmp_path)
    assert e.value.kind == "invalid_output"


def test_truncated_output(make_client, tmp_path):
    c, _ = make_client([_resp('{"content_to', finish=types.FinishReason.MAX_TOKENS)])
    with pytest.raises(GeminiError) as e:
        _run(c, tmp_path)
    assert e.value.kind == "truncated"


def test_safety_block(make_client, tmp_path):
    c, _ = make_client([_resp("", finish=types.FinishReason.SAFETY)])
    with pytest.raises(GeminiError) as e:
        _run(c, tmp_path)
    assert e.value.kind == "blocked"


def test_rate_limit_is_retried(make_client, tmp_path):
    err = genai_errors.ClientError(429, {"error": {"code": 429, "message": "Resource exhausted", "status": "RESOURCE_EXHAUSTED"}})
    c, fake = make_client([err, genai_errors.ServerError(503, {"error": {"code": 503, "message": "overloaded"}}), _resp(VALID)])
    obj, _ = _run(c, tmp_path)
    assert len(fake.calls) == 3


def test_quota_exhausted_after_retries(make_client, tmp_path):
    err = genai_errors.ClientError(429, {"error": {"code": 429, "message": "quota"}})
    c, _ = make_client([err, err], max_retries=1)
    with pytest.raises(GeminiError) as e:
        _run(c, tmp_path)
    assert e.value.kind == "quota" and e.value.status == 429


@pytest.mark.parametrize("code,kind", [(401, "auth"), (403, "auth"), (404, "model_not_found"), (400, "bad_request")])
def test_non_retryable_errors(make_client, tmp_path, code, kind):
    c, fake = make_client([genai_errors.ClientError(code, {"error": {"code": code, "message": "x"}})])
    with pytest.raises(GeminiError) as e:
        _run(c, tmp_path)
    assert e.value.kind == kind and len(fake.calls) == 1
    assert "test-key" not in str(e.value)


def test_schema_rejection_falls_back_to_json_mode(make_client, tmp_path):
    err = genai_errors.ClientError(400, {"error": {"code": 400, "message": "response_schema too complex"}})
    c, fake = make_client([err, _resp(VALID)])
    obj, meta = _run(c, tmp_path)
    assert meta.schema_mode == "json_only"
    assert fake.calls[1]["config"].response_schema is None
    assert "JSON Schema" in fake.calls[1]["contents"][0].parts[-1].text


def test_timeout_is_retried_then_reported(make_client, tmp_path):
    t = httpx.ReadTimeout("slow")
    c, fake = make_client([t, t], max_retries=1)
    with pytest.raises(GeminiError) as e:
        _run(c, tmp_path)
    assert e.value.kind == "timeout" and len(fake.calls) == 2


def test_upload_waits_for_active_and_delete_is_safe(monkeypatch, tmp_path):
    monkeypatch.setattr("app.ai.gemini_client.time.sleep", lambda s: None)
    states = iter([types.FileState.PROCESSING, types.FileState.ACTIVE])

    class Files:
        deleted = []

        def upload(self, *, file, config):
            assert config.mime_type == "application/pdf"
            return SimpleNamespace(name="files/abc", uri="https://x/files/abc", mime_type="application/pdf", state=next(states))

        def get(self, *, name):
            return SimpleNamespace(name=name, uri="https://x/files/abc", mime_type="application/pdf", state=next(states))

        def delete(self, *, name):
            raise RuntimeError("already gone")

    c = GeminiClient(api_key="k", model="m")
    c._client = SimpleNamespace(files=Files())
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(factories.make_pdf())
    up = c.upload_pdf(pdf, "a.pdf")
    assert up.name == "files/abc" and up.as_part().file_data.file_uri == "https://x/files/abc"
    c.delete_file(up.name)  # must not raise
