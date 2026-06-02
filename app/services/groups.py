from datetime import datetime, timezone

from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import ManagedGroup


def is_group_available(group: ManagedGroup) -> bool:
    if not group.enabled:
        return False
    if not group.join_url:
        return False
    if group.max_members > 0 and group.current_members >= group.max_members:
        return False
    return True


def get_recommended_group(session: Session, require_join_url: bool = True) -> ManagedGroup | None:
    groups = session.exec(
        select(ManagedGroup)
        .where(ManagedGroup.enabled == True)  # noqa: E712
        .order_by(ManagedGroup.priority.desc(), ManagedGroup.current_members.asc())
    ).all()
    for group in groups:
        if require_join_url and not group.join_url:
            continue
        if group.max_members > 0 and group.current_members >= group.max_members:
            continue
        return group
    return None


def render_redirect_message(target_group: ManagedGroup | None, source_group: ManagedGroup | None) -> str:
    settings = get_settings()
    if not target_group:
        return settings.public_fallback_message
    template = (
        source_group.redirect_message_template
        if source_group and source_group.redirect_message_template
        else target_group.redirect_message_template
    )
    return template.format(
        group_name=target_group.name or str(target_group.group_id),
        group_id=target_group.group_id,
        join_url=target_group.join_url or "请联系管理员获取",
        priority=target_group.priority,
    )


def touch_group(group: ManagedGroup) -> None:
    group.updated_at = datetime.now(timezone.utc)
