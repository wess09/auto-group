from typing import Any

from nonebot import on_notice, on_request
from nonebot.adapters.onebot.v11 import Bot, GroupDecreaseNoticeEvent, GroupRequestEvent
from sqlmodel import Session, select

from app.core.database import engine
from app.models import JoinRequest, LeaveEvent, ManagedGroup
from app.services.groups import get_recommended_group, render_redirect_message
from app.services.rules import find_matching_rule


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


@request_matcher.handle()
async def handle_group_request(bot: Bot, event: GroupRequestEvent) -> None:
    if event.request_type != "group" or event.sub_type != "add":
        return

    raw_event = event_to_dict(event)
    answer = extract_answer(getattr(event, "comment", "") or "")
    with Session(engine) as session:
        source_group = session.exec(
            select(ManagedGroup).where(ManagedGroup.group_id == event.group_id)
        ).first()
        recommended = get_recommended_group(session, require_join_url=False)
        result = "pending"
        reason = ""
        matched_rule_id: int | None = None

        if recommended and event.group_id != recommended.group_id:
            reason = render_redirect_message(recommended, source_group)
            await bot.call_api(
                "set_group_add_request",
                flag=event.flag,
                sub_type=event.sub_type,
                approve=False,
                reason=reason,
            )
            result = "redirected"
        else:
            matched_rule = find_matching_rule(session, event.group_id, answer)
            if matched_rule:
                matched_rule_id = matched_rule.id
                await bot.call_api(
                    "set_group_add_request",
                    flag=event.flag,
                    sub_type=event.sub_type,
                    approve=True,
                    reason="",
                )
                result = "approved"
            else:
                reason = "答案不正确，请确认后重新申请。"
                await bot.call_api(
                    "set_group_add_request",
                    flag=event.flag,
                    sub_type=event.sub_type,
                    approve=False,
                    reason=reason,
                )
                result = "rejected"

        session.add(
            JoinRequest(
                flag=event.flag,
                user_id=event.user_id,
                group_id=event.group_id,
                answer_text=answer,
                matched_rule_id=matched_rule_id,
                recommended_group_id=recommended.group_id if recommended else None,
                result=result,
                reason=reason,
                raw_event=raw_event,
            )
        )
        session.commit()


@notice_matcher.handle()
async def handle_group_decrease(event: GroupDecreaseNoticeEvent) -> None:
    if event.notice_type != "group_decrease":
        return
    with Session(engine) as session:
        session.add(
            LeaveEvent(
                group_id=event.group_id,
                user_id=event.user_id,
                operator_id=getattr(event, "operator_id", None),
                sub_type=event.sub_type,
                raw_event=event_to_dict(event),
            )
        )
        group = session.exec(select(ManagedGroup).where(ManagedGroup.group_id == event.group_id)).first()
        if group and group.current_members > 0:
            group.current_members -= 1
            session.add(group)
        session.commit()
