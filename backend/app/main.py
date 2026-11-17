import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, router
from app.config import settings
from app.services import jobs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.projects_dir.mkdir(parents=True, exist_ok=True)
    jobs.recover_interrupted()
    jobs.start()
    yield
    jobs.shutdown()


app = FastAPI(title="Document Intelligence Studio API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(router)

# Backwards-compatible alias of /api/health.
app.add_api_route("/health", health, methods=["GET"], include_in_schema=False)
