from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import secrets

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VISIONGUARD_", env_file=PROJECT_ROOT / ".env", extra="ignore"
    )

    env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    frontend_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    max_upload_mb: int = Field(default=500, ge=1, le=4096)
    clip_sample_seconds: float = Field(default=1.0, ge=0.2, le=60)
    analysis_fps: float = Field(default=2.0, ge=0.2, le=30)
    pose_fps: float = Field(default=5.0, ge=1, le=30)
    process_width: int = Field(default=640, ge=224, le=1280)
    detection_threshold: float = Field(default=0.45, ge=0.05, le=0.99)
    device: str = "auto"
    auth_secret: str | None = None
    auth_token_minutes: int = Field(default=480, ge=5, le=10080)
    auth_cookie_secure: bool = False
    login_rate_limit_attempts: int = Field(default=5, ge=2, le=100)
    login_rate_limit_window_seconds: int = Field(default=300, ge=10, le=3600)
    database_url: str | None = None
    migration_database_url: str | None = None
    runtime_dir: Path = PROJECT_ROOT / "runtime"
    model_dir: Path = PROJECT_ROOT / "models"

    @field_validator("frontend_origins", mode="before")
    @classmethod
    def parse_origins(cls, value):
        return value.split(",") if isinstance(value, str) else value

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{(self.runtime_dir / 'visionguard.db').as_posix()}"

    @property
    def is_postgresql(self) -> bool:
        return self.db_url.startswith("postgresql")

    def effective_auth_secret(self) -> str:
        if self.auth_secret:
            return self.auth_secret
        if self.env.lower() in {"production", "pilot"}:
            raise RuntimeError("VISIONGUARD_AUTH_SECRET is required outside local development")
        if not hasattr(self, "_development_auth_secret"):
            object.__setattr__(self, "_development_auth_secret", secrets.token_urlsafe(48))
        return self._development_auth_secret

    @property
    def uploads_dir(self) -> Path:
        return self.runtime_dir / "uploads"

    @property
    def frames_dir(self) -> Path:
        return self.runtime_dir / "frames"

    @property
    def embeddings_dir(self) -> Path:
        return self.runtime_dir / "embeddings"

    @property
    def exports_dir(self) -> Path:
        return self.runtime_dir / "exports"

    @property
    def tools_dir(self) -> Path:
        return self.runtime_dir / "tools"

    def ensure_directories(self) -> None:
        for path in (
            self.runtime_dir, self.model_dir, self.uploads_dir, self.frames_dir,
            self.embeddings_dir, self.exports_dir, self.tools_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings

