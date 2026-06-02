from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, delete, select

from app.models import Announcement, EssenceMessage, GroupFile, GroupMember, ManagedGroup
from app.services import onebot
from app.services.groups import touch_group


def _pick(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return default


async def sync_group_info(session: Session, group: ManagedGroup) -> ManagedGroup:
    info = await onebot.get_group_info(group.group_id)
    group.name = str(_pick(info, "group_name", "name", default=group.name))
    group.current_members = int(_pick(info, "member_count", "current_member_count", default=0) or 0)
    group.max_members = int(_pick(info, "max_member_count", "max_members", default=group.max_members) or 0)
    touch_group(group)
    session.add(group)
    session.commit()
    session.refresh(group)
    return group


async def sync_group_members(session: Session, group_id: int) -> int:
    members = await onebot.get_group_member_list(group_id)
    session.exec(delete(GroupMember).where(GroupMember.group_id == group_id))
    count = 0
    for item in members:
        session.add(
            GroupMember(
                group_id=group_id,
                user_id=int(_pick(item, "user_id", default=0)),
                nickname=str(_pick(item, "nickname", default="")),
                card=str(_pick(item, "card", default="")),
                role=str(_pick(item, "role", default="")),
                synced_at=datetime.now(timezone.utc),
            )
        )
        count += 1
    group = session.exec(select(ManagedGroup).where(ManagedGroup.group_id == group_id)).first()
    if group:
        group.current_members = count
        touch_group(group)
        session.add(group)
    session.commit()
    return count


async def sync_group_notices(session: Session, group_id: int) -> int:
    data = await onebot.get_group_notices(group_id)
    notices = data if isinstance(data, list) else data.get("notices", data.get("data", []))
    session.exec(delete(Announcement).where(Announcement.group_id == group_id))
    count = 0
    for item in notices or []:
        notice_id = str(_pick(item, "notice_id", "id", "fid", default=""))
        if not notice_id:
            continue
        session.add(
            Announcement(
                group_id=group_id,
                notice_id=notice_id,
                sender_id=_pick(item, "sender_id", "user_id"),
                title=str(_pick(item, "title", default="")),
                content=str(_pick(item, "content", "message", "text", default="")),
                raw_data=item,
                synced_at=datetime.now(timezone.utc),
            )
        )
        count += 1
    session.commit()
    return count


async def sync_group_files(session: Session, group_id: int) -> int:
    data = await onebot.get_group_root_files(group_id)
    files = data if isinstance(data, list) else data.get("files", data.get("data", []))
    session.exec(delete(GroupFile).where(GroupFile.group_id == group_id))
    count = 0
    for item in files or []:
        file_id = str(_pick(item, "file_id", "id", default=""))
        if not file_id:
            continue
        session.add(
            GroupFile(
                group_id=group_id,
                file_id=file_id,
                folder_id=str(_pick(item, "folder_id", default="")),
                file_name=str(_pick(item, "file_name", "name", default=file_id)),
                busid=_pick(item, "busid"),
                size=_pick(item, "size"),
                uploader_id=_pick(item, "uploader", "uploader_id", "user_id"),
                raw_data=item,
                synced_at=datetime.now(timezone.utc),
            )
        )
        count += 1
    session.commit()
    return count


async def sync_essence_messages(session: Session, group_id: int) -> int:
    data = await onebot.get_essence_msg_list(group_id)
    messages = data if isinstance(data, list) else data.get("data", data.get("messages", []))
    session.exec(delete(EssenceMessage).where(EssenceMessage.group_id == group_id))
    count = 0
    for item in messages or []:
        message_id = _pick(item, "message_id", "msg_seq")
        if message_id is None:
            continue
        session.add(
            EssenceMessage(
                group_id=group_id,
                message_id=int(message_id),
                sender_id=_pick(item, "sender_id", "sender_uin", "user_id"),
                operator_id=_pick(item, "operator_id", "operator_uin"),
                content=str(_pick(item, "content", "message", default="")),
                raw_data=item,
                synced_at=datetime.now(timezone.utc),
            )
        )
        count += 1
    session.commit()
    return count
