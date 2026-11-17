"""Google Gemini client (official `google-genai` SDK).

Responsibilities: upload PDFs to the Files API, run schema-constrained multimodal generation, retry
transient failures, repair invalid output once, save raw responses, and delete remote files.
Secrets are never logged.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.ai import prompts
from app.config import settings
from app.schemas.analysis import StageMetadata

log = logging.getLogger("app.gemini")

M = TypeVar("M", bound=BaseModel)

RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
MAX_VALIDATION_ATTEMPTS = 2  # first attempt + one controlled repair


class GeminiError(RuntimeError):
    """A Gemini failure with a message that is safe to show to users."""

    def __init__(self, message: str, kind: str = "error", status: int | None = None):
        super().__init__(message)
        self.kind = kind
        self.status = status


@dataclass
class UploadedFile:
    name: str
    uri: str
    mime_type: str

    def as_part(self) -> types.Part:
        return types.Part.from_uri(file_uri=self.uri, mime_type=self.mime_type)


def _sdk_version() -> str:
    try:
        from importlib.metadata import version

        return f"google-genai {version('google-genai')}"
    except Exception:  # pragma: no cover
        return "google-genai"


class GeminiClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: int | None = None,
        max_retries: int | None = None,
        max_output_tokens: int | None = None,
    ):
        api_key = (api_key if api_key is not None else settings.gemini_api_key).strip()
        self.model = (model if model is not None else settings.gemini_model).strip()
        if not api_key:
            raise GeminiError("GEMINI_API_KEY is not configured on the backend.", kind="config")
        if not self.model:
            raise GeminiError("GEMINI_MODEL is not configured on the backend.", kind="config")
        self.timeout_seconds = timeout_seconds or settings.gemini_timeout_seconds
        self.max_retries = settings.gemini_max_retries if max_retries is None else max_retries
        self.max_output_tokens = max_output_tokens or settings.gemini_max_output_tokens
        self.sdk = _sdk_version()
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=self.timeout_seconds * 1000),
        )

    # ------------------------------------------------------------------ files

    def upload_pdf(self, path: Path, display_name: str) -> UploadedFile:
        def _do():
            return self._client.files.upload(
                file=str(path),
                config=types.UploadFileConfig(mime_type="application/pdf", display_name=display_name[:120]),
            )

        f = self._with_retries(_do, what="upload PDF")
        deadline = time.monotonic() + 300
        while f.state == types.FileState.PROCESSING:
            if time.monotonic() > deadline:
                raise GeminiError("Gemini took too long to process the uploaded PDF.", kind="timeout")
            time.sleep(2)
            f = self._with_retries(lambda: self._client.files.get(name=f.name), what="check file status")
        if f.state == types.FileState.FAILED:
            raise GeminiError(f"Gemini could not process the PDF '{display_name}'.", kind="file_failed")
        log.info("Uploaded %s to Gemini Files API as %s", display_name, f.name)
        return UploadedFile(name=f.name, uri=f.uri, mime_type=f.mime_type or "application/pdf")

    def delete_file(self, name: str) -> None:
        try:
            self._client.files.delete(name=name)
        except Exception as exc:  # cleanup must never fail a job; files also expire after 48 h
            log.warning("Could not delete Gemini file %s: %s", name, type(exc).__name__)

    # ------------------------------------------------------------------ generation

    def generate_structured(
        self,
        *,
        stage: str,
        parts: list[types.Part | str],
        schema: type[M],
        raw_dir: Path,
    ) -> tuple[M, StageMetadata]:
        """Generate JSON for `schema`, validate it, and repair once if invalid.

        Raw responses are always saved to `raw_dir` so failures can be debugged.
        """
        raw_dir.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        schema_mode = "constrained"
        contents: list[types.Content] = [types.Content(role="user", parts=[_to_part(p) for p in parts])]
        attempts = 0
        last_error = ""
        in_tok = out_tok = None
        finish = None

        while attempts < MAX_VALIDATION_ATTEMPTS:
            attempts += 1
            try:
                response = self._generate(contents, schema, schema_mode)
            except GeminiError as exc:
                # Some models reject large response schemas; fall back to JSON mode and validate locally.
                if exc.kind == "bad_request" and schema_mode == "constrained" and "schema" in str(exc).lower():
                    log.warning("Stage %s: response schema rejected, retrying in JSON-only mode", stage)
                    schema_mode = "json_only"
                    contents[0].parts.append(types.Part.from_text(text=prompts.json_only_suffix(schema.model_json_schema())))
                    attempts -= 1
                    continue
                raise

            text, finish = _response_text(response)
            usage = getattr(response, "usage_metadata", None)
            in_tok = getattr(usage, "prompt_token_count", None)
            out_tok = getattr(usage, "candidates_token_count", None)
            (raw_dir / f"{stage}-attempt{attempts}.txt").write_text(text or "", encoding="utf-8")

            if finish in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"):
                raise GeminiError(f"Gemini stopped the {stage} analysis (reason: {finish}).", kind="blocked")
            if finish == "MAX_TOKENS":
                raise GeminiError(
                    f"Gemini's {stage} analysis exceeded the output limit ({self.max_output_tokens} tokens). "
                    "Try Standard depth, or raise GEMINI_MAX_OUTPUT_TOKENS if your model supports it.",
                    kind="truncated",
                )
            if not text:
                raise GeminiError(f"Gemini returned an empty response for the {stage} analysis.", kind="empty")

            try:
                obj = schema.model_validate_json(_strip_fences(text))
                meta = StageMetadata(
                    stage=stage,
                    attempts=attempts,
                    duration_seconds=round(time.monotonic() - started, 2),
                    finish_reason=finish,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    schema_mode=schema_mode,
                )
                return obj, meta
            except ValidationError as exc:
                last_error = _summarise_validation(exc)
                log.warning("Stage %s attempt %d failed validation: %s", stage, attempts, last_error[:300])
                contents = contents[:1] + [
                    types.Content(role="model", parts=[types.Part.from_text(text=text)]),
                    types.Content(role="user", parts=[types.Part.from_text(text=prompts.repair_prompt(last_error))]),
                ]

        raise GeminiError(
            f"Gemini's {stage} analysis did not match the required structure after {attempts} attempts. "
            f"Raw responses were saved for debugging. First errors: {last_error[:500]}",
            kind="invalid_output",
        )

    def _generate(self, contents: list[types.Content], schema: type[BaseModel], schema_mode: str):
        config = types.GenerateContentConfig(
            system_instruction=prompts.SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=schema if schema_mode == "constrained" else None,
            max_output_tokens=self.max_output_tokens,
        )
        return self._with_retries(
            lambda: self._client.models.generate_content(model=self.model, contents=contents, config=config),
            what="generate analysis",
        )

    # ------------------------------------------------------------------ retries / errors

    def _with_retries(self, fn, what: str):
        attempt = 0
        while True:
            try:
                return fn()
            except genai_errors.APIError as exc:
                code = getattr(exc, "code", None)
                if code in RETRYABLE_STATUS and attempt < self.max_retries:
                    self._sleep_backoff(attempt, what, f"HTTP {code}")
                    attempt += 1
                    continue
                raise _map_api_error(exc, self.model, what) from exc
            except (httpx.TimeoutException, TimeoutError) as exc:
                if attempt < self.max_retries:
                    self._sleep_backoff(attempt, what, "timeout")
                    attempt += 1
                    continue
                raise GeminiError(
                    f"Gemini timed out while trying to {what} (limit {self.timeout_seconds}s). "
                    "Large documents can take several minutes; raise GEMINI_TIMEOUT_SECONDS if needed.",
                    kind="timeout",
                ) from exc
            except httpx.TransportError as exc:
                if attempt < self.max_retries:
                    self._sleep_backoff(attempt, what, type(exc).__name__)
                    attempt += 1
                    continue
                raise GeminiError("Could not connect to the Gemini API. Check internet access.", kind="network") from exc

    @staticmethod
    def _sleep_backoff(attempt: int, what: str, reason: str) -> None:
        delay = min(60.0, 2.0 * (2**attempt)) + random.uniform(0, 1)
        log.warning("Gemini %s failed (%s); retrying in %.1fs", what, reason, delay)
        time.sleep(delay)


def _map_api_error(exc: genai_errors.APIError, model: str, what: str) -> GeminiError:
    code = getattr(exc, "code", None)
    msg = (getattr(exc, "message", None) or str(exc) or "").strip()[:500]
    if code == 400:
        return GeminiError(f"Gemini rejected the request ({what}): {msg}", kind="bad_request", status=code)
    if code in (401, 403):
        return GeminiError("Gemini rejected the API key (HTTP %s). Check GEMINI_API_KEY." % code, kind="auth", status=code)
    if code == 404:
        return GeminiError(
            f"Gemini model '{model}' was not found or is not available to this key. "
            "Run scripts/list_gemini_models.py and update GEMINI_MODEL.",
            kind="model_not_found",
            status=code,
        )
    if code == 429:
        if "limit: 0" in msg and "free_tier" in msg:
            return GeminiError(
                f"Gemini model '{model}' has no free-tier quota on this API key (limit: 0). "
                "Enable billing for the key's Google Cloud project, or set GEMINI_MODEL to a model your tier allows.",
                kind="quota",
                status=code,
            )
        detail = f" Details: {msg}" if msg else ""
        return GeminiError(f"Gemini quota or rate limit exceeded. Wait and retry, or check your plan's limits.{detail}", kind="quota", status=code)
    return GeminiError(f"Gemini API error HTTP {code} while trying to {what}: {msg}", kind="server", status=code)


def _to_part(p: types.Part | str) -> types.Part:
    return types.Part.from_text(text=p) if isinstance(p, str) else p


def _response_text(response) -> tuple[str, str | None]:
    feedback = getattr(response, "prompt_feedback", None)
    if feedback is not None and getattr(feedback, "block_reason", None):
        reason = getattr(feedback.block_reason, "name", str(feedback.block_reason))
        raise GeminiError(f"Gemini blocked the request (reason: {reason}).", kind="blocked")
    finish = None
    candidates = getattr(response, "candidates", None) or []
    if candidates:
        fr = getattr(candidates[0], "finish_reason", None)
        finish = getattr(fr, "name", None) or (str(fr) if fr is not None else None)
    try:
        text = response.text or ""
    except Exception:
        text = ""
    return text, finish


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def _summarise_validation(exc: ValidationError) -> str:
    lines = []
    for err in exc.errors()[:25]:
        loc = ".".join(str(x) for x in err.get("loc", ()))
        lines.append(f"- {loc or '(root)'}: {err.get('msg')}")
    if exc.error_count() > 25:
        lines.append(f"- … and {exc.error_count() - 25} more")
    return "\n".join(lines)


def list_models(api_key: str | None = None) -> list[dict]:
    """Models available to the key that support generateContent (used by scripts/list_gemini_models.py)."""
    client = genai.Client(api_key=(api_key or settings.gemini_api_key))
    out = []
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or []
        if "generateContent" in actions:
            out.append({"name": (m.name or "").removeprefix("models/"), "display_name": m.display_name})
    return out


__all__ = ["GeminiClient", "GeminiError", "UploadedFile", "list_models"]
