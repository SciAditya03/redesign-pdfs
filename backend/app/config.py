from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Backend configuration. Values come from environment variables or backend/.env.

    Secrets (GEMINI_API_KEY) are only ever read on the server and are never returned by any endpoint.
    """

    gemini_api_key: str = ""
    # Deliberately no default: Gemini model IDs change frequently. Run scripts/list_gemini_models.py.
    gemini_model: str = ""
    gemini_timeout_seconds: int = 600
    gemini_max_retries: int = 3
    gemini_max_output_tokens: int = 65536

    data_dir: Path = Path("./data")
    # Gemini's Files API accepts PDFs up to 50 MB.
    max_upload_mb: int = 50
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    job_workers: int = 2

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key.strip()) and bool(self.gemini_model.strip())

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def allowed_origins(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    @property
    def projects_dir(self) -> Path:
        return self.data_dir / "projects"


settings = Settings()
