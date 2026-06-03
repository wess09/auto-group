import re
from typing import Protocol

from sqlmodel import Session, col, select

from app.models import MessageModerationRule
from app.models.entities import MessageModerationAction
from app.services import onebot


class GroupMessageLike(Protocol):
    group_id: int
    user_id: int
    message_id: int

    def get_plaintext(self) -> str: ...


def message_matches_rule(rule: MessageModerationRule, message_text: str) -> bool:
    for pattern in rule.patterns:
        pattern = pattern.strip()
        if not pattern:
            continue
        try:
            if re.search(pattern, message_text, flags=re.IGNORECASE):
                return True
        except re.error:
            continue
    return False


def find_matching_moderation_rule(
    session: Session, group_id: int, message_text: str
) -> MessageModerationRule | None:
    rules = session.exec(
        select(MessageModerationRule)
        .where(MessageModerationRule.enabled == True)  # noqa: E712
        .order_by(col(MessageModerationRule.group_id).desc(), col(MessageModerationRule.id).desc())
    ).all()
    for rule in rules:
        if rule.group_id is not None and rule.group_id != group_id:
            continue
        if message_matches_rule(rule, message_text):
            return rule
    return None


async def apply_moderation_action(
    rule: MessageModerationRule, group_id: int, user_id: int, message_id: int
) -> None:
    errors: list[str] = []
    if rule.action in {
        MessageModerationAction.recall,
        MessageModerationAction.recall_and_mute,
    }:
        try:
            await onebot.delete_msg(message_id)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"撤回失败：{exc}")
    if rule.action in {
        MessageModerationAction.mute,
        MessageModerationAction.recall_and_mute,
    }:
        try:
            await onebot.set_group_ban(group_id, user_id, rule.mute_duration_seconds)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"禁言失败：{exc}")
    if errors:
        raise RuntimeError("；".join(errors))


async def moderate_group_message(session: Session, event: GroupMessageLike) -> MessageModerationRule | None:
    message_text = event.get_plaintext()
    if not message_text:
        return None
    rule = find_matching_moderation_rule(session, event.group_id, message_text)
    if not rule:
        return None
    await apply_moderation_action(rule, event.group_id, event.user_id, event.message_id)
    return rule
