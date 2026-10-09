from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.entities import LogicMode, MatchMode, MessageModerationAction
from app.services.image_review_policy import DEFAULT_IMAGE_REVIEW_PROMPT


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ManagedGroupIn(AdminInput):
    group_id: int
    name: str = ""
    priority: int = 100
    enabled: bool = True
    max_members: int = 0
    current_members: int = 0
    join_url: str = ""
    min_qq_level: int = Field(default=0, ge=0, le=1000)
    max_wrong_answers: int = Field(default=0, ge=0, le=1000)
    wrong_answer_window_hours: int = Field(default=24, ge=1, le=8760)
    redirect_message_template: str = (
        "请申请推荐群：{group_name}（{group_id}）。入群链接：{join_url}"
    )
    note: str = ""


class ManagedGroupPatch(AdminInput):
    name: str | None = None
    priority: int | None = None
    enabled: bool | None = None
    max_members: int | None = None
    current_members: int | None = None
    join_url: str | None = None
    min_qq_level: int | None = Field(default=None, ge=0, le=1000)
    max_wrong_answers: int | None = Field(default=None, ge=0, le=1000)
    wrong_answer_window_hours: int | None = Field(default=None, ge=1, le=8760)
    redirect_message_template: str | None = None
    note: str | None = None


class AnswerRuleIn(AdminInput):
    name: str
    enabled: bool = True
    group_id: int | None = None
    match_mode: MatchMode = MatchMode.contains
    logic_mode: LogicMode = LogicMode.any
    patterns: list[str] = Field(default_factory=list)


class AnswerRulePatch(AdminInput):
    name: str | None = None
    enabled: bool | None = None
    group_id: int | None = None
    match_mode: MatchMode | None = None
    logic_mode: LogicMode | None = None
    patterns: list[str] | None = None


class MessageModerationRuleIn(AdminInput):
    name: str
    enabled: bool = True
    group_id: int | None = None
    patterns: list[str] = Field(default_factory=list)
    cloud_review_enabled: bool = False
    ocr_enabled: bool = False
    image_review_enabled: bool = False
    action: MessageModerationAction = MessageModerationAction.recall
    mute_duration_seconds: int = Field(default=600, ge=1)
    note: str = ""


class MessageModerationRulePatch(AdminInput):
    name: str | None = None
    enabled: bool | None = None
    group_id: int | None = None
    patterns: list[str] | None = None
    cloud_review_enabled: bool | None = None
    ocr_enabled: bool | None = None
    image_review_enabled: bool | None = None
    action: MessageModerationAction | None = None
    mute_duration_seconds: int | None = Field(default=None, ge=1)
    note: str | None = None


class TencentCloudTmsConfigIn(AdminInput):
    secret_id: str = ""
    secret_key: str = ""
    region: str = "ap-guangzhou"
    biz_type: str = "TencentCloudDefault"
    source_language: str = "zh"
    timeout_seconds: float = Field(default=5.0, ge=1)


class TencentCloudTmsConfigOut(BaseModel):
    secret_id: str = ""
    secret_key_configured: bool = False
    region: str = "ap-guangzhou"
    biz_type: str = "TencentCloudDefault"
    source_language: str = "zh"
    timeout_seconds: float = 5.0


class ImageReviewChannelSettings(AdminInput):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(default="", max_length=100)
    enabled: bool = True
    base_url: str = "https://api.openai.com/v1"
    model: str = Field(default="", max_length=200)
    response_format: Literal["tool_call", "json_schema", "json_object", "none"] = "tool_call"
    reasoning_effort: Literal["", "none", "minimal", "low", "medium", "high", "xhigh", "max"] = ""
    max_completion_tokens: int = Field(default=2048, ge=128, le=131072)
    extra_body: dict[str, Any] = Field(default_factory=dict)
    image_detail: Literal["auto", "low", "high", "original"] = "auto"
    timeout_seconds: float = Field(default=30.0, ge=1, le=180)

    @field_validator("base_url")
    @classmethod
    def valid_base_url(cls, value: str) -> str:
        from urllib.parse import urlsplit

        value = value.strip().rstrip("/")
        url = urlsplit(value)
        if url.scheme not in {"https", "http"} or not url.hostname or url.username or url.password:
            raise ValueError("API 地址必须是无账号密码的 HTTP(S) URL")
        if url.query or url.fragment:
            raise ValueError("API 地址不能包含查询参数或片段")
        return value

    @field_validator("model", "name")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("extra_body")
    @classmethod
    def valid_extra_body(cls, value: dict) -> dict:
        import json

        protected = {
            "model",
            "messages",
            "stream",
            "n",
            "response_format",
            "max_tokens",
            "max_completion_tokens",
            "reasoning_effort",
            "tools",
            "tool_choice",
            "parallel_tool_calls",
            "functions",
            "function_call",
        }
        if protected.intersection(value):
            raise ValueError("扩展参数不能覆盖模型、消息、工具、输出格式或标准预算字段")
        if len(json.dumps(value, allow_nan=False)) > 16000:
            raise ValueError("扩展参数过大")
        return value

    @model_validator(mode="after")
    def valid_channel(self):
        if self.enabled and not self.model:
            raise ValueError("启用渠道时必须填写模型")
        return self


