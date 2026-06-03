from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.entities import LogicMode, MatchMode, MessageModerationAction


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ManagedGroupIn(BaseModel):
    group_id: int
    name: str = ""
    priority: int = 100
    enabled: bool = True
    max_members: int = 0
    current_members: int = 0
    join_url: str = ""
    redirect_message_template: str = (
        "请申请推荐群：{group_name}（{group_id}）。入群链接：{join_url}"
    )
    note: str = ""


class ManagedGroupPatch(BaseModel):
    name: str | None = None
    priority: int | None = None
    enabled: bool | None = None
    max_members: int | None = None
    current_members: int | None = None
    join_url: str | None = None
    redirect_message_template: str | None = None
    note: str | None = None


class AnswerRuleIn(BaseModel):
    name: str
    enabled: bool = True
    group_id: int | None = None
    match_mode: MatchMode = MatchMode.contains
    logic_mode: LogicMode = LogicMode.any
    patterns: list[str] = Field(default_factory=list)


class AnswerRulePatch(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    group_id: int | None = None
    match_mode: MatchMode | None = None
    logic_mode: LogicMode | None = None
    patterns: list[str] | None = None


class MessageModerationRuleIn(BaseModel):
    name: str
    enabled: bool = True
    group_id: int | None = None
    patterns: list[str] = Field(default_factory=list)
    action: MessageModerationAction = MessageModerationAction.recall
    mute_duration_seconds: int = Field(default=600, ge=1)
    note: str = ""


class MessageModerationRulePatch(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    group_id: int | None = None
    patterns: list[str] | None = None
    action: MessageModerationAction | None = None
    mute_duration_seconds: int | None = Field(default=None, ge=1)
    note: str | None = None


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


class EssenceCreateIn(BaseModel):
    group_ids: list[int]
    content: str


class EssenceDeleteIn(BaseModel):
    group_id: int
    message_ids: list[int]


class DedupeExecuteIn(BaseModel):
    job_id: int


class DedupeWhitelistIn(BaseModel):
    user_id: int
    note: str = ""
    enabled: bool = True


class DedupeWhitelistPatch(BaseModel):
    note: str | None = None
    enabled: bool | None = None


class JoinBlacklistIn(BaseModel):
    user_id: int
    enabled: bool = True
    reason: str = "你已被加入黑名单，无法申请入群。"
    note: str = ""


class JoinBlacklistPatch(BaseModel):
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
