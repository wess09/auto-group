from pathlib import Path

import nonebot
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import init_db


def create_app() -> FastAPI:
    settings = get_settings()
    admin_prefix = settings.normalized_admin_route_prefix
    nonebot.init(
        driver="~fastapi",
        host=settings.app_host,
        port=settings.app_port,
        onebot_access_token="",
    )
    driver = nonebot.get_driver()
    driver.register_adapter(OneBotV11Adapter)

    init_db()
    nonebot.load_plugin("app.bot.events")

    app = driver.server_app
    app.title = settings.app_name
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials="*" not in settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    frontend_dist = Path("frontend/dist")
    if settings.frontend_static_enabled and frontend_dist.exists():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

        def frontend_index() -> str:
            return (frontend_dist / "index.html").read_text(encoding="utf-8")

        @app.get(f"{admin_prefix}" + "{path:path}")
        def admin_spa(path: str) -> HTMLResponse:
            del path
            return HTMLResponse(frontend_index())

        @app.get("/join{path:path}")
        def join_spa(path: str) -> HTMLResponse:
            del path
            return HTMLResponse(frontend_index())

        @app.get("/")
        def root() -> dict[str, str]:
            return {
                "public_join": "/join",
                "message": "后台入口已自定义，请访问配置的 ADMIN_ROUTE_PREFIX。",
            }
    else:
        @app.get("/")
        def root() -> dict[str, str]:
            return {
                "name": settings.app_name,
                "message": "Auto Group API is running. Frontend is expected to be served by CDN.",
            }

    return app


app = create_app()


def main() -> None:
    nonebot.run()


if __name__ == "__main__":
    main()
