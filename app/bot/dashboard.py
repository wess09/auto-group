from pathlib import Path
import asyncio

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from nonebot import get_driver

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import init_db
from app.services.group_sync import group_info_sync_loop, member_snapshot_daily_loop


driver = get_driver()


@driver.on_startup
async def start_background_sync_tasks() -> None:
    app = getattr(driver, "server_app", None)
    if app is None or getattr(app.state, "auto_group_sync_tasks_started", False):
        return
    app.state.auto_group_sync_tasks_started = True
    app.state.auto_group_info_sync_task = asyncio.create_task(group_info_sync_loop())
    app.state.auto_group_member_snapshot_task = asyncio.create_task(member_snapshot_daily_loop())


def mount_dashboard() -> None:
    settings = get_settings()
    app = getattr(driver, "server_app", None)
    if app is None:
        return
    if not getattr(app.state, "auto_group_cors_mounted", False):
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials="*" not in settings.cors_origin_list,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Captcha-Verify-Code"],
        )
        app.state.auto_group_cors_mounted = True
    if getattr(app.state, "auto_group_dashboard_mounted", False):
        return

    init_db()
    app.include_router(api_router)
    app.state.auto_group_dashboard_mounted = True

    frontend_dist = Path("frontend/dist")
    admin_prefix = settings.normalized_admin_route_prefix
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


mount_dashboard()
