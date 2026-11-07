from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    # OPENROUTER_API_KEY is preferred. Legacy DASHSCOPE_API_KEY remains supported.
    openrouter_api_key: str = ""
    dashscope_api_key: str = ""
    qwen_base_url: str = "https://openrouter.ai/api/v1"
    qwen_model: str = "qwen/qwen3-vl-235b-a22b-instruct"
    data_dir: Path = Path("./data")
    max_upload_mb: int = 80
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    api_timeout_seconds: int = 180
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @property
    def api_key(self) -> str:
        return self.openrouter_api_key or self.dashscope_api_key

    @property
    def allowed_origins(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
