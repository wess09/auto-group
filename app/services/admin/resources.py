from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import String, cast, or_
from sqlmodel import Session, col, func, select

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
from app.schemas.admin import (
    AnswerRuleIn,
    AnswerRulePatch,
    DedupeWhitelistIn,
    DedupeWhitelistPatch,
    JoinBlacklistIn,
    JoinBlacklistPatch,
    ManagedGroupIn,
    ManagedGroupPatch,
    MessageModerationRuleIn,
    MessageModerationRulePatch,
    RecallAdminIn,
    RecallAdminPatch,
)
from app.schemas.rpc import MoveInput, PageInput, PageResult, Selection, WriteInput
from app.schemas.resources import LIST_MODELS, DETAIL_MODELS
from app.services.admin.notices import content_text


RESOURCES = {
    "groups": (ManagedGroup, ManagedGroupIn, ManagedGroupPatch),
    "rules": (AnswerRule, AnswerRuleIn, AnswerRulePatch),
    "blacklist": (JoinBlacklist, JoinBlacklistIn, JoinBlacklistPatch),
    "moderation": (MessageModerationRule, MessageModerationRuleIn, MessageModerationRulePatch),
    "whitelist": (DedupeWhitelist, DedupeWhitelistIn, DedupeWhitelistPatch),
    "recall-admins": (RecallAdmin, RecallAdminIn, RecallAdminPatch),
    "notices": (Announcement, None, None),
    "essence": (EssenceMessage, None, None),
    "files": (GroupFile, None, None),
    "joins": (JoinRequest, None, None),
    "leaves": (LeaveEvent, None, None),
    "audits": (AuditLog, None, None),
    "actions": (DedupeAction, None, None),
    "jobs": (AdminJob, None, None),
    "job-items": (AdminJobItem, None, None),
}
HEAVY_FIELDS = {"raw_event", "raw_data", "detail", "params"}


def conditions(model: Any, params: PageInput) -> list[Any]:
    terms = []
    for name in ("group_id", "enabled", "status", "job_id"):
        value = getattr(params, name)
        if value is not None and hasattr(model, name):
            terms.append(getattr(model, name) == value)
    if params.q:
        fields = [
            getattr(model, name)
            for name in (
                "name",
                "file_name",
                "title",
                "nickname",
                "note",
                "reason",
                "action",
                "user_id",
                "group_id",
                "content",
                "answer_text",
                "target",
                "error",
                "kick_group_id",
                "keep_group_id",
                "kind",
            )
            if hasattr(model, name)
        ]
        escaped = params.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        terms.append(
            or_(*(cast(field, String).ilike(f"%{escaped}%", escape="\\") for field in fields))
        )
    if hasattr(model, "created_at"):
        if params.start_date:
            terms.append(model.created_at >= datetime.fromisoformat(params.start_date))
        if params.end_date:
            terms.append(model.created_at < datetime.fromisoformat(params.end_date))
    if model is LeaveEvent:
        terms.append(col(LeaveEvent.group_id).in_(select(ManagedGroup.group_id)))
    return terms


def serialize(row: Any, detail: bool = False) -> dict[str, Any]:
    data = row.model_dump(mode="json")
    if isinstance(row, Announcement):
        data["content"] = content_text(data["content"])
    if not detail:
        for key, value in data.items():
            if isinstance(value, str) and len(value) > 180:
                data[key] = value[:180] + "…"
        if isinstance(data.get("patterns"), list):
            patterns = data["patterns"]
            data["patterns"] = [str(value)[:180] for value in patterns[:3]]
            if len(patterns) > 3:
                data["patterns"].append(f"…（共 {len(patterns)} 条）")
        for field in HEAVY_FIELDS:
            data.pop(field, None)
        if "content" in data:
            data["content"] = str(data["content"])[:180]
        if "summary" in data:
            data["summary"] = {
                key: value
                for key, value in data["summary"].items()
                if key not in {"skipped_members", "failed_details", "errors"}
            }
    return data


