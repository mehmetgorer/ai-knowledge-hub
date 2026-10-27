from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

_PACKAGE_DIR = Path(__file__).resolve().parent
_API_ROOT = _PACKAGE_DIR.parent.parent
_REPO_ROOT = _API_ROOT.parent.parent

_ENV_FILES = (
    _REPO_ROOT / ".env",
    _API_ROOT / ".env",
)


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=tuple(str(path) for path in _ENV_FILES if path.is_file())
        or (str(_API_ROOT / ".env"),),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = Field(
        default="ai-knowledge-hub-api",
        validation_alias="SERVICE_NAME",
    )
    cors_origins_raw: str = Field(
        default="http://localhost:3000",
        validation_alias="CORS_ORIGINS",
    )
    api_host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(default=8000, validation_alias="API_PORT")

    database_url: SecretStr | None = Field(
        default=None,
        validation_alias="DATABASE_URL",
    )
    postgres_db: str = Field(
        default="ai_knowledge_hub",
        validation_alias="POSTGRES_DB",
    )
    postgres_user: str = Field(
        default="ai_knowledge_hub",
        validation_alias="POSTGRES_USER",
    )
    postgres_password: SecretStr = Field(
        default=SecretStr("dev_password_change_me"),
        validation_alias="POSTGRES_PASSWORD",
    )
    postgres_host: str = Field(default="127.0.0.1", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5433, validation_alias="POSTGRES_PORT")
    database_connect_timeout: float = Field(
        default=5.0,
        validation_alias="DATABASE_CONNECT_TIMEOUT",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins(self) -> list[str]:
        origins = [
            item.strip() for item in self.cors_origins_raw.split(",") if item.strip()
        ]
        return origins or ["http://localhost:3000"]

    @property
    def resolved_database_url(self) -> str:
        if self.database_url is not None:
            return self.database_url.get_secret_value()
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
