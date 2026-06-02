from pathlib import Path

import nonebot
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import init_db


def create_app() -> FastAPI:
    settings = get_settings()
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
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    frontend_dist = Path("frontend/dist")
    if frontend_dist.exists():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

        @app.get("/admin{path:path}")
        def admin_spa(path: str) -> FileResponse:
            del path
            return FileResponse(frontend_dist / "index.html")

        @app.get("/join{path:path}")
        def join_spa(path: str) -> FileResponse:
            del path
            return FileResponse(frontend_dist / "index.html")

        @app.get("/login{path:path}")
        def login_spa(path: str) -> FileResponse:
            del path
            return FileResponse(frontend_dist / "index.html")

        @app.get("/")
        def root() -> FileResponse:
            return FileResponse(frontend_dist / "index.html")

    return app


app = create_app()


def main() -> None:
    nonebot.run()


if __name__ == "__main__":
    main()
