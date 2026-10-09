from types import SimpleNamespace

import pytest
from nonebot import logger

from app.models import ImageReviewConfig, MessageModerationRule, TencentCloudTmsConfig
from app.models.entities import MessageModerationAction
from app.services import image_moderation, message_moderation, onebot


def image_event():
    return SimpleNamespace(
        group_id=1001,
        user_id=42,
        message_id=-9001,
        message=[
            {"type": "image", "data": {"url": f"https://image.example/{index}.jpg"}}
            for index in range(3)
        ],
        get_plaintext=lambda: "普通文字",
    )


async def moderate(action=MessageModerationAction.recall_and_mute, duration=600):
    rule = MessageModerationRule(
        id=7,
        name="图片",
        image_review_enabled=True,
        action=action,
        mute_duration_seconds=duration,
    )
    return await message_moderation._moderate_snapshot(
        image_event(),
        [rule.model_dump()],
        TencentCloudTmsConfig().model_dump(),
        ImageReviewConfig(enabled=True).model_dump(),
    )


@pytest.fixture
def verdict_api(monkeypatch):
    reviews = []

    async def review(config, url, text, *, context):
        reviews.append(url)
        return image_moderation.ImageVerdict(
            violates=True, confidence=0.96, reason="明确的违规内容"
        )

    monkeypatch.setattr(image_moderation, "review_image", review)
    return reviews


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action,duration,expected_apis,expected_action",
    [
        (MessageModerationAction.recall, 600, ["delete_msg"], "已撤回"),
        (MessageModerationAction.mute, 30, ["set_group_ban"], "已禁言 30秒"),
        (MessageModerationAction.mute, 3661, ["set_group_ban"], "已禁言 1小时1分钟1秒"),
        (MessageModerationAction.mute, 86400, ["set_group_ban"], "已禁言 1天"),
        (
            MessageModerationAction.recall_and_mute,
            600,
            ["delete_msg", "set_group_ban"],
            "已撤回并禁言 10分钟",
        ),
    ],
)
async def test_warning_replies_once_after_successful_actions(
    monkeypatch, verdict_api, action, duration, expected_apis, expected_action
):
    calls = []

    async def call(api, **data):
        calls.append((api, data))
        return {"message_id": 123}

    monkeypatch.setattr(onebot, "call_onebot", call)
    result = await moderate(action, duration)

    assert result.id == 7 and len(verdict_api) == 1
    assert [api for api, _ in calls] == [*expected_apis, "send_group_msg"]
    if "delete_msg" in expected_apis:
        assert calls[0][1] == {"message_id": -9001}
    if "set_group_ban" in expected_apis:
        assert calls[-2][1] == {"group_id": 1001, "user_id": 42, "duration": duration}
    assert calls[-1][1] == {
        "group_id": 1001,
        "message": [
            {"type": "reply", "data": {"id": "-9001"}},
            {
                "type": "text",
                "data": {
                    "text": "警告：\n因模型检测到：明确的违规内容\n置信度：96.0%\n"
                    + expected_action
                },
            },
        ],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failed_apis,expected_action",
    [
        ({"delete_msg"}, "已禁言 10分钟"),
        ({"set_group_ban"}, "已撤回"),
        ({"delete_msg", "set_group_ban"}, None),
    ],
)
async def test_failed_actions_are_not_reported_as_success(
    monkeypatch, verdict_api, failed_apis, expected_action
):
    calls = []

    async def call(api, **data):
        calls.append((api, data))
        if api in failed_apis:
            raise RuntimeError("no permission")

    monkeypatch.setattr(onebot, "call_onebot", call)
    with pytest.raises(RuntimeError, match="失败"):
        await moderate()

    assert len(verdict_api) == 1
    assert [api for api, _ in calls[:2]] == ["delete_msg", "set_group_ban"]
    replies = [data for api, data in calls if api == "send_group_msg"]
    if expected_action is None:
        assert not replies
    else:
        assert len(replies) == 1
        assert replies[0]["message"][1]["data"]["text"].splitlines()[-1] == expected_action


@pytest.mark.asyncio
async def test_warning_failure_logs_and_does_not_repeat_actions_or_review(
    monkeypatch, verdict_api
):
    calls, logs = [], []

    async def call(api, **data):
        calls.append(api)
        if api == "send_group_msg":
            raise RuntimeError("private upstream body")

    monkeypatch.setattr(onebot, "call_onebot", call)
    sink = logger.add(lambda message: logs.append(str(message)), format="{message}", level="INFO")
    try:
        result = await moderate()
    finally:
        logger.remove(sink)

    assert result.id == 7 and len(verdict_api) == 1
    assert calls == ["delete_msg", "set_group_ban", "send_group_msg"]
    assert any(
        "图片审核警告回复失败" in line and "group=1001, user=42, message=-9001" in line
        for line in logs
    )
    assert not any("private upstream body" in line or "警告已回复" in line for line in logs)


@pytest.mark.asyncio
@pytest.mark.parametrize("verdict", [None, (False, 0.99), (True, 0.4)])
async def test_no_warning_when_review_does_not_trigger_action(monkeypatch, verdict):
    async def review(*args, **kwargs):
        if verdict is None:
            return None
        return image_moderation.ImageVerdict(
            violates=verdict[0], confidence=verdict[1], reason="审核原因"
        )

    async def unexpected_api(*args, **kwargs):
        pytest.fail("non-triggering verdicts must not execute actions or send warnings")

    monkeypatch.setattr(image_moderation, "review_image", review)
    monkeypatch.setattr(onebot, "call_onebot", unexpected_api)
    assert await moderate() is None


@pytest.mark.asyncio
async def test_model_reason_is_sent_as_plain_text_and_keeps_warning_format(monkeypatch):
    calls = []

    async def call(api, **data):
        calls.append((api, data))

    monkeypatch.setattr(onebot, "call_onebot", call)
    verdict = image_moderation.ImageVerdict(
        violates=True,
        confidence=1,
        reason="  违规内容\n\t[CQ:at,qq=all] [CQ:image,file=https://image.example/a]  ",
    )
    await message_moderation.apply_moderation_action(
        MessageModerationRule(name="图片", action=MessageModerationAction.recall),
        group_id=1001,
        user_id=42,
        message_id=-9001,
        verdict=verdict,
    )

    segments = calls[-1][1]["message"]
    assert [segment["type"] for segment in segments] == ["reply", "text"]
    assert segments[1]["data"]["text"].splitlines() == [
        "警告：",
        "因模型检测到：违规内容 [CQ:at,qq=all] [CQ:image,file=https://image.example/a]",
        "置信度：100.0%",
        "已撤回",
    ]
