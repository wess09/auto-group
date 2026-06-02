import asyncio
from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.database import engine
from app.models import ManagedGroup
from app.services.dedupe import refresh_group_members
from app.services.sync import sync_group_info


async def sync_one_group_info(group_id: int) -> bool:
    with Session(engine) as session:
        group = session.exec(select(ManagedGroup).where(ManagedGroup.group_id == group_id)).first()
        if not group:
            return False
        await sync_group_info(session, group)
    return True


async def sync_all_group_info() -> None:
    settings = get_settings()
    with Session(engine) as session:
        group_ids = session.exec(
            select(ManagedGroup.group_id).where(ManagedGroup.enabled == True)  # noqa: E712
        ).all()

    semaphore = asyncio.Semaphore(max(1, settings.group_sync_concurrency))

    async def sync_guarded(group_id: int) -> None:
        async with semaphore:
            try:
                await sync_one_group_info(group_id)
            except Exception:
                pass

    await asyncio.gather(*(sync_guarded(group_id) for group_id in group_ids))


async def sync_all_member_snapshots() -> None:
    with Session(engine) as session:
        groups = session.exec(
            select(ManagedGroup).where(ManagedGroup.enabled == True)  # noqa: E712
        ).all()
        for group in groups:
            try:
                await refresh_group_members(session, group)
            except Exception:
                continue


def _seconds_until_daily_time(value: str) -> float:
    now = datetime.now()
    try:
        hour_text, minute_text = value.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError:
        hour = 3
        minute = 0
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return max(1.0, (target - now).total_seconds())


async def group_info_sync_loop() -> None:
    settings = get_settings()
    while True:
        try:
            await sync_all_group_info()
        except Exception:
            pass
        await asyncio.sleep(max(1, settings.group_sync_interval_seconds))


async def member_snapshot_daily_loop() -> None:
    settings = get_settings()
    while True:
        await asyncio.sleep(_seconds_until_daily_time(settings.member_snapshot_daily_time))
        try:
            await sync_all_member_snapshots()
        except Exception:
            pass
