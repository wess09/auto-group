import asyncio
import json
from urllib.parse import quote

import httpx
import pytest
from nonebot import logger

from app.models import ImageReviewConfig
from app.schemas.admin import ImageReviewChannelIn
from app.services import image_moderation


IMAGE_URL = "https://multimedia.nt.qq.com.cn/download?fileid=private-image-token"
API_KEY = "sk-test-private-key"
CONTEXT = "group=1001, user=42, message=9001, image=1/1"


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch):
    monkeypatch.setattr(image_moderation, "RETRY_400_DELAYS", (0, 0))


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


def configured(model="omni-moderation-latest"):
    return ImageReviewConfig(
        enabled=True,
        channels=[
            ImageReviewChannelIn(
                id="primary",
                model=model,
                api_key=API_KEY,
                base_url="https://primary.example/v1",
                response_format="json_object",
            ).model_dump(exclude={"clear_api_key"}),
            ImageReviewChannelIn(
                id="backup",
                model="vision",
                api_key="backup-key",
                base_url="https://backup.example/v1",
                response_format="json_object",
            ).model_dump(exclude={"clear_api_key"}),
        ],
    )


def success(request):
    if request.url.path.endswith("/moderations"):
        categories = {
            name: False
            for name in [
                "sexual",
                "sexual/minors",
                "harassment",
                "harassment/threatening",
                "hate",
                "hate/threatening",
                "illicit",
                "illicit/violent",
                "self-harm",
                "self-harm/intent",
                "self-harm/instructions",
                "violence",
                "violence/graphic",
            ]
        }
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "flagged": False,
                        "categories": categories,
                        "category_scores": {name: 0.01 for name in categories},
                    }
                ]
            },
        )
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": json.dumps(
                            {"violates": False, "confidence": 0.95, "reason": "游戏画面"}
                        )
                    },
                }
            ]
        },
    )


def bad_request(attempt):
    return httpx.Response(
        400,
        headers={"x-request-id": f"req-{attempt}"},
        json={
            "error": {
                "type": "invalid_request_error",
                "code": "invalid_image_url",
                "param": "input",
                "message": f"Timeout downloading image {IMAGE_URL}. Authorization: Bearer {API_KEY}",
                "debug": "private upstream body",
            }
        },
    )


def mock_api(monkeypatch, handler):
    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        image_moderation.httpx,
        "AsyncClient",
        lambda **kwargs: client_class(
            transport=httpx.MockTransport(handler),
            **kwargs,
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["omni-moderation-latest", "vision"])
@pytest.mark.parametrize("failures", [1, 2])
async def test_400_retries_same_remote_image_request_and_stops_on_success(
    monkeypatch, logs, model, failures
):
    requests = []

    def handler(request):
        requests.append(request)
        return bad_request(len(requests)) if len(requests) <= failures else success(request)

    mock_api(monkeypatch, handler)
    verdict = await image_moderation.review_image(configured(model), IMAGE_URL, context=CONTEXT)
    assert verdict is not None and not verdict.violates and verdict._channel_name == "primary"
    assert len(requests) == failures + 1
    assert all(
        request.method == "POST" and request.url.host == "primary.example" for request in requests
    )
    assert all(request.content == requests[0].content for request in requests)
    body = json.loads(requests[0].content)
    url = (
        body["input"][0]["image_url"]["url"]
        if model.startswith("omni-")
        else body["messages"][1]["content"][1]["image_url"]["url"]
    )
    assert url == IMAGE_URL  # Keep remote URLs: no GET/download or data-URL conversion.
    for attempt in range(1, failures + 1):
        assert any(
            f"重发 {attempt}/2" in line
            and f"request_id='req-{attempt}'" in line
            and CONTEXT in line
            for line in logs
        )
    assert any(
        "Timeout downloading image" in line and "code='invalid_image_url'" in line for line in logs
    )
    assert not any("尝试下一启用渠道" in line for line in logs)
    assert not any(
        secret in line
        for line in logs
        for secret in [IMAGE_URL, API_KEY, "private-image-token", "private upstream body"]
    )


@pytest.mark.asyncio
async def test_three_400_responses_exhaust_retries_before_backup(monkeypatch, logs):
    requests = []

    def handler(request):
        requests.append(request)
        return (
            bad_request(len(requests))
            if request.url.host == "primary.example"
            else success(request)
        )

    mock_api(monkeypatch, handler)
    verdict = await image_moderation.review_image(configured(), IMAGE_URL, context=CONTEXT)
    assert verdict._channel_name == "backup"
    assert [request.url.host for request in requests] == ["primary.example"] * 3 + [
        "backup.example"
    ]
    assert any("额外重发 2 次仍失败" in line and "request_id='req-3'" in line for line in logs)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 429, 500, 503])
async def test_other_http_errors_switch_channels_without_retries(monkeypatch, logs, status):
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.host == "primary.example":
            return httpx.Response(
                status, json={"error": {"code": "test_error", "message": "upstream failed"}}
            )
        return success(request)

    mock_api(monkeypatch, handler)
    assert (await image_moderation.review_image(configured(), IMAGE_URL))._channel_name == "backup"
    assert len(requests) == 2 and not any("重发" in line for line in logs)
    assert any(f"HTTP {status}" in line and "message='upstream failed'" in line for line in logs)


@pytest.mark.asyncio
async def test_retry_delay_shares_channel_deadline_and_still_fails_over(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return bad_request(1) if request.url.host == "primary.example" else success(request)

    mock_api(monkeypatch, handler)
    monkeypatch.setattr(image_moderation, "RETRY_400_DELAYS", (1, 1))
    original_wait = asyncio.wait_for

    async def short_deadline(awaitable, timeout):
        return await original_wait(awaitable, timeout=0.01)

    monkeypatch.setattr(image_moderation.asyncio, "wait_for", short_deadline)
    assert (await image_moderation.review_image(configured(), IMAGE_URL))._channel_name == "backup"
    assert [request.url.host for request in requests] == ["primary.example", "backup.example"]


def test_error_details_are_redacted_single_line_and_bounded():
    response = httpx.Response(
        400,
        headers={"x-request-id": "req-example"},
        json={
            "error": {
                "type": "invalid_request_error",
                "code": "invalid_image",
                "param": "input[0].image_url",
                "message": f"Could not fetch {quote(IMAGE_URL, safe='')}\nBearer {API_KEY} https://other.example/?token=private-other-token data:image/png;base64,private-image-data sk-unknown-key "
                + "x" * 1000,
                "debug": "private upstream body",
            }
        },
    )
    details = image_moderation.http_error_details(response, secrets=(API_KEY, IMAGE_URL))
    assert "request_id='req-example'" in details and "code='invalid_image'" in details
    assert "Could not fetch" in details and "\\n" in details and "\n" not in details
    assert len(details) < 750 and "x" * 1000 not in details
    for secret in [
        "private-image-token",
        "private-other-token",
        API_KEY,
        "private-image-data",
        "sk-unknown-key",
        "private upstream body",
        "https://",
    ]:
        assert secret not in details


@pytest.mark.parametrize(
    "body",
    [
        b"<html>private upstream body</html>",
        b"x" * (64 * 1024 + 1),
        b'{"error": "private upstream body"}',
    ],
    ids=["html", "oversized", "string-error"],
)
def test_nonstandard_error_bodies_are_not_dumped(body):
    details = image_moderation.http_error_details(httpx.Response(400, content=body))
    assert "private upstream body" not in details and len(details) < 100
