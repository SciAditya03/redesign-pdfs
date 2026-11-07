import base64, json, re
from pathlib import Path
from openai import OpenAI
from openai import APIConnectionError, APIStatusError, APITimeoutError
from app.config import settings
from app.schemas.design import DesignSpec

PROMPT = """You are analysing a visual design reference for a document redesign system.
Inspect the supplied PDF page images and return ONLY valid JSON matching this shape:
{"tokens":{"page_size":"A4","orientation":"portrait","primary_color":"#191F5B","accent_color":"#079B4B","background_color":"#FFFFFF","surface_color":"#EEF0F8","heading_font":"Poppins","body_font":"Inter","label_font":"IBM Plex Mono","style_notes":[]},"page_types":[],"components":{},"observations":[],"confidence_notes":[]}.
Infer only what is visibly supported. Use hex colors where reasonably estimable.
Distinguish observed facts from uncertain guesses in confidence_notes.
Do not invent brand assets or content. Keep page_types concise.
Components should describe reusable visual structures, not page-specific text."""

class QwenUnavailable(RuntimeError):
    pass

def analyse_reference(images: list[Path]) -> DesignSpec:
    if not settings.api_key:
        return DesignSpec(
            observations=["No multimodal API key configured; using starter design tokens."],
            confidence_notes=["Set OPENROUTER_API_KEY (or legacy DASHSCOPE_API_KEY) to enable AI reference analysis."]
        )

    client = OpenAI(
        api_key=settings.api_key,
        base_url=settings.qwen_base_url.rstrip("/"),
        timeout=settings.api_timeout_seconds,
        max_retries=2,
        default_headers={
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "AI PDF Redesign Studio"
        } if "openrouter.ai" in settings.qwen_base_url else None
    )
    content = [{"type": "text", "text": PROMPT}]
    for p in images:
        encoded = base64.b64encode(p.read_bytes()).decode("ascii")
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}
        })

    try:
        response = client.chat.completions.create(
            model=settings.qwen_model,
            messages=[{"role": "user", "content": content}],
            temperature=0.1,
            max_tokens=5000
        )
    except APITimeoutError as exc:
        raise QwenUnavailable("Vision model request timed out. Try fewer reference pages or increase API_TIMEOUT_SECONDS.") from exc
    except APIConnectionError as exc:
        raise QwenUnavailable("Could not connect to the configured AI provider. Check QWEN_BASE_URL and internet access.") from exc
    except APIStatusError as exc:
        body = getattr(exc, "body", None)
        detail = str(body)[:1200] if body else str(exc)[:1200]
        raise QwenUnavailable(f"AI provider returned HTTP {exc.status_code}: {detail}") from exc

    raw = response.choices[0].message.content or ""
    if isinstance(raw, list):
        raw = "".join(part.get("text", "") for part in raw if isinstance(part, dict))
    raw = re.sub(r"^```(?:json)?\\s*|\\s*```$", "", raw.strip(), flags=re.I)
    try:
        data = json.loads(raw)
        return DesignSpec.model_validate(data)
    except Exception as exc:
        raise QwenUnavailable(f"Vision model returned invalid design JSON: {str(exc)[:500]}. Retry analysis or change model.") from exc
