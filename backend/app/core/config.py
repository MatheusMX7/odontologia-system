from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]  # backend/
ROOT_DIR = BASE_DIR.parent
INSECURE_KEYS = {"troque-esta-chave-antes-de-ir-para-producao", "troque-esta-chave", ""}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/odontologia"
    secret_key: str = "troque-esta-chave-antes-de-ir-para-producao"
    access_token_minutes: int = 480
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    timezone: str = "America/Recife"
    upload_dir: str = "uploads"
    frontend_dir: str = ""
    max_login_attempts: int = 5
    login_lock_minutes: int = 15

    @property
    def upload_path(self) -> Path:
        p = Path(self.upload_dir)
        return p if p.is_absolute() else BASE_DIR / p

    @property
    def frontend_path(self) -> Path:
        return Path(self.frontend_dir) if self.frontend_dir else ROOT_DIR / "frontend"


@lru_cache
def get_settings() -> Settings:
    return Settings()
