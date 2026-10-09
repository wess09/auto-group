import copy
import json
from types import SimpleNamespace

import httpx
import pytest
from nonebot import logger

from app.models import ImageReviewConfig, MessageModerationRule, TencentCloudTmsConfig
from app.schemas.admin import ImageReviewChannelIn
from app.services import image_moderation, message_moderation


def moderation_reply(flagged=True, score=0.96):
    categories = {
        "sexual": False,
        "sexual/minors": False,
        "harassment": False,
        "harassment/threatening": False,
        "hate": False,
        "hate/threatening": False,
        "illicit": None,
        "illicit/violent": None,
        "self-harm": False,
        "self-harm/intent": False,
        "self-harm/instructions": False,
        "violence": flagged,
        "violence/graphic": False,
    }
    scores = {name: 0.001 for name in categories}
    scores["violence"] = score
    return {
        "id": "modr-example",
        "model": "omni-moderation-latest",
        "results": [
            {
                "flagged": flagged,
                "categories": categories,
                "category_scores": scores,
                "category_applied_input_types": {"violence": ["image", "text"]},
            }
        ],
    }


def config_for(*models):
    return ImageReviewConfig(
        enabled=True,
        channels=[
            ImageReviewChannelIn(
                id=f"channel-{index}",
                model=model,
                base_url=f"https://channel-{index}.example/v1",
                api_key=f"test-key-{index}",
                response_format="json_object",
            ).model_dump(exclude={"clear_api_key"})
            for index, model in enumerate(models)
        ],
    )


def mock_api(monkeypatch, handler):
    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        image_moderation.httpx,
        "AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs),
    )


async def moderate(config):
    event = SimpleNamespace(
        group_id=1001,
        user_id=42,
        message_id=9001,
        message=[{"type": "image", "data": {"url": "https://image.example/a"}}],
        get_plaintext=lambda: "游戏画面",
    )
    rule = MessageModerationRule(id=7, name="图片", image_review_enabled=True)
    return await message_moderation._moderate_snapshot(
        event, [rule.model_dump()], TencentCloudTmsConfig().model_dump(), config.model_dump()
    )


@pytest.mark.parametrize("model", ["omni-moderation-latest", "omni-moderation-2024-09-26"])
@pytest.mark.parametrize("suffix", ["", "/", "/moderations", "/chat/completions/"])
def test_moderations_endpoint_and_payload_exclude_chat_parameters(model, suffix):
    channel = ImageReviewChannelIn(
        id="primary",
        model=model,
        base_url="https://api.example/custom/v1" + suffix,
        reasoning_effort="high",
        max_completion_tokens=4096,
        extra_body={"thinking": {"budget_tokens": 1024}, "temperature": 0.5},
        image_detail="high",
    )
    assert image_moderation.build_endpoint(channel) == "https://api.example/custom/v1/moderations"
    body = image_moderation.build_request(
        ImageReviewConfig(), channel, "data:image/png;base64,abc", ""
    )
    assert body == {
        "model": model,
        "input": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}],
    }
    body = image_moderation.build_request(
        ImageReviewConfig(), channel, "https://image.example/a", "x" * 3000
    )
    assert set(body) == {"model", "input"}
    assert body["input"][0] == {"type": "text", "text": "x" * 2000}


def test_category_scores_use_only_flagged_categories_and_nullable_illicit_is_supported():
    data = moderation_reply(score=0.4)
    data["results"][0]["category_scores"]["sexual"] = 0.99
    verdict = image_moderation.parse_moderation_response(data)
    assert verdict.violates and verdict.confidence == 0.4
    assert verdict._score_label == "分类分数"
    assert "暴力(violence)=0.4000" in verdict.reason
    assert "sexual" not in verdict.reason
    # Older compatible responses may omit the nullable illicit categories.
    for field in ["categories", "category_scores"]:
        for category in ["illicit", "illicit/violent"]:
            del data["results"][0][field][category]
    assert image_moderation.parse_moderation_response(data).confidence == 0.4


