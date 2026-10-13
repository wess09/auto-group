import asyncio
import base64
import json
from urllib.parse import quote

import httpx
import pytest
from pydantic import ValidationError

from app.models import ImageReviewConfig
from app.schemas.admin import ImageReviewChannelIn
from app.services import image_moderation
from app.services.image_review_config import image_review_config_out
from tests.test_image_review_failover import tool_reply
from tests.test_omni_moderation import moderation_reply


@pytest.mark.parametrize(
    "proxy_url",
    [
        "",
        "http://127.0.0.1:7890",
        "https://proxy.example:8443/",
        "socks5://localhost:1080",
        "socks5://user:pa%3Ass@proxy.example:1080",
        "http://[::1]:7890",
    ],
)
def test_supported_proxy_addresses(proxy_url):
    channel = ImageReviewChannelIn(id="a", model="vision", proxy_url=f" {proxy_url} ")
    assert channel.proxy_url == proxy_url
    # Exercise HTTPX's real HTTP/SOCKS transport initialization, including socksio.
    with httpx.Client(proxy=channel.proxy_url or None, trust_env=False):
        pass


@pytest.mark.parametrize(
    "proxy_url",
    [
        "127.0.0.1:7890",
        "ftp://proxy.example:21",
        "socks4://proxy.example:1080",
        "http://",
        "http://user:pass@:7890",
        "http://proxy.example:bad",
        "http://proxy.example:65536",
        "http://proxy.example:0",
        "http://[::1",
        "http://proxy.example/path",
        "http://proxy.example?token=secret",
        "http://proxy.example#fragment",
        "http://proxy.example:78\t90",
        "http://user:two words@proxy.example:7890",
    ],
)
def test_invalid_proxy_addresses_are_rejected(proxy_url):
    with pytest.raises(ValidationError):
        ImageReviewChannelIn(id="a", model="vision", proxy_url=proxy_url)


def test_cannot_set_and_clear_proxy_at_once():
    with pytest.raises(ValidationError, match="不能同时设置和清除代理地址"):
        ImageReviewChannelIn(
            id="a", model="vision", proxy_url="http://localhost:7890", clear_proxy_url=True
        )


def test_legacy_channel_has_no_explicit_proxy():
    config = ImageReviewConfig(channels=[{"id": "a", "model": "vision"}])
    assert not image_review_config_out(config).channels[0].proxy_url_configured
    assert ImageReviewChannelIn.model_validate(config.channels[0]).proxy_url == ""


async def serve_proxy(reader, writer, *, status, reply, calls):
    try:
        head = (await reader.readuntil(b"\r\n\r\n")).decode("ascii")
        lines = head.split("\r\n")
        headers = {
            key.lower(): value for line in lines[1:] if line for key, value in [line.split(": ", 1)]
        }
        body = await reader.readexactly(int(headers["content-length"]))
        calls.append((lines[0], headers, json.loads(body)))
        content = json.dumps(reply()).encode()
        writer.write(
            f"HTTP/1.1 {status} Test\r\nContent-Type: application/json\r\n"
            f"Content-Length: {len(content)}\r\nConnection: close\r\n\r\n".encode()
            + content
        )
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,attempts", [(400, 3), (407, 1)])
@pytest.mark.parametrize("model", ["vision", "omni-moderation-latest"])
async def test_real_proxy_auth_retries_and_independent_failover(
    monkeypatch, failure, attempts, model
):
    primary_calls, backup_calls, logs = [], [], []
    proxy_url = ""
    username, password = "proxy-user-private", "pa:ss-private"
    monkeypatch.setattr(image_moderation, "RETRY_400_DELAYS", (0, 0))
    monkeypatch.setattr(image_moderation.logger, "warning", logs.append)
    # Explicit channel proxies must take precedence over environment proxies/bypass settings.
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "*")

    async def fail(reader, writer):
        await serve_proxy(
            reader,
            writer,
            status=failure,
            reply=lambda: {
                "error": {
                    "message": f"Proxy {proxy_url} {quote(proxy_url, safe='')} "
                    f"{username} {password} {quote(password, safe='')} failed"
                }
            },
            calls=primary_calls,
        )

    async def success(reader, writer):
        await serve_proxy(
            reader,
            writer,
            status=200,
            reply=moderation_reply if model.startswith("omni-") else tool_reply,
            calls=backup_calls,
        )

    primary = await asyncio.start_server(fail, "127.0.0.1", 0)
    backup = await asyncio.start_server(success, "127.0.0.1", 0)
    async with primary, backup:
        proxy_url = (
            f"http://{username}:{quote(password, safe='')}@127.0.0.1:"
            f"{primary.sockets[0].getsockname()[1]}"
        )
        backup_url = f"http://127.0.0.1:{backup.sockets[0].getsockname()[1]}"
        config = ImageReviewConfig(
            enabled=True,
            channels=[
                ImageReviewChannelIn(
                    id="primary",
                    model=model,
                    api_key="primary-api-key",
                    base_url="http://primary.invalid/v1",
                    proxy_url=proxy_url,
                ).model_dump(exclude={"clear_api_key", "clear_proxy_url"}),
                ImageReviewChannelIn(
                    id="backup",
                    model=model,
                    api_key="backup-api-key",
                    base_url="http://backup.invalid/v1",
                    proxy_url=backup_url,
                ).model_dump(exclude={"clear_api_key", "clear_proxy_url"}),
            ],
        )
        verdict = await image_moderation.review_image(config, "https://image.example/a")

    assert verdict is not None and verdict._channel_name == "backup"
    assert len(primary_calls) == attempts and len(backup_calls) == 1
    endpoint = "moderations" if model.startswith("omni-") else "chat/completions"
    auth = "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()
    for target, headers, body in primary_calls:
        assert target == f"POST http://primary.invalid/v1/{endpoint} HTTP/1.1"
        assert headers["proxy-authorization"] == auth
        assert headers["authorization"] == "Bearer primary-api-key"
        assert body["model"] == model and "proxy_url" not in body
    target, headers, body = backup_calls[0]
    assert target == f"POST http://backup.invalid/v1/{endpoint} HTTP/1.1"
    assert "proxy-authorization" not in headers
    assert headers["authorization"] == "Bearer backup-api-key"
    assert logs
    for secret in (username, password, quote(password, safe=""), proxy_url, "primary-api-key"):
        assert secret not in " ".join(logs)


@pytest.mark.asyncio
async def test_legacy_channel_still_uses_environment_proxy(monkeypatch):
    calls = []

    async def success(reader, writer):
        await serve_proxy(reader, writer, status=200, reply=tool_reply, calls=calls)

    proxy = await asyncio.start_server(success, "127.0.0.1", 0)
    async with proxy:
        monkeypatch.setenv("HTTP_PROXY", f"http://127.0.0.1:{proxy.sockets[0].getsockname()[1]}")
        monkeypatch.setenv("NO_PROXY", "")
        config = ImageReviewConfig(
            enabled=True,
            channels=[{"id": "legacy", "model": "vision", "base_url": "http://api.invalid/v1"}],
        )
        verdict = await image_moderation.review_image(config, "https://image.example/a")
    assert verdict is not None and verdict._channel_name == "legacy"
    assert len(calls) == 1