class ImageReviewChannelIn(ImageReviewChannelSettings):
    api_key: str = ""
    clear_api_key: bool = False

    @field_validator("api_key")
    @classmethod
    def strip_key(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def valid_key(self):
        if self.api_key and self.clear_api_key:
            raise ValueError("不能同时设置和清除 API Key")
        return self


class ImageReviewChannelOut(ImageReviewChannelSettings):
    api_key_configured: bool


class ImageReviewConfigIn(AdminInput):
    enabled: bool = False
    system_prompt: str = Field(default=DEFAULT_IMAGE_REVIEW_PROMPT, min_length=1, max_length=16000)
    min_confidence: float = Field(default=0.85, ge=0, le=1)
    channels: list[ImageReviewChannelIn] = Field(default_factory=list, max_length=8)

    @field_validator("system_prompt")
    @classmethod
    def strip_prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("提示词不能为空")
        return value.strip()

    @model_validator(mode="after")
    def valid_channels(self):
        ids = [channel.id for channel in self.channels]
        if len(ids) != len(set(ids)):
            raise ValueError("渠道 ID 不可重复")
        if self.enabled and not any(channel.enabled for channel in self.channels):
            raise ValueError("启用审核时至少需要一个启用的渠道")
        return self


class ImageReviewConfigOut(BaseModel):
    enabled: bool
    system_prompt: str
    default_system_prompt: str = DEFAULT_IMAGE_REVIEW_PROMPT
    min_confidence: float
    channels: list[ImageReviewChannelOut]


class NoticeSendIn(BaseModel):
    group_ids: list[int]
    content: str


class NoticeDeleteIn(BaseModel):
    group_id: int
    notice_ids: list[str]


class FileDistributeIn(BaseModel):
    group_ids: list[int]
    file_path: str
    name: str | None = None
    folder_id: str | None = None


class GroupFileDeleteIn(BaseModel):
    group_id: int
    file_id: str
    busid: int


class FileRenameIn(BaseModel):
    group_id: int
    file_id: str
    current_parent_directory: str
    new_name: str


class FolderRenameIn(BaseModel):
    group_id: int
    folder_id: str
    new_folder_name: str


class EssenceCreateIn(BaseModel):
    group_ids: list[int]
    content: str


class EssenceDeleteIn(BaseModel):
    group_id: int
    message_ids: list[int]


class DedupeExecuteIn(BaseModel):
    job_id: int


class DedupeWhitelistIn(AdminInput):
    user_id: int
    note: str = ""
    enabled: bool = True


class DedupeWhitelistPatch(AdminInput):
    note: str | None = None
    enabled: bool | None = None


class JoinBlacklistIn(AdminInput):
    user_id: int
    enabled: bool = True
    reason: str = "你已被加入黑名单，无法申请入群。"
    note: str = ""


class JoinBlacklistPatch(AdminInput):
    enabled: bool | None = None
    reason: str | None = None
    note: str | None = None


class PublicGroupOut(BaseModel):
    available: bool
    group_id: int | None = None
    group_name: str | None = None
    join_url: str | None = None
    current_members: int | None = None
    max_members: int | None = None
    message: str


class DashboardOut(BaseModel):
    groups: int
    enabled_groups: int
    join_requests: int
    leave_events: int
    announcements: int
    files: int
    essence_messages: int
    total_members: int
    today_join_requests: int
    today_leave_events: int
    today_admin_actions: int
    today_messages: int
    today_active_members: int
    join_result_breakdown: list[dict[str, Any]]
    activity_trend: list[dict[str, Any]]
    top_groups: list[dict[str, Any]]
    active_groups: list[dict[str, Any]]
    active_members: list[dict[str, Any]]
    recent_leave_events: list[dict[str, Any]]
    recent_audit_logs: list[dict[str, Any]]


class UploadOut(BaseModel):
    file_name: str
    file_path: str
    size: int


class GenericResult(BaseModel):
    ok: bool
    message: str = ""
    data: Any = None


class DedupePreviewAction(BaseModel):
    user_id: int
    nickname: str = ""
    keep_group_id: int
    kick_group_id: int
    status: str = "preview"
    error: str = ""


class DedupePreviewOut(BaseModel):
    job_id: int
    status: str = "preview"
    summary: dict[str, Any] = Field(default_factory=dict)
    duplicate_users: int
    actions: list[DedupePreviewAction]


class TimeRangeOut(BaseModel):
    created_at: datetime | None = None
    updated_at: datetime | None = None
