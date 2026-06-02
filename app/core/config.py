from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Auto Group"
    app_host: str = "127.0.0.1"
    app_port: int = 8080
    database_url: str = "sqlite:///./data/auto_group.db"
    jwt_secret: str = "change-this-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7
    admin_username: str = "admin"
    admin_password: str = "admin123"
    admin_route_prefix: str = "/admin"
    frontend_static_enabled: bool = False
    cors_origins: str = "*"
    public_fallback_message: str = "当前没有可加入的群，请稍后再试。"
    upload_dir: str = "./uploads"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir).resolve()

    @property
    def normalized_admin_route_prefix(self) -> str:
        prefix = self.admin_route_prefix.strip() or "/admin"
        if not prefix.startswith("/"):
            prefix = f"/{prefix}"
        return prefix.rstrip("/") or "/admin"

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return origins or ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
