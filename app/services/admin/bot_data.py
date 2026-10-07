"""Short database transactions for bot events; no Session crosses an await."""

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import (
    JoinRequest,
    LeaveEvent,
    ManagedGroup,
    MemberActivityStat,
    MessageModerationRule,
)
from app.services.groups import (
    get_recommended_group,
    get_unfilled_prioritized_group,
    render_redirect_message,
)
from app.services.join_blacklist import get_enabled_blacklist_item
from app.services.rules import find_matching_rule
from app.services.tencentcloud_tms_config import get_tms_config


def decide_join(session: Session, group_id: int, user_id: int, answer: str) -> dict:
    blacklist = get_enabled_blacklist_item(session, user_id)
    group = session.exec(select(ManagedGroup).where(ManagedGroup.group_id == group_id)).first()
    recommended = get_recommended_group(session, require_join_url=False)
    redirect = get_unfilled_prioritized_group(session, group)
    if not redirect and recommended and group_id != recommended.group_id:
        redirect = recommended
    result, reason, rule_id = "rejected", "答案不正确，请确认后重新申请。", None
    if blacklist:
        result, reason = "blacklisted", blacklist.reason or get_settings().public_fallback_message
    elif redirect:
        result, reason = "redirected", render_redirect_message(redirect, group)
    else:
        rule = find_matching_rule(session, group_id, answer)
        if rule:
            result, reason, rule_id = "approved", "", rule.id
    return {
        "result": result,
        "reason": reason,
        "matched_rule_id": rule_id,
        "recommended_group_id": redirect.group_id
        if redirect
        else recommended.group_id
        if recommended
        else None,
    }


def record_join(session: Session, data: dict) -> None:
    session.add(JoinRequest(**data))
    session.commit()


def record_activity(
    session: Session, group_id: int, user_id: int, nickname: str, card: str
) -> bool:
    if (
        session.exec(select(ManagedGroup.id).where(ManagedGroup.group_id == group_id)).first()
        is None
    ):
        return False
    now = datetime.now(timezone.utc)
    day = now.date().isoformat()
    stat = session.exec(
        select(MemberActivityStat).where(
            MemberActivityStat.group_id == group_id,
            MemberActivityStat.user_id == user_id,
            MemberActivityStat.stat_date == day,
        )
    ).first()
    if stat is None:
        stat = MemberActivityStat(group_id=group_id, user_id=user_id, stat_date=day)
    stat.nickname = nickname or stat.nickname
    stat.card = card or stat.card
    stat.message_count += 1
    stat.last_active_at = now
    session.add(stat)
    session.commit()
    return True


def record_notice(
    session: Session,
    group_id: int,
    user_id: int,
    notice_type: str,
    sub_type: str,
    operator_id: int | None,
    raw: dict,
) -> bool:
    if (
        session.exec(select(ManagedGroup.id).where(ManagedGroup.group_id == group_id)).first()
        is None
    ):
        return False
    if notice_type == "group_decrease":
        session.add(
            LeaveEvent(
                group_id=group_id,
                user_id=user_id,
                operator_id=operator_id,
                sub_type=sub_type,
                raw_event=raw,
            )
        )
        session.commit()
    return True


def moderation_snapshot(session: Session, group_id: int) -> tuple[list[dict], dict]:
    rules = session.exec(
        select(MessageModerationRule)
        .where(
            MessageModerationRule.enabled == True,  # noqa: E712
            (MessageModerationRule.group_id == group_id) | MessageModerationRule.group_id.is_(None),
        )
        .order_by(MessageModerationRule.group_id.desc(), MessageModerationRule.id.desc())
    ).all()
    return [rule.model_dump() for rule in rules], get_tms_config(session).model_dump()
