from pathlib import Path
from typing import Any, Protocol

from nonebot import get_bots

from app.core.config import get_settings


class BotLike(Protocol):
    async def call_api(self, api: str, **data: Any) -> Any: ...


def get_onebot() -> BotLike | None:
    bots = get_bots()
    if not bots:
        return None
    return next(iter(bots.values()))


async def call_onebot(api: str, **data: Any) -> Any:
    bot = get_onebot()
    if bot is None:
        raise RuntimeError("没有已连接的 OneBot/LLBot 实例")
    return await bot.call_api(api, **data)


async def set_group_add_request(flag: str, sub_type: str, approve: bool, reason: str = "") -> Any:
    return await call_onebot(
        "set_group_add_request",
        flag=flag,
        sub_type=sub_type,
        approve=approve,
        reason=reason,
    )


async def get_group_info(group_id: int) -> dict[str, Any]:
    settings = get_settings()
    return await call_onebot(
        "get_group_info",
        group_id=group_id,
        _timeout=settings.onebot_api_timeout_seconds,
    )


async def get_group_member_list(group_id: int) -> list[dict[str, Any]]:
    settings = get_settings()
    return await call_onebot(
        "get_group_member_list",
        group_id=group_id,
        _timeout=settings.group_member_sync_timeout_seconds,
    )


async def set_group_kick(group_id: int, user_id: int, reject_add_request: bool = False) -> Any:
    return await call_onebot(
        "set_group_kick",
        group_id=group_id,
        user_id=user_id,
        reject_add_request=reject_add_request,
    )


async def delete_msg(message_id: int) -> Any:
    return await call_onebot("delete_msg", message_id=message_id)


async def set_group_ban(group_id: int, user_id: int, duration: int) -> Any:
    return await call_onebot(
        "set_group_ban",
        group_id=group_id,
        user_id=user_id,
        duration=duration,
    )


async def send_group_notice(group_id: int, content: str) -> Any:
    return await call_onebot("_send_group_notice", group_id=group_id, content=content)


async def get_group_notices(group_id: int) -> Any:
    return await call_onebot("_get_group_notice", group_id=group_id)


async def delete_group_notice(group_id: int, notice_id: str) -> Any:
    return await call_onebot("_delete_group_notice", group_id=group_id, notice_id=notice_id)


async def upload_group_file(
    group_id: int,
    file_path: str,
    name: str | None = None,
    folder_id: str | None = None,
) -> Any:
    path = Path(file_path).resolve()
    data: dict[str, Any] = {"group_id": group_id, "file": str(path)}
    if name:
        data["name"] = name
    if folder_id:
        data["folder"] = folder_id
    return await call_onebot("upload_group_file", **data)


async def get_group_root_files(group_id: int) -> Any:
    return await call_onebot("get_group_root_files", group_id=group_id)


async def get_group_files_by_folder(group_id: int, folder_id: str) -> Any:
    return await call_onebot("get_group_files_by_folder", group_id=group_id, folder_id=folder_id)


async def delete_group_file(group_id: int, file_id: str, busid: int) -> Any:
    return await call_onebot("delete_group_file", group_id=group_id, file_id=file_id, busid=busid)


async def get_group_file_url(group_id: int, file_id: str, busid: int) -> Any:
    return await call_onebot("get_group_file_url", group_id=group_id, file_id=file_id, busid=busid)


async def get_group_file_system_info(group_id: int) -> Any:
    return await call_onebot("get_group_file_system_info", group_id=group_id)


async def rename_group_file(
    group_id: int, file_id: str, current_parent_directory: str, new_name: str
) -> Any:
    return await call_onebot(
        "rename_group_file",
        group_id=group_id,
        file_id=file_id,
        current_parent_directory=current_parent_directory,
        new_name=new_name,
    )


async def rename_group_file_folder(
    group_id: int, folder_id: str, new_folder_name: str
) -> Any:
    return await call_onebot(
        "rename_group_file_folder",
        group_id=group_id,
        folder_id=folder_id,
        new_folder_name=new_folder_name,
    )


async def send_group_message(group_id: int, message: str) -> Any:
    return await call_onebot("send_group_msg", group_id=group_id, message=message)


async def get_essence_msg_list(group_id: int) -> Any:
    return await call_onebot("get_essence_msg_list", group_id=group_id)


async def set_essence_msg(message_id: int) -> Any:
    return await call_onebot("set_essence_msg", message_id=message_id)


async def delete_essence_msg(message_id: int) -> Any:
    return await call_onebot("delete_essence_msg", message_id=message_id)
