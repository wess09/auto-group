from typing import Any

import asyncio

from nonebot import on_message, on_notice, on_request
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    GroupRequestEvent,
    NoticeEvent,
)

from app.services.group_sync import sync_one_group_info
from app.services.message_moderation import moderate_group_message_detached
from app.services.join_requests import process_join_request
from app.services.admin import bot_data, jobs
from app.services.admin.runtime import database


def event_to_dict(event: Any) -> dict[str, Any]:
    if hasattr(event, "model_dump"):
        return event.model_dump(mode="json")
    if hasattr(event, "dict"):
        return event.dict()
    return {}


def extract_answer(comment: str) -> str:
    if not comment:
        return ""
    # OneBot v11 usually puts question/answer text inside comment. Keep this
    # permissive because clients format request comments differently.
    markers = ["答案：", "答案:", "回答：", "回答:", "answer:"]
    for marker in markers:
        if marker in comment:
            return comment.split(marker, 1)[1].strip()
    return comment.strip()


request_matcher = on_request(priority=5, block=False)
notice_matcher = on_notice(priority=5, block=False)
message_matcher = on_message(priority=99, block=False)


async def sync_group_info_safely(group_id: int) -> None:
    try:
        await sync_one_group_info(group_id)
    except Exception:
        pass


@request_matcher.handle()
async def handle_group_request(bot: Bot, event: GroupRequestEvent) -> None:
    if event.request_type != "group" or event.sub_type != "add":
        return
    answer = extract_answer(getattr(event, "comment", "") or "")
    await process_join_request(
        bot,
        {
            "flag": event.flag,
            "group_id": event.group_id,
            "user_id": event.user_id,
            "answer_text": answer,
            "raw_event": event_to_dict(event),
        },
        event.sub_type,
    )


activity_lock = asyncio.Lock()


@message_matcher.handle()
async def handle_group_message(event: GroupMessageEvent) -> None:
    sender = getattr(event, "sender", None)
    async with activity_lock:
        managed = await database(
            bot_data.record_activity,
            event.group_id,
            event.user_id,
            getattr(sender, "nickname", ""),
            getattr(sender, "card", ""),
        )
    if managed:
        try:
            await moderate_group_message_detached(event)
        except Exception:
            pass


@notice_matcher.handle()
async def handle_group_member_change(event: NoticeEvent) -> None:
    if event.notice_type not in {"group_increase", "group_decrease"}:
        return
    group_id = int(getattr(event, "group_id", 0) or 0)
    user_id = int(getattr(event, "user_id", 0) or 0)
    if group_id <= 0 or user_id <= 0:
        return
    should_sync = await database(
        bot_data.record_notice,
        group_id,
        user_id,
        event.notice_type,
        str(getattr(event, "sub_type", "")),
        getattr(event, "operator_id", None),
        event_to_dict(event),
    )
    if should_sync:
        task = asyncio.create_task(sync_group_info_safely(group_id))
        jobs.tasks.add(task)
        task.add_done_callback(jobs.tasks.discard)
