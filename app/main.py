from typing import cast

import nonebot
from fastapi import FastAPI
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

from app.core.config import get_settings


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

    nonebot.load_plugin("app.bot.dashboard")
    nonebot.load_plugin("app.bot.events")

    app = cast(FastAPI, driver.server_app)
    app.title = settings.app_name
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