def list_resource(session: Session, resource: str, params: PageInput) -> PageResult:
    model = RESOURCES[resource][0]
    terms = conditions(model, params)
    total = session.exec(select(func.count()).select_from(model).where(*terms)).one()
    order = [col(model.id).desc()]
    if model is ManagedGroup:
        order = [col(model.priority).desc(), col(model.group_id).asc()]
    elif hasattr(model, "created_at"):
        order = [col(model.created_at).desc(), col(model.id).desc()]
    rows = session.exec(
        select(model)
        .where(*terms)
        .order_by(*order)
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    ).all()
    return PageResult(
        items=[
            LIST_MODELS[resource].model_validate(serialize(row)).model_dump(mode="json")
            for row in rows
        ],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


def get_resource(session: Session, resource: str, item_id: int) -> dict[str, Any]:
    item = session.get(RESOURCES[resource][0], item_id)
    if item is None:
        raise HTTPException(404, "记录不存在")
    return (
        DETAIL_MODELS[resource].model_validate(serialize(item, detail=True)).model_dump(mode="json")
    )


def write_resource(
    session: Session, resource: str, action: str, params: WriteInput, admin_id: int
) -> dict[str, Any]:
    model, create_schema, patch_schema = RESOURCES[resource]
    if create_schema is None:
        raise HTTPException(400, "该资源不能直接修改")
    if action == "create":
        data = create_schema.model_validate(params.data).model_dump()
        item = model(**data)
    else:
        item = session.get(model, params.id)
        if item is None:
            raise HTTPException(404, "记录不存在")
        data = patch_schema.model_validate(params.data).model_dump(exclude_unset=True)
        # Reject null for non-nullable fields, while allowing a global rule's group_id.
        if any(value is None and key != "group_id" for key, value in data.items()):
            raise HTTPException(422, "字段不能为空")
        for key, value in data.items():
            setattr(item, key, value)
        item.updated_at = datetime.now(timezone.utc)
    session.add(item)
    session.flush()
    session.add(
        AuditLog(
            admin_id=admin_id,
            action=f"{resource}.{action}",
            target=str(item.id),
            detail=params.data,
        )
    )
    session.commit()
    session.refresh(item)
    return (
        DETAIL_MODELS[resource].model_validate(serialize(item, detail=True)).model_dump(mode="json")
    )


def delete_resource(session: Session, resource: str, item_id: int, admin_id: int) -> dict:
    model, create_schema, _ = RESOURCES[resource]
    if create_schema is None:
        raise HTTPException(400, "该资源不能直接删除")
    item = session.get(model, item_id)
    if item is None:
        raise HTTPException(404, "记录不存在")
    session.delete(item)
    session.add(AuditLog(admin_id=admin_id, action=f"{resource}.delete", target=str(item_id)))
    session.commit()
    return {"ok": True}


def move_group(session: Session, params: MoveInput, admin_id: int) -> dict:
    rows = list(
        session.exec(
            select(ManagedGroup).order_by(
                col(ManagedGroup.priority).desc(), col(ManagedGroup.group_id).asc()
            )
        ).all()
    )
    item = next((row for row in rows if row.group_id == params.group_id), None)
    if item is None:
        raise HTTPException(404, "群不存在")
    if params.position > len(rows):
        raise HTTPException(422, "目标位置超出范围")
    rows.remove(item)
    rows.insert(params.position - 1, item)
    for index, row in enumerate(rows):
        row.priority = max(1000, len(rows) * 10) - index * 10
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
    session.add(AuditLog(admin_id=admin_id, action="groups.move", target=str(params.group_id)))
    session.commit()
    return {"ok": True}


def resolve_selection(session: Session, selection: Selection) -> list[int]:
    query = select(ManagedGroup.group_id)
    if selection.mode == "ids":
        query = query.where(col(ManagedGroup.group_id).in_(selection.ids))
    else:
        query = query.where(
            *conditions(ManagedGroup, PageInput(q=selection.q, enabled=selection.enabled))
        )
        if selection.excluded_ids:
            query = query.where(col(ManagedGroup.group_id).not_in(selection.excluded_ids))
    return list(session.exec(query.order_by(ManagedGroup.group_id)).all())
