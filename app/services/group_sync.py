import asyncio
from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import ManagedGroup
from app.services.admin.jobs import sync
from app.services.admin.runtime import database


async def sync_one_group_info(group_id: int) -> bool:
    exists = await database(
        lambda session: session.exec(
            select(ManagedGroup.id).where(ManagedGroup.group_id == group_id)
        ).first()
    )
    if not exists:
        return False
    await sync("groups", group_id)
    return True


def enabled_ids(session: Session) -> list[int]:
    return list(
        session.exec(select(ManagedGroup.group_id).where(ManagedGroup.enabled.is_(True))).all()
    )


async def sync_all_group_info() -> None:
    settings = get_settings()
    group_ids = await database(enabled_ids)

    semaphore = asyncio.Semaphore(max(1, settings.group_sync_concurrency))

    async def sync_guarded(group_id: int) -> None:
        async with semaphore:
            try:
                await sync_one_group_info(group_id)
            except Exception:
                pass

    await asyncio.gather(*(sync_guarded(group_id) for group_id in group_ids))


async def sync_all_member_snapshots() -> None:
    group_ids = await database(enabled_ids)
    for group_id in group_ids:
        try:
            await sync("members", group_id)
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
