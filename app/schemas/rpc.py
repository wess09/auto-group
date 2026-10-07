from typing import Any, Generic, Literal, TypeVar

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


T = TypeVar("T")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Request(Input):
    v: Literal[1]
    id: str = Field(min_length=1, max_length=100)
    method: str = Field(min_length=1, max_length=100)
    params: dict[str, Any] = Field(default_factory=dict)


class PageInput(Input):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)
    q: str = Field(default="", max_length=200)
    group_id: int | None = None
    enabled: bool | None = None
    status: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    job_id: int | None = None

    @field_validator("start_date", "end_date")
    @classmethod
    def valid_date(cls, value: str | None) -> str | None:
        if value is not None:
            datetime.fromisoformat(value)
        return value


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class IdInput(Input):
    id: int = Field(gt=0)


class WriteInput(Input):
    id: int | None = Field(default=None, gt=0)
    data: dict[str, Any]


class MoveInput(Input):
    group_id: int = Field(gt=0)
    position: int = Field(ge=1)


class Selection(Input):
    mode: Literal["ids", "all_matching"] = "ids"
    ids: list[int] = Field(default_factory=list)
    q: str = ""
    enabled: bool | None = None
    excluded_ids: list[int] = Field(default_factory=list)


class JobInput(Input):
    selection: Selection = Field(default_factory=Selection)
    group_id: int | None = Field(default=None, gt=0)
    job_id: int | None = Field(default=None, gt=0)
    content: str = ""
    file_path: str = ""
    name: str = ""
    folder_id: str = ""
    file_id: str = ""
    busid: int = 0
    notice_id: str = ""
    message_id: int | None = None
    new_name: str = ""
    current_parent_directory: str = "/"


class JobRef(BaseModel):
    id: int
    kind: str
    status: str


class JobOut(JobRef):
    summary: dict[str, Any]
    dedupe_job_id: int | None = None


class BrowseInput(PageInput):
    group_id: int = Field(gt=0)
    folder_id: str = ""


class FileUrlInput(Input):
    group_id: int = Field(gt=0)
    file_id: str
    busid: int


class AuthInput(Input):
    token: str


class TopicsInput(Input):
    topics: list[str] = Field(max_length=64)


class RequestIdInput(Input):
    request_id: str


class OkOut(BaseModel):
    ok: bool


class GroupOptionOut(BaseModel):
    id: int
    group_id: int
    name: str
    enabled: bool


class FileEntryOut(BaseModel):
    type: Literal["folder", "file"]
    name: str
    folder_id: str | None = None
    file_id: str | None = None
    size: int | None = None
    busid: int | None = None
    upload_time: int | None = None


class FileUrlOut(BaseModel):
    url: str


class DashboardSummaryOut(BaseModel):
    groups: int
    enabled_groups: int
    total_members: int
    join_requests: int
    leave_events: int
    announcements: int
    files: int
    essence_messages: int
    today_join_requests: int
    today_leave_events: int
    today_admin_actions: int
    today_messages: int
    today_active_members: int


class TrendOut(BaseModel):
    date: str
    messages: int
    admin_actions: int
    join_requests: int
    leave_events: int


class TrendsOut(BaseModel):
    items: list[TrendOut]


class ResultCountOut(BaseModel):
    result: str
    count: int


class BreakdownOut(BaseModel):
    items: list[ResultCountOut]


class GroupActivityOut(BaseModel):
    group_id: int
    name: str
    message_count: int
    active_members: int


class MemberActivityOut(BaseModel):
    group_id: int
    user_id: int
    nickname: str
    message_count: int
