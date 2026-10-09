import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError

from app.models import ImageReviewConfig
from app.schemas.admin import ImageReviewChannelIn, ImageReviewConfigIn
from app.services import image_moderation


def config():
    return ImageReviewConfig(
        enabled=True,
        channels=[
            ImageReviewChannelIn(id="disabled", name="停用渠道", enabled=False).model_dump(
                exclude={"clear_api_key"}
            ),
            ImageReviewChannelIn(
                id="primary",
                name="主渠道",
                model="model-a",
                api_key="key-a",
                base_url="https://primary.example/v1",
            ).model_dump(exclude={"clear_api_key"}),
            ImageReviewChannelIn(
                id="backup",
                name="备用渠道",
                model="model-b",
                api_key="key-b",
                base_url="https://backup.example/v1",
                response_format="json_object",
                max_completion_tokens=4096,
                reasoning_effort="low",
            ).model_dump(exclude={"clear_api_key"}),
        ],
    )


def json_reply(violates=False, confidence=0.95):
    return {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": json.dumps(
                        {
                            "violates": violates,
                            "confidence": confidence,
                            "reason": "可见证据",
                        }
                    )
                },
            }
        ]
    }


def tool_reply(violates=False, confidence=0.95):
    return {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {
                                "name": "submit_image_review",
                                "arguments": json.dumps(
                                    {
                                        "violates": violates,
                                        "confidence": confidence,
                                        "reason": "可见证据",
                                    }
                                ),
                            },
                        }
                    ]
                },
            }
        ]
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", ["timeout", "network", "401", "429", "503", "malformed", "refusal", "wrong-tool"]
)
async def test_failing_channel_uses_independent_backup_settings(monkeypatch, failure):
    calls = []

    async def handler(request):
        calls.append(request)
        if request.url.host == "primary.example":
            if failure == "timeout":
                raise httpx.ReadTimeout("timeout")
            if failure == "network":
                raise httpx.ConnectError("unreachable")
            if failure.isdigit():
                return httpx.Response(int(failure))
            if failure == "refusal":
                return httpx.Response(200, json={"choices": [{"message": {"refusal": "refused"}}]})
            if failure == "wrong-tool":
                data = tool_reply(True)
                data["choices"][0]["message"]["tool_calls"][0]["function"]["name"] = "kick_user"
                return httpx.Response(200, json=data)
            return httpx.Response(200, json={"choices": []})
        return httpx.Response(200, json=json_reply(True))

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        image_moderation.httpx,
        "AsyncClient",
        lambda **kw: client_class(
            transport=httpx.MockTransport(handler),
            **kw,
        ),
    )
    verdict = await image_moderation.review_image(config(), "https://image.example/a")
    assert verdict.violates and verdict._channel_name == "备用渠道"
    assert verdict._model_name == "model-b"
    assert [request.url.host for request in calls] == ["primary.example", "backup.example"]
    assert calls[0].headers["authorization"] == "Bearer key-a"
    assert calls[1].headers["authorization"] == "Bearer key-b"
    backup_body = json.loads(calls[1].content)
    assert backup_body["model"] == "model-b"
    assert backup_body["max_completion_tokens"] == 4096 and backup_body["reasoning_effort"] == "low"
    assert backup_body["response_format"]["type"] == "json_object"
    assert "tools" not in backup_body


@pytest.mark.asyncio
@pytest.mark.parametrize("violates,confidence", [(False, 0.95), (True, 0.4), (True, 0.99)])
async def test_any_valid_verdict_stops_failover(monkeypatch, violates, confidence):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=tool_reply(violates, confidence))

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        image_moderation.httpx,
        "AsyncClient",
        lambda **kw: client_class(
            transport=httpx.MockTransport(handler),
            **kw,
        ),
    )
    verdict = await image_moderation.review_image(config(), "https://image.example/a")
    assert verdict.violates == violates and verdict.confidence == confidence
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_total_deadline_and_all_channels_fail(monkeypatch):
    async def handler(request):
        await asyncio.sleep(0.05)
        return httpx.Response(500)

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        image_moderation.httpx,
        "AsyncClient",
        lambda **kw: client_class(
            transport=httpx.MockTransport(handler),
            **kw,
        ),
    )
    settings = config()
    # Use a short deadline directly on the runtime config to keep this test fast.
    settings.channels[1]["timeout_seconds"] = 1
    settings.channels[2]["timeout_seconds"] = 1
    original_wait = asyncio.wait_for

    async def fast_wait(awaitable, timeout):
        return await original_wait(awaitable, timeout=0.01)

    monkeypatch.setattr(image_moderation.asyncio, "wait_for", fast_wait)
    assert await image_moderation.review_image(settings, "https://image.example/a") is None


def test_duplicate_channels_and_enabled_config_without_channels_are_rejected():
    entry = ImageReviewChannelIn(id="same", model="vision")
    with pytest.raises(ValidationError):
        ImageReviewConfigIn(enabled=True, channels=[entry, entry])
    with pytest.raises(ValidationError):
        ImageReviewConfigIn(enabled=True)
