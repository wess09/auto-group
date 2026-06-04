from sqlmodel import Session, SQLModel, create_engine

import pytest

from app.models import MessageModerationRule
from app.models.entities import MessageModerationAction
from app.services.cloud_text_moderation import TextModerationDecision
from app.services import message_moderation
from app.services.message_moderation import (
    apply_moderation_action,
    find_matching_moderation_rule,
    message_matches_rule,
    moderate_group_message,
)
from app.schemas.admin import TencentCloudTmsConfigIn
from app.services.tencentcloud_tms_config import (
    get_tms_config,
    tms_config_out,
    update_tms_config,
)


class FakeGroupMessage:
    group_id = 1001
    user_id = 42
    message_id = 9001

    def __init__(self, text: str) -> None:
        self.text = text

    def get_plaintext(self) -> str:
        return self.text


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
async def test_moderate_group_message_uses_regex_only_when_cloud_review_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    calls: list[tuple[int, int, int]] = []

    async def fake_apply(
        rule: MessageModerationRule, group_id: int, user_id: int, message_id: int
    ) -> None:
        del rule
        calls.append((group_id, user_id, message_id))

    async def fail_cloud_review(*args: object, **kwargs: object) -> TextModerationDecision:
        raise AssertionError("cloud review should not be called")

    monkeypatch.setattr(message_moderation, "apply_moderation_action", fake_apply)
    monkeypatch.setattr(message_moderation.cloud_text_moderation, "moderate_text", fail_cloud_review)
    with Session(engine) as session:
        rule = MessageModerationRule(name="spam", patterns=[r"blocked"])
        session.add(rule)
        session.commit()

        matched = await moderate_group_message(session, FakeGroupMessage("blocked text"))

    assert matched is not None
    assert calls == [(1001, 42, 9001)]


@pytest.mark.asyncio
async def test_moderate_group_message_skips_action_when_cloud_review_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    calls: list[str] = []

    async def fake_apply(
        rule: MessageModerationRule, group_id: int, user_id: int, message_id: int
    ) -> None:
        del rule, group_id, user_id, message_id
        calls.append("apply")

    async def fake_cloud_review(*args: object, **kwargs: object) -> TextModerationDecision:
        return TextModerationDecision(should_trigger=False, suggestion="Pass")

    monkeypatch.setattr(message_moderation, "apply_moderation_action", fake_apply)
    monkeypatch.setattr(message_moderation.cloud_text_moderation, "moderate_text", fake_cloud_review)
    with Session(engine) as session:
        rule = MessageModerationRule(
            name="spam",
            patterns=[r"blocked"],
            cloud_review_enabled=True,
        )
        session.add(rule)
        session.commit()

        matched = await moderate_group_message(session, FakeGroupMessage("blocked text"))

    assert matched is None
    assert calls == []


@pytest.mark.asyncio
async def test_moderate_group_message_applies_action_when_cloud_review_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    calls: list[str] = []

    async def fake_apply(
        rule: MessageModerationRule, group_id: int, user_id: int, message_id: int
    ) -> None:
        del group_id, user_id, message_id
        calls.append(rule.name)

    async def fake_cloud_review(*args: object, **kwargs: object) -> TextModerationDecision:
        return TextModerationDecision(should_trigger=True, suggestion="Block")

    monkeypatch.setattr(message_moderation, "apply_moderation_action", fake_apply)
    monkeypatch.setattr(message_moderation.cloud_text_moderation, "moderate_text", fake_cloud_review)
    with Session(engine) as session:
        rule = MessageModerationRule(
            name="spam",
            patterns=[r"blocked"],
            cloud_review_enabled=True,
        )
        session.add(rule)
        session.commit()

        matched = await moderate_group_message(session, FakeGroupMessage("blocked text"))

    assert matched is not None
    assert matched.name == "spam"
    assert calls == ["spam"]


def test_tencentcloud_tms_config_update_keeps_existing_secret_key() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        config = update_tms_config(
            session,
            TencentCloudTmsConfigIn(
                secret_id="first-id",
                secret_key="first-key",
                region="ap-shanghai",
                biz_type="custom",
                source_language="zh",
                timeout_seconds=3,
            ),
        )
        assert config.secret_key == "first-key"

        config = update_tms_config(
            session,
            TencentCloudTmsConfigIn(
                secret_id="second-id",
                secret_key="",
                region="ap-guangzhou",
                biz_type="TencentCloudDefault",
                source_language="en",
                timeout_seconds=5,
            ),
        )
        output = tms_config_out(get_tms_config(session))

    assert config.secret_id == "second-id"
    assert config.secret_key == "first-key"
    assert output.secret_key_configured
    assert output.secret_id == "second-id"


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
