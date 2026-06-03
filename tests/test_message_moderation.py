from sqlmodel import Session, SQLModel, create_engine

import pytest

from app.models import MessageModerationRule
from app.models.entities import MessageModerationAction
from app.services import message_moderation
from app.services.message_moderation import (
    apply_moderation_action,
    find_matching_moderation_rule,
    message_matches_rule,
)


def test_message_moderation_regex_matches_case_insensitively() -> None:
    rule = MessageModerationRule(name="spam", patterns=[r"buy\s+now"])

    assert message_matches_rule(rule, "BUY now")


def test_message_moderation_skips_invalid_regex() -> None:
    rule = MessageModerationRule(name="bad", patterns=["[", r"safe-\d+"])

    assert message_matches_rule(rule, "safe-100")
    assert not message_matches_rule(rule, "hello")


def test_find_matching_moderation_rule_prefers_group_specific_rule() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            MessageModerationRule(
                name="global",
                group_id=None,
                patterns=[r"blocked"],
                action=MessageModerationAction.recall,
            )
        )
        session.add(
            MessageModerationRule(
                name="group",
                group_id=1001,
                patterns=[r"blocked"],
                action=MessageModerationAction.recall_and_mute,
            )
        )
        session.commit()

        rule = find_matching_moderation_rule(session, 1001, "blocked")

    assert rule is not None
    assert rule.name == "group"


@pytest.mark.asyncio
async def test_apply_moderation_action_recalls_and_mutes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, int, int | None, int | None]] = []

    async def fake_delete_msg(message_id: int) -> None:
        calls.append(("delete", message_id, None, None))

    async def fake_set_group_ban(group_id: int, user_id: int, duration: int) -> None:
        calls.append(("ban", group_id, user_id, duration))

    monkeypatch.setattr(message_moderation.onebot, "delete_msg", fake_delete_msg)
    monkeypatch.setattr(message_moderation.onebot, "set_group_ban", fake_set_group_ban)
    rule = MessageModerationRule(
        name="spam",
        action=MessageModerationAction.recall_and_mute,
        mute_duration_seconds=300,
    )

    await apply_moderation_action(rule, group_id=1001, user_id=42, message_id=9001)

    assert calls == [("delete", 9001, None, None), ("ban", 1001, 42, 300)]


@pytest.mark.asyncio
async def test_apply_moderation_action_attempts_mute_when_recall_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, int, int | None, int | None]] = []

    async def fake_delete_msg(message_id: int) -> None:
        calls.append(("delete", message_id, None, None))
        raise RuntimeError("no permission")

    async def fake_set_group_ban(group_id: int, user_id: int, duration: int) -> None:
        calls.append(("ban", group_id, user_id, duration))

    monkeypatch.setattr(message_moderation.onebot, "delete_msg", fake_delete_msg)
    monkeypatch.setattr(message_moderation.onebot, "set_group_ban", fake_set_group_ban)
    rule = MessageModerationRule(
        name="spam",
        action=MessageModerationAction.recall_and_mute,
        mute_duration_seconds=300,
    )

    with pytest.raises(RuntimeError, match="撤回失败"):
        await apply_moderation_action(rule, group_id=1001, user_id=42, message_id=9001)

    assert calls == [("delete", 9001, None, None), ("ban", 1001, 42, 300)]
