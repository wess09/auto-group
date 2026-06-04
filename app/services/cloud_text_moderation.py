import asyncio
import base64
from dataclasses import dataclass
from uuid import uuid4

from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.tms.v20201229 import models, tms_client

from app.models import TencentCloudTmsConfig


@dataclass(frozen=True)
class TextModerationDecision:
    should_trigger: bool
    suggestion: str = ""
    label: str = ""
    score: int | None = None
    request_id: str = ""


def is_configured(config: TencentCloudTmsConfig) -> bool:
    return bool(config.secret_id and config.secret_key)


def _create_client(config: TencentCloudTmsConfig) -> tms_client.TmsClient:
    cred = credential.Credential(
        config.secret_id,
        config.secret_key,
    )
    http_profile = HttpProfile()
    http_profile.endpoint = "tms.tencentcloudapi.com"
    http_profile.reqTimeout = config.timeout_seconds
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    return tms_client.TmsClient(cred, config.region, client_profile)


def _build_request(
    config: TencentCloudTmsConfig, text: str, *, group_id: int, user_id: int, message_id: int
) -> models.TextModerationRequest:
    request = models.TextModerationRequest()
    request.Content = base64.b64encode(text.encode("utf-8")).decode("ascii")
    request.BizType = config.biz_type
    request.DataId = f"msg-{message_id}-{uuid4().hex[:8]}"
    request.Type = "TEXT"
    request.SourceLanguage = config.source_language
    request.SessionId = str(group_id)

    user = models.User()
    user.UserId = str(user_id)
    user.AccountType = 2
    user.RoomId = str(group_id)
    request.User = user
    return request


def moderate_text_sync(
    config: TencentCloudTmsConfig, text: str, *, group_id: int, user_id: int, message_id: int
) -> TextModerationDecision:
    if not is_configured(config):
        return TextModerationDecision(should_trigger=False)

    client = _create_client(config)
    response = client.TextModeration(
        _build_request(config, text, group_id=group_id, user_id=user_id, message_id=message_id)
    )
    suggestion = str(response.Suggestion or "")
    return TextModerationDecision(
        should_trigger=suggestion.casefold() in {"block", "review"},
        suggestion=suggestion,
        label=str(response.Label or ""),
        score=response.Score,
        request_id=str(response.RequestId or ""),
    )


async def moderate_text(
    config: TencentCloudTmsConfig, text: str, *, group_id: int, user_id: int, message_id: int
) -> TextModerationDecision:
    return await asyncio.to_thread(
        moderate_text_sync,
        config,
        text,
        group_id=group_id,
        user_id=user_id,
        message_id=message_id,
    )
