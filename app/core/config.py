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
    admin_password: str = "change-this-password"
    admin_route_prefix: str = "/admin"
    frontend_static_enabled: bool = False
    cors_origins: str = "*"
    public_fallback_message: str = "当前没有可加入的群，请稍后再试。"
    upload_dir: str = "./uploads"
    group_sync_interval_seconds: int = 60
    group_sync_concurrency: int = 3
    onebot_api_timeout_seconds: float = 15.0
    group_member_sync_timeout_seconds: float = 300.0
    member_snapshot_daily_time: str = "03:00"
    ws_ping_interval_seconds: float = 20.0
    ws_ping_timeout_seconds: float = 60.0
    login_rate_limit_max_failures: int = 5
    login_rate_limit_window_seconds: int = 15 * 60
    login_rate_limit_lock_seconds: int = 15 * 60
    login_rate_limit_trust_proxy_headers: bool = False

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
