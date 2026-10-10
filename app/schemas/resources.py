"""Explicit resource DTOs, independent of table serialization and new DB columns."""

from pydantic import BaseModel, ConfigDict, create_model

from app.models import (
    Announcement,
    AnswerRule,
    AuditLog,
    DedupeAction,
    DedupeWhitelist,
    EssenceMessage,
    GroupFile,
    JoinBlacklist,
    JoinRequest,
    LeaveEvent,
    ManagedGroup,
    MessageModerationRule,
    RecallAdmin,
)
from app.models.entities import AdminJob, AdminJobItem


class ResourceOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


COMMON = "id created_at updated_at"
RESOURCE_FIELDS = {
    "groups": (
        ManagedGroup,
        COMMON
        + " group_id name priority enabled max_members current_members join_url min_qq_level"
        + " max_wrong_answers wrong_answer_window_hours redirect_message_template note",
        "",
    ),
    "rules": (AnswerRule, COMMON + " name enabled group_id match_mode logic_mode patterns", ""),
    "moderation": (
        MessageModerationRule,
        COMMON
        + " name enabled group_id patterns cloud_review_enabled ocr_enabled image_review_enabled"
        + " action mute_duration_seconds note",
        "",
    ),
    "blacklist": (JoinBlacklist, COMMON + " user_id enabled reason note", ""),
    "whitelist": (DedupeWhitelist, COMMON + " user_id enabled note", ""),
    "recall-admins": (RecallAdmin, COMMON + " user_id enabled note", ""),
    "notices": (
        Announcement,
        "id group_id notice_id sender_id title content created_at synced_at",
        "raw_data",
    ),
    "essence": (
        EssenceMessage,
        "id group_id message_id sender_id operator_id content created_at synced_at",
        "raw_data",
    ),
    "files": (
        GroupFile,
        "id group_id file_id folder_id file_name busid size upload_time uploader_id synced_at",
        "raw_data",
    ),
    "joins": (
        JoinRequest,
        "id flag user_id group_id answer_text qq_level wrong_answer_count apply_status apply_error"
        + " matched_rule_id recommended_group_id result reason created_at",
        "raw_event",
    ),
    "leaves": (LeaveEvent, "id group_id user_id operator_id sub_type created_at", "raw_event"),
    "audits": (AuditLog, "id admin_id action target created_at", "detail"),
    "actions": (
        DedupeAction,
        "id job_id user_id keep_group_id kick_group_id nickname status error created_at executed_at",
        "",
    ),
    "jobs": (AdminJob, COMMON + " admin_id request_id kind status summary dedupe_job_id", "params"),
    "job-items": (AdminJobItem, "id job_id group_id status error", "detail"),
}


def dto(name, model, fields):
    return create_model(
        name,
        __base__=ResourceOut,
        **{
            field: (int if field == "id" else model.model_fields[field].annotation, ...)
            for field in fields.split()
        },
    )


LIST_MODELS = {
    resource: dto(model.__name__ + "ListOut", model, fields)
    for resource, (model, fields, _) in RESOURCE_FIELDS.items()
}
DETAIL_MODELS = {
    resource: dto(model.__name__ + "DetailOut", model, fields + " " + detail)
    for resource, (model, fields, detail) in RESOURCE_FIELDS.items()
}
