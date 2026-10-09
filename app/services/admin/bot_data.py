"""Short database transactions for bot events; no Session crosses an await."""

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import (
    JoinRequest,
    JoinBlacklist,
    AuditLog,
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
from app.services.image_review_config import get_image_review_config


def join_requirements(session: Session, group_id: int, user_id: int) -> int | None:
    group = session.exec(select(ManagedGroup).where(ManagedGroup.group_id == group_id)).first()
    if not group or not group.enabled:
        return None
    if get_enabled_blacklist_item(session, user_id):
        return 0
    return group.min_qq_level


def decide_join(
    session: Session, group_id: int, user_id: int, answer: str, qq_level: int | None = None
) -> dict:
    blacklist = get_enabled_blacklist_item(session, user_id)
    group = session.exec(select(ManagedGroup).where(ManagedGroup.group_id == group_id)).first()
    recommended = get_recommended_group(session, require_join_url=False)
    redirect = get_unfilled_prioritized_group(session, group)
    if not redirect and recommended and group_id != recommended.group_id:
        redirect = recommended
    result, reason, rule_id = "rejected", "答案不正确，请确认后重新申请。", None
    wrong_answer_count = 0
    if blacklist:
        result, reason = "blacklisted", blacklist.reason or get_settings().public_fallback_message
    elif group and group.min_qq_level and qq_level is None:
        result, reason = "level_unknown", "暂时无法获取 QQ 等级，请稍后重新申请。"
    elif group and qq_level is not None and qq_level < group.min_qq_level:
        result, reason = (
            "level_rejected",
            (f"QQ 等级不足：当前 {qq_level} 级，本群要求至少 {group.min_qq_level} 级。"),
        )
    elif redirect:
        result, reason = "redirected", render_redirect_message(redirect, group)
    else:
        rule = find_matching_rule(session, group_id, answer)
        if rule:
            result, reason, rule_id = "approved", "", rule.id
        elif group and group.max_wrong_answers:
            now = datetime.now(timezone.utc)
            since = now - timedelta(hours=group.wrong_answer_window_hours)
            existing = session.exec(
                select(JoinBlacklist).where(JoinBlacklist.user_id == user_id)
            ).first()
            # Disabling a blacklist is a pardon: do not count attempts before it.
            if existing and not existing.enabled:
                pardoned = existing.updated_at
                if pardoned.tzinfo is None:
                    pardoned = pardoned.replace(tzinfo=timezone.utc)
                since = max(since, pardoned)
            recent = session.exec(
                select(JoinRequest)
                .where(
                    JoinRequest.group_id == group_id,
                    JoinRequest.user_id == user_id,
                    JoinRequest.created_at >= since,
                )
                .order_by(JoinRequest.id.desc())
            ).all()
            for request in recent:
                if request.result == "approved":
                    break
                if request.result == "rejected":
                    wrong_answer_count += 1
            wrong_answer_count += 1
            if wrong_answer_count >= group.max_wrong_answers:
                reason = (
                    f"入群答案错误次数达到上限：{group.wrong_answer_window_hours} 小时内"
                    f"已答错 {wrong_answer_count} 次（上限 {group.max_wrong_answers} 次），"
                    "已加入加群黑名单。"
                )
                note = (
                    f"自动拉黑：入群验证答案错误过多；来源群：{group.name or '未命名'}"
                    f"（{group_id}）；QQ：{user_id}；统计窗口：{group.wrong_answer_window_hours} 小时；"
                    f"错误次数：{wrong_answer_count}；阈值：{group.max_wrong_answers}；"
                    f"最后一次错误答案：{answer[:500]!r}；"
                    f"触发时间（UTC+8）：{now.astimezone(timezone(timedelta(hours=8))).isoformat()}；"
                    "适用于所有受管理群的加群申请。"
                )
                item = existing or JoinBlacklist(user_id=user_id)
                item.enabled, item.reason = True, reason
                item.note = (item.note + "\n" if item.note else "") + note
                item.updated_at = now
                session.add(item)
                session.add(
                    AuditLog(
                        action="blacklist.auto",
                        target=str(user_id),
                        detail={
                            "group_id": group_id,
                            "wrong_answer_count": wrong_answer_count,
                            "threshold": group.max_wrong_answers,
                            "note": note,
                        },
                    )
                )
                result = "blacklisted"
    return {
        "result": result,
        "reason": reason,
        "matched_rule_id": rule_id,
        "wrong_answer_count": wrong_answer_count,
        "recommended_group_id": redirect.group_id
        if redirect
        else recommended.group_id
        if recommended
        else None,
    }


def record_join(session: Session, data: dict) -> None:
    session.add(JoinRequest(**data))
    session.commit()


def decide_and_record_join(session: Session, data: dict, qq_level: int | None) -> tuple[dict, int]:
    previous = session.exec(
        select(JoinRequest).where(
            JoinRequest.flag == data["flag"],
            JoinRequest.group_id == data["group_id"],
            JoinRequest.user_id == data["user_id"],
        )
    ).first()
    keys = ("result", "reason", "matched_rule_id", "recommended_group_id", "wrong_answer_count")
    if previous:
        blacklist = get_enabled_blacklist_item(session, data["user_id"])
        if blacklist and previous.result != "blacklisted":
            # A stale approval must not bypass a blacklist added before a retry.
            previous.result = "blacklisted"
            previous.reason = blacklist.reason or get_settings().public_fallback_message
            previous.matched_rule_id = None
            session.add(previous)
            session.commit()
            session.refresh(previous)
        return {key: getattr(previous, key) for key in keys}, previous.id
    decision = decide_join(
        session, data["group_id"], data["user_id"], data["answer_text"], qq_level
    )
    row = JoinRequest(**data, qq_level=qq_level, **decision)
    session.add(row)
    session.commit()
    session.refresh(row)
    return decision, row.id


def finish_join(session: Session, item_id: int, error: str = "") -> None:
    row = session.get(JoinRequest, item_id)
    if row:
        row.apply_status = "failed" if error else "success"
        row.apply_error = error[:1000]
        session.add(row)
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


def moderation_snapshot(session: Session, group_id: int) -> tuple[list[dict], dict, dict]:
    rules = session.exec(
        select(MessageModerationRule)
        .where(
            MessageModerationRule.enabled == True,  # noqa: E712
            (MessageModerationRule.group_id == group_id) | MessageModerationRule.group_id.is_(None),
        )
        .order_by(MessageModerationRule.group_id.desc(), MessageModerationRule.id.desc())
    ).all()
    return (
        [rule.model_dump() for rule in rules],
        get_tms_config(session).model_dump(),
        get_image_review_config(session).model_dump(),
    )
