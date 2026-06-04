from datetime import datetime, timezone
from enum import Enum
from typing import Any, ClassVar

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class MatchMode(str, Enum):
    contains = "contains"
    exact = "exact"
    regex = "regex"


class LogicMode(str, Enum):
    any = "any"
    all = "all"


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    preview = "preview"


class MessageModerationAction(str, Enum):
    recall = "recall"
    mute = "mute"
    recall_and_mute = "recall_and_mute"


class ManagedGroup(SQLModel, table=True):
    __tablename__: ClassVar[str] = "managed_groups"

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(index=True, unique=True)
    name: str = ""
    priority: int = Field(default=100, index=True)
    enabled: bool = True
    max_members: int = 0
    current_members: int = 0
    join_url: str = ""
    redirect_message_template: str = (
        "请申请推荐群：{group_name}（{group_id}）。入群链接：{join_url}"
    )
    note: str = ""
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class AnswerRule(SQLModel, table=True):
    __tablename__: ClassVar[str] = "answer_rules"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    enabled: bool = True
    group_id: int | None = Field(default=None, index=True)
    match_mode: MatchMode = MatchMode.contains
    logic_mode: LogicMode = LogicMode.any
    patterns: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class MessageModerationRule(SQLModel, table=True):
    __tablename__: ClassVar[str] = "message_moderation_rules"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    enabled: bool = True
    group_id: int | None = Field(default=None, index=True)
    patterns: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    cloud_review_enabled: bool = False
    action: MessageModerationAction = MessageModerationAction.recall
    mute_duration_seconds: int = 600
    note: str = ""
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class TencentCloudTmsConfig(SQLModel, table=True):
    __tablename__: ClassVar[str] = "tencentcloud_tms_config"

    id: int | None = Field(default=None, primary_key=True)
    secret_id: str = ""
    secret_key: str = ""
    region: str = "ap-guangzhou"
    biz_type: str = "TencentCloudDefault"
    source_language: str = "zh"
    timeout_seconds: float = 5.0
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class JoinRequest(SQLModel, table=True):
    __tablename__: ClassVar[str] = "join_requests"

    id: int | None = Field(default=None, primary_key=True)
    flag: str = Field(index=True)
    user_id: int = Field(index=True)
    group_id: int = Field(index=True)
    answer_text: str = ""
    matched_rule_id: int | None = None
    recommended_group_id: int | None = None
    result: str = "pending"
    reason: str = ""
    raw_event: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now_utc)


class GroupMember(SQLModel, table=True):
    __tablename__: ClassVar[str] = "group_members"

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(index=True)
    user_id: int = Field(index=True)
    nickname: str = ""
    card: str = ""
    role: str = ""
    joined_at: datetime | None = None
    synced_at: datetime = Field(default_factory=now_utc)


class LeaveEvent(SQLModel, table=True):
    __tablename__: ClassVar[str] = "leave_events"

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(index=True)
    user_id: int = Field(index=True)
    operator_id: int | None = None
    sub_type: str = ""
    raw_event: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now_utc)


class MemberActivityStat(SQLModel, table=True):
    __tablename__: ClassVar[str] = "member_activity_stats"

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(index=True)
    user_id: int = Field(index=True)
    stat_date: str = Field(index=True)
    nickname: str = ""
    card: str = ""
    message_count: int = 0
    first_active_at: datetime = Field(default_factory=now_utc)
    last_active_at: datetime = Field(default_factory=now_utc)


class DedupeJob(SQLModel, table=True):
    __tablename__: ClassVar[str] = "dedupe_jobs"

    id: int | None = Field(default=None, primary_key=True)
    status: TaskStatus = TaskStatus.preview
    summary: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now_utc)
    executed_at: datetime | None = None


class DedupeAction(SQLModel, table=True):
    __tablename__: ClassVar[str] = "dedupe_actions"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(index=True)
    user_id: int = Field(index=True)
    keep_group_id: int
    kick_group_id: int
    nickname: str = ""
    status: str = "preview"
    error: str = ""
    created_at: datetime = Field(default_factory=now_utc)
    executed_at: datetime | None = None


class DedupeWhitelist(SQLModel, table=True):
    __tablename__: ClassVar[str] = "dedupe_whitelist"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, unique=True)
    note: str = ""
    enabled: bool = True
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class JoinBlacklist(SQLModel, table=True):
    __tablename__: ClassVar[str] = "join_blacklist"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, unique=True)
    enabled: bool = True
    reason: str = "你已被加入黑名单，无法申请入群。"
    note: str = ""
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class Announcement(SQLModel, table=True):
    __tablename__: ClassVar[str] = "announcements"

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(index=True)
    notice_id: str = Field(index=True)
    sender_id: int | None = None
    title: str = ""
    content: str = ""
    raw_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now_utc)
    synced_at: datetime = Field(default_factory=now_utc)


class FileDistributionJob(SQLModel, table=True):
    __tablename__: ClassVar[str] = "file_distribution_jobs"

    id: int | None = Field(default=None, primary_key=True)
    file_name: str
    file_path: str
    target_group_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    status: TaskStatus = TaskStatus.pending
    results: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now_utc)
    executed_at: datetime | None = None


class GroupFile(SQLModel, table=True):
    __tablename__: ClassVar[str] = "group_files"

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(index=True)
    file_id: str = Field(index=True)
    folder_id: str = ""
    file_name: str = ""
    busid: int | None = None
    size: int | None = None
    upload_time: datetime | None = None
    uploader_id: int | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    synced_at: datetime = Field(default_factory=now_utc)


class EssenceMessage(SQLModel, table=True):
    __tablename__: ClassVar[str] = "essence_messages"

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(index=True)
    message_id: int = Field(index=True)
    sender_id: int | None = None
    operator_id: int | None = None
    content: str = ""
    raw_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now_utc)
    synced_at: datetime = Field(default_factory=now_utc)


class Admin(SQLModel, table=True):
    __tablename__: ClassVar[str] = "admins"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    created_at: datetime = Field(default_factory=now_utc)


class AuditLog(SQLModel, table=True):
    __tablename__: ClassVar[str] = "audit_logs"

    id: int | None = Field(default=None, primary_key=True)
    admin_id: int | None = None
    action: str = Field(index=True)
    target: str = ""
    detail: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now_utc)
