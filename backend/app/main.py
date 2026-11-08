from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.routes import router

app = FastAPI(title="AI PDF Redesign Studio API", version="0.1.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/health")
def health():
    return {"status": "ok", "service": "ai-pdf-redesign-studio"}

@app.get("/api/ai-status")
def ai_status():
    return {
        "configured": bool(settings.api_key),
        "provider_base_url": settings.qwen_base_url,
        "model": settings.qwen_model,
        "note": "API key is never returned."
    }
