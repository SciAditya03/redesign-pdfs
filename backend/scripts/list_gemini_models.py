"""List Gemini models available to GEMINI_API_KEY that support generateContent.

Usage (from backend/):  python scripts/list_gemini_models.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.gemini_client import list_models  # noqa: E402
from app.config import settings  # noqa: E402


def main() -> int:
    if not settings.gemini_api_key:
        print("GEMINI_API_KEY is not set (backend/.env).", file=sys.stderr)
        return 1
    models = list_models()
    for m in sorted(models, key=lambda m: m["name"]):
        print(f"{m['name']:<45} {m['display_name'] or ''}")
    print(f"\n{len(models)} models. Set GEMINI_MODEL in backend/.env to one of the names above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