@pytest.mark.parametrize(
    "invalid",
    [
        "missing-results",
        "empty-results",
        "multiple-results",
        "flag-string",
        "flag-mismatch",
        "missing-category",
        "empty-categories",
        "category-string",
        "category-null",
        "missing-score",
        "score-string",
        "score-bool",
        "score-nan",
        "score-infinite",
        "score-negative",
        "score-over-one",
    ],
)
def test_invalid_moderation_responses_are_rejected(invalid):
    data = copy.deepcopy(moderation_reply())
    result = data["results"][0]
    if invalid == "missing-results":
        data.pop("results")
    elif invalid == "empty-results":
        data["results"] = []
    elif invalid == "multiple-results":
        data["results"].append(result)
    elif invalid == "flag-string":
        result["flagged"] = "true"
    elif invalid == "flag-mismatch":
        result["flagged"] = False
    elif invalid == "missing-category":
        del result["categories"]["sexual"]
        del result["category_scores"]["sexual"]
    elif invalid == "empty-categories":
        result["categories"] = {}
    elif invalid == "category-string":
        result["categories"]["violence"] = "true"
    elif invalid == "category-null":
        result["categories"]["violence"] = None
    elif invalid == "missing-score":
        del result["category_scores"]["violence"]
    else:
        result["category_scores"]["violence"] = {
            "score-string": "0.9",
            "score-bool": True,
            "score-nan": float("nan"),
            "score-infinite": float("inf"),
            "score-negative": -0.1,
            "score-over-one": 1.1,
        }[invalid]
    with pytest.raises(ValueError):
        image_moderation.parse_moderation_response(data)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "models", [("omni-moderation-latest", "vision"), ("vision", "omni-moderation-latest")]
)
@pytest.mark.parametrize("failure", ["http", "malformed"])
async def test_failover_between_moderations_and_chat_uses_each_channels_protocol(
    monkeypatch, models, failure
):
    requests, actions = [], []

    def handler(request):
        requests.append(request)
        if request.url.host == "channel-0.example":
            return httpx.Response(503) if failure == "http" else httpx.Response(200, json={})
        if request.url.path.endswith("/moderations"):
            return httpx.Response(200, json=moderation_reply())
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {"violates": True, "confidence": 0.96, "reason": "可见证据"}
                            )
                        },
                    }
                ]
            },
        )

    async def action(*args, **kwargs):
        actions.append(args)

    mock_api(monkeypatch, handler)
    monkeypatch.setattr(message_moderation, "apply_moderation_action", action)
    result = await moderate(config_for(*models))
    assert result.id == 7 and len(actions) == 1
    assert len(requests) == 2
    for index, (request, model) in enumerate(zip(requests, models)):
        assert request.headers["authorization"] == f"Bearer test-key-{index}"
        body = json.loads(request.content)
        if model == "omni-moderation-latest":
            assert request.url.path == "/v1/moderations"
            assert set(body) == {"model", "input"}
        else:
            assert request.url.path == "/v1/chat/completions" and "messages" in body


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "flagged,score,trigger", [(False, 0.99, False), (True, 0.4, False), (True, 0.96, True)]
)
async def test_valid_omni_verdict_stops_failover_and_logs_category_score(
    monkeypatch, flagged, score, trigger
):
    requests, actions, logs = [], [], []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=moderation_reply(flagged, score))

    async def action(*args, **kwargs):
        actions.append(args)

    mock_api(monkeypatch, handler)
    monkeypatch.setattr(message_moderation, "apply_moderation_action", action)
    sink = logger.add(lambda message: logs.append(str(message)), format="{message}", level="INFO")
    try:
        await moderate(config_for("omni-moderation-latest", "vision"))
    finally:
        logger.remove(sink)
    assert len(requests) == 1 and bool(actions) == trigger
    assert any("mode=moderations" in line and "message=9001" in line for line in logs)
    assert any(
        "图片审核完成" in line and f"分类分数={score}" in line and f"触发动作={trigger}" in line
        for line in logs
    )
    if flagged:
        assert any("暴力(violence)" in line for line in logs)
