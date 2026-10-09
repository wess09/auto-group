"""QQ account levels come from stranger info, never the group member rank."""

import asyncio
from typing import Any

from nonebot import logger

from app.core.config import get_settings
from app.services.admin import bot_data
from app.services.admin.runtime import database
from app.services.onebot import BotLike


join_lock = asyncio.Lock()


def extract_qq_level(info: Any) -> int | None:
    if not isinstance(info, dict):
        return None
    for key in ("qq_level", "qqLevel", "level"):
        value = info.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int) and value >= 0:
            return value
        if isinstance(value, str) and value.isascii() and value.isdigit():
            return int(value)
    return None


async def process_join_request(bot: BotLike, data: dict, sub_type: str = "add") -> dict | None:
    minimum = await database(bot_data.join_requirements, data["group_id"], data["user_id"])
    if minimum is None:
        return None
    level = None
    if minimum:
        try:
            info = await bot.call_api(
                "get_stranger_info",
                user_id=data["user_id"],
                no_cache=True,
                _timeout=get_settings().onebot_api_timeout_seconds,
            )
            level = extract_qq_level(info)
        except Exception as exc:
            logger.warning(f"获取 QQ 等级失败 user={data['user_id']}：{type(exc).__name__}")
    # Count and persist together, preventing concurrent/replayed requests counting twice.
    async with join_lock:
        decision, item_id = await database(bot_data.decide_and_record_join, data, level)
    try:
        await bot.call_api(
            "set_group_add_request",
            flag=data["flag"],
            sub_type=sub_type,
            approve=decision["result"] == "approved",
            reason=decision["reason"],
            _timeout=get_settings().onebot_api_timeout_seconds,
        )
    except Exception as exc:
        await database(bot_data.finish_join, item_id, str(exc))
        raise
    await database(bot_data.finish_join, item_id)
    return decision
