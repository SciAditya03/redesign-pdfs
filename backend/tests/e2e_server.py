"""Run the real backend with a stubbed Gemini client, for browser/integration checks without an API key.

Usage (from backend/):  python -m tests.e2e_server [--port 8001] [--delay 1.5]
Not for production. Data goes to ./data-e2e.
"""

import argparse
import os
import time

os.environ.setdefault("GEMINI_API_KEY", "stub-key-not-real")
os.environ.setdefault("GEMINI_MODEL", "stub-gemini (no API calls)")
os.environ.setdefault("DATA_DIR", "./data-e2e")

import uvicorn  # noqa: E402

from app.services import jobs  # noqa: E402
from tests.conftest import FakeGemini  # noqa: E402


class SlowFake(FakeGemini):
    delay = 1.5

    def generate_structured(self, **kw):
        time.sleep(self.delay)
        return super().generate_structured(**kw)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--delay", type=float, default=1.5)
    args = ap.parse_args()
    SlowFake.delay = args.delay
    jobs.set_client_factory(SlowFake)
    from app.main import app

    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
