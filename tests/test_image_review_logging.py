from types import SimpleNamespace

import httpx
import pytest
from nonebot import logger
from nonebot.adapters.onebot.v11 import Message, MessageSegment

from app.bot import events
from app.models import ImageReviewConfig, MessageModerationRule, TencentCloudTmsConfig
from app.schemas.admin import ImageReviewChannelIn
from app.services import image_moderation, message_moderation


CONTEXT = "group=1001, user=42, message=9001"


@pytest.fixture
def logs():
    messages = []
    sink = logger.add(
        lambda message: messages.append(str(message)), format="{message}", level="INFO"
    )
    try:
        yield messages
    finally:
        logger.remove(sink)


def image_event():
    return SimpleNamespace(
        group_id=1001,
        user_id=42,
        message_id=9001,
        message=Message(MessageSegment.image("https://image.example/a?token=private-token")),
        get_plaintext=lambda: "普通文字",
    )


async def moderate(event, rule=None, config=None):
    return await message_moderation._moderate_snapshot(
        event,
        [rule.model_dump()] if rule else [],
        TencentCloudTmsConfig().model_dump(),
        (config or ImageReviewConfig(enabled=True)).model_dump(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["no-rule", "disabled", "no-url", "text-action"])
async def test_skipping_images_explains_why_without_calling_api(monkeypatch, logs, case):
    event = image_event()
    rule = MessageModerationRule(id=7, name="图片", image_review_enabled=True)
    config = ImageReviewConfig(enabled=True)
    if case == "no-rule":
        rule = None
        expected = "消息审查中没有对当前群生效且已启用「LLM 多模态图片审核」的规则"
    elif case == "disabled":
        config.enabled = False
        expected = "全局图片审核服务未启用"
    elif case == "no-url":
        event.message = Message(MessageSegment.image("local-image.jpg"))
        expected = "图片消息没有可用的图片 URL"
    else:
        rule.patterns = ["普通"]
        expected = "文本规则已执行动作"

    async def unexpected_review(*args, **kwargs):
        pytest.fail("skipped images must not call the API")

    async def action(*args, **kwargs):
        pass

    monkeypatch.setattr(image_moderation, "review_image", unexpected_review)
    monkeypatch.setattr(message_moderation, "apply_moderation_action", action)
    await moderate(event, rule, config)
    assert any("图片审核跳过" in line and CONTEXT in line and expected in line for line in logs)
    assert not any("图片审核完成" in line for line in logs)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "violates,confidence,fail_action",
    [(False, 0.95, False), (True, 0.4, False), (True, 0.96, False), (True, 0.96, True)],
)
async def test_completed_verdict_and_action_result_are_distinct(
    monkeypatch, logs, violates, confidence, fail_action
):
    actions = []

    async def review(config, url, text, *, context):
        assert context == CONTEXT + ", image=1/1"
        verdict = image_moderation.ImageVerdict(
            violates=violates, confidence=confidence, reason="可见证据"
        )
        verdict._channel_name, verdict._model_name = "主渠道", "vision"
        return verdict

    async def action(*args, **kwargs):
        actions.append(args)
        if fail_action:
            raise RuntimeError("private upstream body")

    monkeypatch.setattr(image_moderation, "review_image", review)
    monkeypatch.setattr(message_moderation, "apply_moderation_action", action)
    rule = MessageModerationRule(id=7, name="图片", image_review_enabled=True)
    if fail_action:
        with pytest.raises(RuntimeError):
            await moderate(image_event(), rule)
    else:
        await moderate(image_event(), rule)
    trigger = violates and confidence >= 0.85
    assert bool(actions) == trigger
    assert any(
        "图片审核完成" in line
        and CONTEXT in line
        and "channel=主渠道" in line
        and "model=vision" in line
        and f"触发动作={trigger}" in line
        for line in logs
    )
    if trigger:
        expected = "图片审核动作失败" if fail_action else "图片审核动作完成"
    else:
        expected = "模型判定不违规" if not violates else "置信度未达到阈值"
    assert any(expected in line and CONTEXT in line for line in logs)
    assert not any("private upstream body" in line for line in logs)
    if fail_action:
        assert not any("图片审核动作完成" in line for line in logs)


@pytest.mark.asyncio
async def test_api_failover_logs_correlated_requests_and_completion_without_secrets(
    monkeypatch, logs
):
    def handler(request):
        if request.url.host == "primary.example":
            return httpx.Response(401, json={"error": "private upstream body"})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": '{"violates": false, "confidence": 0.95, "reason": "游戏画面"}'
                        },
                    }
                ]
            },
        )

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        image_moderation.httpx,
        "AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs),
    )
    config = ImageReviewConfig(
        enabled=True,
        channels=[
            ImageReviewChannelIn(
                id=name,
                model="vision",
                base_url=f"https://{name}.example/v1",
                api_key="private-key",
                response_format="json_object",
            ).model_dump(exclude={"clear_api_key"})
            for name in ["primary", "backup"]
        ],
    )
    await moderate(
        image_event(), MessageModerationRule(name="图片", image_review_enabled=True), config
    )
    requests = [line for line in logs if "图片审核 API 请求" in line]
    assert len(requests) == 2 and all(CONTEXT in line for line in requests)
    assert "channel=primary" in requests[0] and "channel=backup" in requests[1]
    assert any("HTTP 401" in line and CONTEXT in line and "耗时=" in line for line in logs)
    assert any("API 响应有效" in line and "channel=backup" in line for line in logs)
    assert any("图片审核完成" in line and "违规=False" in line for line in logs)
    assert not any(
        secret in line
        for line in logs
        for secret in ["private-key", "private-token", "private upstream body", "https://"]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("managed", [False, True])
async def test_handler_logs_unmanaged_images_and_unexpected_review_errors(
    monkeypatch, logs, managed
):
    async def database(*args):
        return managed

    async def broken_review(event):
        raise RuntimeError("private upstream body")

    monkeypatch.setattr(events, "database", database)
    monkeypatch.setattr(events, "moderate_group_message_detached", broken_review)
    await events.handle_group_message(image_event())
    assert any("图片审核收到图片消息" in line and CONTEXT in line for line in logs)
    expected = "图片审核异常" if managed else "该群不在受管理群配置中"
    assert any(expected in line and CONTEXT in line for line in logs)
    assert not any("private upstream body" in line for line in logs)

    logs.clear()
    event = image_event()
    event.message = Message("普通文字")
    await events.handle_group_message(event)
    assert not any("图片审核" in line for line in logs)
