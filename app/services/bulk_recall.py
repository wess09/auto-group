import asyncio
import re
import time
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any, Protocol

from nonebot import logger
from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.models import AuditLog, RecallAdmin
from app.services.admin import jobs
from app.services.admin.runtime import database
from app.services.message_cache import MESSAGE_CACHE_CAPACITY, cache_io
from app.services.onebot import BotLike


COMMAND = "/大记忆清除数"
DEFAULT_COUNT = 500
active_groups: set[tuple[str, int]] = set()


class RecallBot(BotLike, Protocol):
    self_id: str


@dataclass
class RecallResult:
    requested: int
    selected: int
    succeeded: int = 0
    failed: int = 0
    elapsed_seconds: float = 0


def is_recall_command(text: str) -> bool:
    return re.match(r"^/大记忆清除数(?:\s|$)", text.strip()) is not None


def parse_count(text: str) -> int:
    argument = text.strip()[len(COMMAND) :].strip()
    if not argument:
        return DEFAULT_COUNT
    if not re.fullmatch(r"[0-9]{1,5}", argument):
        raise ValueError("条数必须是 1–20000 的整数")
    count = int(argument)
    if not 1 <= count <= MESSAGE_CACHE_CAPACITY:
        raise ValueError("条数必须是 1–20000 的整数")
    return count


def is_admin(session: Session, user_id: int) -> bool:
    return (
        session.exec(
            select(RecallAdmin.id).where(
                RecallAdmin.user_id == user_id, col(RecallAdmin.enabled).is_(True)
            )
        ).first()
        is not None
    )


@lru_cache
def recall_limit() -> asyncio.Semaphore:
    return asyncio.Semaphore(get_settings().message_recall_concurrency)


async def recall_recent(bot: RecallBot, group_id: int, count: int, before_id: int) -> RecallResult:
    started = time.perf_counter()
    rows = await cache_io("latest", str(bot.self_id), group_id, count, before_id)
    result = RecallResult(requested=count, selected=len(rows))
    pending = iter(rows)
    succeeded: list[int] = []
    settings = get_settings()

    async def worker() -> None:
        # Each worker immediately picks another message after success, error or timeout.
        # A slow request never blocks replenishing the other workers.
        for cache_id, message_id in pending:
            try:
                async with recall_limit():
                    await asyncio.wait_for(
                        bot.call_api(
                            "delete_msg",
                            message_id=message_id,
                            _timeout=settings.message_recall_timeout_seconds,
                        ),
                        timeout=settings.message_recall_timeout_seconds,
                    )
            except Exception:
                result.failed += 1
                continue
            succeeded.append(cache_id)
            result.succeeded += 1

    workers = [
        asyncio.create_task(worker())
        for _ in range(min(settings.message_recall_concurrency, len(rows)))
    ]
    try:
        await asyncio.gather(*workers)
    finally:
        for task in workers:
            if not task.done():
                task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        # Batch updates keep SQLite writes out of the per-message API hot path.
        await cache_io("mark_recalled", succeeded)
    result.elapsed_seconds = round(time.perf_counter() - started, 3)
    return result


async def reply(bot: RecallBot, group_id: int, text: str) -> None:
    try:
        await bot.call_api(
            "send_group_msg",
            group_id=group_id,
            message=[{"type": "text", "data": {"text": text}}],
            _timeout=get_settings().onebot_api_timeout_seconds,
        )
    except Exception as exc:
        logger.warning(f"批量撤回回复失败：group={group_id}, error={type(exc).__name__}")


def save_audit(
    session: Session, bot_id: str, group_id: int, user_id: int, result: RecallResult
) -> None:
    session.add(
        AuditLog(
            action="messages.bulk-recall",
            target=str(group_id),
            detail={"bot_id": bot_id, "operator_qq": user_id, **asdict(result)},
        )
    )
    session.commit()


async def run_command(
    bot: RecallBot, group_id: int, user_id: int, count: int, before_id: int
) -> None:
    key = (str(bot.self_id), group_id)
    try:
        result = await recall_recent(bot, group_id, count, before_id)
        try:
            await database(save_audit, str(bot.self_id), group_id, user_id, result)
        except Exception as exc:
            logger.error(f"批量撤回审计保存失败：group={group_id}, error={type(exc).__name__}")
        text = (
            f"批量撤回完成：成功 {result.succeeded} 条，失败并跳过 {result.failed} 条，"
            f"耗时 {result.elapsed_seconds:.2f} 秒。"
        )
        if result.selected < result.requested:
            text += f"缓存中可尝试撤回的消息只有 {result.selected} 条。"
        await reply(bot, group_id, text)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.error(f"批量撤回任务失败：group={group_id}, error={type(exc).__name__}")
        await reply(bot, group_id, "批量撤回任务异常，已停止；请查看服务日志。")
    finally:
        active_groups.discard(key)


async def handle_message(bot: RecallBot, event: Any) -> bool:
    text = event.get_plaintext()
    command = is_recall_command(text)
    try:
        sequence, created = await cache_io(
            "record",
            str(bot.self_id),
            event.group_id,
            event.message_id,
            event.user_id,
            int(getattr(event, "time", 0)),
            command,
        )
    except Exception as exc:
        logger.error(f"消息缓存写入失败：group={event.group_id}, error={type(exc).__name__}")
        if command:
            await reply(bot, event.group_id, "消息缓存不可用，无法执行批量撤回；请查看服务日志。")
        return command
    if not command or not created:
        return command
    if not await database(is_admin, event.user_id):
        await reply(bot, event.group_id, "你没有批量撤回权限，请在后台添加此 QQ 为撤回管理员。")
        return True
    try:
        count = parse_count(text)
    except ValueError as exc:
        await reply(bot, event.group_id, f"{exc}。用法：{COMMAND} [条数]，默认 500 条。")
        return True
    key = (str(bot.self_id), event.group_id)
    if key in active_groups:
        await reply(bot, event.group_id, "当前群已有批量撤回任务正在执行，请等待完成。")
        return True
    active_groups.add(key)
    task = asyncio.create_task(run_command(bot, event.group_id, event.user_id, count, sequence))
    jobs.tasks.add(task)
    task.add_done_callback(jobs.tasks.discard)
    return True
