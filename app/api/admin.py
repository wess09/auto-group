import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from sqlmodel import delete, func, select

from app.api.deps import AdminDep, SessionDep
from app.core.config import get_settings
from app.models import (
    Announcement,
    AnswerRule,
    AuditLog,
    DedupeJob,
    DedupeWhitelist,
    EssenceMessage,
    FileDistributionJob,
    GroupFile,
    JoinRequest,
    LeaveEvent,
    MemberActivityStat,
    ManagedGroup,
)
from app.models.entities import TaskStatus
from app.schemas.admin import (
    AnswerRuleIn,
    AnswerRulePatch,
    DashboardOut,
    DedupeExecuteIn,
    DedupePreviewAction,
    DedupePreviewOut,
    DedupeWhitelistIn,
    DedupeWhitelistPatch,
    EssenceCreateIn,
    EssenceDeleteIn,
    FileDistributeIn,
    GenericResult,
    GroupFileDeleteIn,
    ManagedGroupIn,
    ManagedGroupPatch,
    NoticeDeleteIn,
    NoticeSendIn,
    UploadOut,
)
from app.services import onebot
from app.services.audit import add_audit
from app.services.dedupe import (
    create_realtime_dedupe_preview_job,
    get_dedupe_job_out,
    queue_dedupe_execute,
    run_dedupe_execute_task,
    run_realtime_preview_task,
)
from app.services.groups import touch_group
from app.services.sync import (
    sync_essence_messages,
    sync_group_files,
    sync_group_info,
    sync_group_notices,
)


router = APIRouter(prefix="/api/admin", tags=["admin"])


def _patch_model(model: object, payload: object) -> None:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(model, key, value)


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(session: SessionDep, admin: AdminDep) -> DashboardOut:
    del admin
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    trend_start = today_start - timedelta(days=6)
    recent_logs = session.exec(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(8)).all()
    top_groups = session.exec(
        select(ManagedGroup).order_by(ManagedGroup.current_members.desc()).limit(6)
    ).all()
    recent_leaves = session.exec(
        select(LeaveEvent)
        .where(LeaveEvent.group_id.in_(select(ManagedGroup.group_id)))
        .order_by(LeaveEvent.created_at.desc())
        .limit(8)
    ).all()
    join_breakdown_rows = session.exec(
        select(JoinRequest.result, func.count(JoinRequest.id)).group_by(JoinRequest.result)
    ).all()
    audit_trend_rows = session.exec(
        select(func.date(AuditLog.created_at), func.count(AuditLog.id))
        .where(AuditLog.created_at >= trend_start)
        .group_by(func.date(AuditLog.created_at))
    ).all()
    join_trend_rows = session.exec(
        select(func.date(JoinRequest.created_at), func.count(JoinRequest.id))
        .where(JoinRequest.created_at >= trend_start)
        .group_by(func.date(JoinRequest.created_at))
    ).all()
    leave_trend_rows = session.exec(
        select(func.date(LeaveEvent.created_at), func.count(LeaveEvent.id))
        .where(
            LeaveEvent.created_at >= trend_start,
            LeaveEvent.group_id.in_(select(ManagedGroup.group_id)),
        )
        .group_by(func.date(LeaveEvent.created_at))
    ).all()
    message_trend_rows = session.exec(
        select(MemberActivityStat.stat_date, func.sum(MemberActivityStat.message_count))
        .where(MemberActivityStat.stat_date >= trend_start.date().isoformat())
        .group_by(MemberActivityStat.stat_date)
    ).all()
    active_group_rows = session.exec(
        select(
            MemberActivityStat.group_id,
            func.sum(MemberActivityStat.message_count),
            func.count(MemberActivityStat.user_id),
        )
        .where(MemberActivityStat.stat_date >= trend_start.date().isoformat())
        .group_by(MemberActivityStat.group_id)
        .order_by(func.sum(MemberActivityStat.message_count).desc())
        .limit(8)
    ).all()
    active_member_rows = session.exec(
        select(
            MemberActivityStat.group_id,
            MemberActivityStat.user_id,
            func.max(MemberActivityStat.nickname),
            func.max(MemberActivityStat.card),
            func.sum(MemberActivityStat.message_count),
            func.max(MemberActivityStat.last_active_at),
        )
        .where(MemberActivityStat.stat_date >= trend_start.date().isoformat())
        .group_by(MemberActivityStat.group_id, MemberActivityStat.user_id)
        .order_by(func.sum(MemberActivityStat.message_count).desc())
        .limit(12)
    ).all()
    group_names = {
        group.group_id: group.name or str(group.group_id)
        for group in session.exec(select(ManagedGroup)).all()
    }
    audit_trend = {str(day): count for day, count in audit_trend_rows}
    join_trend = {str(day): count for day, count in join_trend_rows}
    leave_trend = {str(day): count for day, count in leave_trend_rows}
    message_trend = {str(day): count or 0 for day, count in message_trend_rows}
    activity_trend = []
    for offset in range(7):
        day = (trend_start + timedelta(days=offset)).date().isoformat()
        activity_trend.append(
            {
                "date": day,
                "admin_actions": audit_trend.get(day, 0),
                "join_requests": join_trend.get(day, 0),
                "leave_events": leave_trend.get(day, 0),
                "messages": message_trend.get(day, 0),
            }
        )
    return DashboardOut(
        groups=session.exec(select(func.count(ManagedGroup.id))).one(),
        enabled_groups=session.exec(
            select(func.count(ManagedGroup.id)).where(ManagedGroup.enabled == True)  # noqa: E712
        ).one(),
        join_requests=session.exec(select(func.count(JoinRequest.id))).one(),
        leave_events=session.exec(
            select(func.count(LeaveEvent.id)).where(
                LeaveEvent.group_id.in_(select(ManagedGroup.group_id))
            )
        ).one(),
        announcements=session.exec(select(func.count(Announcement.id))).one(),
        files=session.exec(select(func.count(GroupFile.id))).one(),
        essence_messages=session.exec(select(func.count(EssenceMessage.id))).one(),
        total_members=session.exec(select(func.sum(ManagedGroup.current_members))).one() or 0,
        today_join_requests=session.exec(
            select(func.count(JoinRequest.id)).where(JoinRequest.created_at >= today_start)
        ).one(),
        today_leave_events=session.exec(
            select(func.count(LeaveEvent.id)).where(
                LeaveEvent.created_at >= today_start,
                LeaveEvent.group_id.in_(select(ManagedGroup.group_id)),
            )
        ).one(),
        today_admin_actions=session.exec(
            select(func.count(AuditLog.id)).where(AuditLog.created_at >= today_start)
        ).one(),
        today_messages=session.exec(
            select(func.sum(MemberActivityStat.message_count)).where(
                MemberActivityStat.stat_date == today_start.date().isoformat()
            )
        ).one()
        or 0,
        today_active_members=session.exec(
            select(func.count(MemberActivityStat.id)).where(
                MemberActivityStat.stat_date == today_start.date().isoformat(),
                MemberActivityStat.message_count > 0,
            )
        ).one(),
        join_result_breakdown=[
            {"result": result or "unknown", "count": count}
            for result, count in join_breakdown_rows
        ],
        activity_trend=activity_trend,
        top_groups=[
            {
                "group_id": group.group_id,
                "name": group.name or str(group.group_id),
                "priority": group.priority,
                "current_members": group.current_members,
                "max_members": group.max_members,
                "enabled": group.enabled,
            }
            for group in top_groups
        ],
        active_groups=[
            {
                "group_id": group_id,
                "name": group_names.get(group_id, str(group_id)),
                "message_count": int(message_count or 0),
                "active_members": int(active_members or 0),
            }
            for group_id, message_count, active_members in active_group_rows
        ],
        active_members=[
            {
                "group_id": group_id,
                "group_name": group_names.get(group_id, str(group_id)),
                "user_id": user_id,
                "nickname": card or nickname or str(user_id),
                "message_count": int(message_count or 0),
                "last_active_at": last_active_at,
            }
            for group_id, user_id, nickname, card, message_count, last_active_at in active_member_rows
        ],
        recent_leave_events=[event.model_dump(mode="json") for event in recent_leaves],
        recent_audit_logs=[log.model_dump(mode="json") for log in recent_logs],
    )


@router.get("/groups")
def list_groups(session: SessionDep, admin: AdminDep) -> list[ManagedGroup]:
    del admin
    return session.exec(select(ManagedGroup).order_by(ManagedGroup.priority.desc())).all()


@router.post("/groups")
def create_group(payload: ManagedGroupIn, session: SessionDep, admin: AdminDep) -> ManagedGroup:
    exists = session.exec(select(ManagedGroup).where(ManagedGroup.group_id == payload.group_id)).first()
    if exists:
        raise HTTPException(status_code=409, detail="群已存在")
    group = ManagedGroup(**payload.model_dump())
    session.add(group)
    session.commit()
    session.refresh(group)
    add_audit(session, "group.create", str(group.group_id), payload.model_dump(), admin)
    return group


@router.patch("/groups/{group_id}")
def update_group(
    group_id: int,
    payload: ManagedGroupPatch,
    session: SessionDep,
    admin: AdminDep,
) -> ManagedGroup:
    group = session.exec(select(ManagedGroup).where(ManagedGroup.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="群不存在")
    _patch_model(group, payload)
    touch_group(group)
    session.add(group)
    session.commit()
    session.refresh(group)
    add_audit(session, "group.update", str(group_id), payload.model_dump(exclude_unset=True), admin)
    return group


@router.delete("/groups/{group_id}", response_model=GenericResult)
def delete_group(group_id: int, session: SessionDep, admin: AdminDep) -> GenericResult:
    group = session.exec(select(ManagedGroup).where(ManagedGroup.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="群不存在")
    session.delete(group)
    session.commit()
    add_audit(session, "group.delete", str(group_id), {}, admin)
    return GenericResult(ok=True, message="已删除")


@router.post("/groups/{group_id}/sync", response_model=GenericResult)
async def sync_group(group_id: int, session: SessionDep, admin: AdminDep) -> GenericResult:
    group = session.exec(select(ManagedGroup).where(ManagedGroup.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="群不存在")
    try:
        await sync_group_info(session, group)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"刷新群基础信息失败：{exc}") from exc
    add_audit(
        session,
        "group.sync_info",
        str(group_id),
        {"current_members": group.current_members, "max_members": group.max_members},
        admin,
    )
    return GenericResult(ok=True, message="已刷新群基础信息", data=group.model_dump(mode="json"))


@router.get("/rules")
def list_rules(session: SessionDep, admin: AdminDep) -> list[AnswerRule]:
    del admin
    return session.exec(select(AnswerRule).order_by(AnswerRule.id.desc())).all()


@router.post("/rules")
def create_rule(payload: AnswerRuleIn, session: SessionDep, admin: AdminDep) -> AnswerRule:
    rule = AnswerRule(**payload.model_dump())
    session.add(rule)
    session.commit()
    session.refresh(rule)
    add_audit(session, "rule.create", str(rule.id), payload.model_dump(mode="json"), admin)
    return rule


@router.patch("/rules/{rule_id}")
def update_rule(
    rule_id: int,
    payload: AnswerRulePatch,
    session: SessionDep,
    admin: AdminDep,
) -> AnswerRule:
    rule = session.get(AnswerRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    _patch_model(rule, payload)
    rule.updated_at = datetime.now(timezone.utc)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    add_audit(session, "rule.update", str(rule_id), payload.model_dump(exclude_unset=True), admin)
    return rule


@router.delete("/rules/{rule_id}", response_model=GenericResult)
def delete_rule(rule_id: int, session: SessionDep, admin: AdminDep) -> GenericResult:
    rule = session.get(AnswerRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    session.delete(rule)
    session.commit()
    add_audit(session, "rule.delete", str(rule_id), {}, admin)
    return GenericResult(ok=True, message="已删除")


@router.get("/join-requests")
def join_requests(session: SessionDep, admin: AdminDep) -> list[JoinRequest]:
    del admin
    return session.exec(select(JoinRequest).order_by(JoinRequest.created_at.desc()).limit(200)).all()


@router.get("/leave-events")
def leave_events(session: SessionDep, admin: AdminDep) -> list[LeaveEvent]:
    del admin
    return session.exec(
        select(LeaveEvent)
        .where(LeaveEvent.group_id.in_(select(ManagedGroup.group_id)))
        .order_by(LeaveEvent.created_at.desc())
        .limit(200)
    ).all()


@router.get("/dedupe/whitelist")
def dedupe_whitelist(session: SessionDep, admin: AdminDep) -> list[DedupeWhitelist]:
    del admin
    return session.exec(select(DedupeWhitelist).order_by(DedupeWhitelist.created_at.desc())).all()


@router.post("/dedupe/whitelist")
def create_dedupe_whitelist(
    payload: DedupeWhitelistIn,
    session: SessionDep,
    admin: AdminDep,
) -> DedupeWhitelist:
    exists = session.exec(
        select(DedupeWhitelist).where(DedupeWhitelist.user_id == payload.user_id)
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail="该 QQ 已在白名单中")
    item = DedupeWhitelist(**payload.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    add_audit(session, "dedupe.whitelist.create", str(item.user_id), payload.model_dump(), admin)
    return item


@router.patch("/dedupe/whitelist/{item_id}")
def update_dedupe_whitelist(
    item_id: int,
    payload: DedupeWhitelistPatch,
    session: SessionDep,
    admin: AdminDep,
) -> DedupeWhitelist:
    item = session.get(DedupeWhitelist, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="白名单不存在")
    _patch_model(item, payload)
    item.updated_at = datetime.now(timezone.utc)
    session.add(item)
    session.commit()
    session.refresh(item)
    add_audit(
        session,
        "dedupe.whitelist.update",
        str(item.user_id),
        payload.model_dump(exclude_unset=True),
        admin,
    )
    return item


@router.delete("/dedupe/whitelist/{item_id}", response_model=GenericResult)
def delete_dedupe_whitelist(
    item_id: int,
    session: SessionDep,
    admin: AdminDep,
) -> GenericResult:
    item = session.get(DedupeWhitelist, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="白名单不存在")
    user_id = item.user_id
    session.delete(item)
    session.commit()
    add_audit(session, "dedupe.whitelist.delete", str(user_id), {}, admin)
    return GenericResult(ok=True, message="已删除")


@router.post("/dedupe/preview", response_model=DedupePreviewOut)
async def dedupe_preview(session: SessionDep, admin: AdminDep) -> DedupePreviewOut:
    job = create_realtime_dedupe_preview_job(session)
    asyncio.create_task(run_realtime_preview_task(job.id))
    add_audit(session, "dedupe.preview.start", str(job.id), job.summary, admin)
    return DedupePreviewOut(
        job_id=job.id,
        status=job.status,
        summary=job.summary,
        duplicate_users=0,
        actions=[],
    )


@router.get("/dedupe/jobs/{job_id}", response_model=DedupePreviewOut)
def dedupe_job(job_id: int, session: SessionDep, admin: AdminDep) -> DedupePreviewOut:
    del admin
    data = get_dedupe_job_out(session, job_id)
    if data is None:
        raise HTTPException(status_code=404, detail="去重任务不存在")
    return DedupePreviewOut(
        job_id=data["job_id"],
        status=str(data["status"]),
        summary=data["summary"],
        duplicate_users=data["duplicate_users"],
        actions=[
            DedupePreviewAction(
                user_id=action["user_id"],
                nickname=action["nickname"],
                keep_group_id=action["keep_group_id"],
                kick_group_id=action["kick_group_id"],
                status=action["status"],
                error=action["error"],
            )
            for action in data["actions"]
        ],
    )


@router.post("/dedupe/execute")
async def dedupe_execute(
    payload: DedupeExecuteIn,
    session: SessionDep,
    admin: AdminDep,
) -> DedupeJob:
    try:
        job = queue_dedupe_execute(session, payload.job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    asyncio.create_task(run_dedupe_execute_task(job.id))
    add_audit(session, "dedupe.execute.start", str(job.id), job.summary, admin)
    return job


@router.get("/notices")
def list_notices(session: SessionDep, admin: AdminDep) -> list[Announcement]:
    del admin
    return session.exec(select(Announcement).order_by(Announcement.synced_at.desc())).all()


@router.post("/notices/sync/{group_id}", response_model=GenericResult)
async def notices_sync(group_id: int, session: SessionDep, admin: AdminDep) -> GenericResult:
    count = await sync_group_notices(session, group_id)
    add_audit(session, "notice.sync", str(group_id), {"count": count}, admin)
    return GenericResult(ok=True, message=f"已同步 {count} 条公告")


@router.post("/notices/send", response_model=GenericResult)
async def notices_send(payload: NoticeSendIn, session: SessionDep, admin: AdminDep) -> GenericResult:
    results: dict[int, str] = {}
    for group_id in payload.group_ids:
        try:
            await onebot.send_group_notice(group_id, payload.content)
            await sync_group_notices(session, group_id)
            results[group_id] = "success"
        except Exception as exc:  # noqa: BLE001
            results[group_id] = str(exc)
    add_audit(session, "notice.send", ",".join(map(str, payload.group_ids)), results, admin)
    return GenericResult(ok=all(v == "success" for v in results.values()), data=results)


@router.post("/notices/delete", response_model=GenericResult)
async def notices_delete(payload: NoticeDeleteIn, session: SessionDep, admin: AdminDep) -> GenericResult:
    results: dict[str, str] = {}
    for notice_id in payload.notice_ids:
        try:
            await onebot.delete_group_notice(payload.group_id, notice_id)
            session.exec(
                delete(Announcement).where(
                    Announcement.group_id == payload.group_id,
                    Announcement.notice_id == notice_id,
                )
            )
            session.commit()
            results[notice_id] = "success"
        except Exception as exc:  # noqa: BLE001
            results[notice_id] = str(exc)
    add_audit(session, "notice.delete", str(payload.group_id), results, admin)
    return GenericResult(ok=all(v == "success" for v in results.values()), data=results)


@router.post("/uploads", response_model=UploadOut)
async def upload_file(file: UploadFile = File(...), admin: AdminDep = None) -> UploadOut:
    del admin
    settings = get_settings()
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "upload.bin").name
    target = settings.upload_path / f"{int(datetime.now().timestamp())}_{safe_name}"
    size = 0
    with target.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            output.write(chunk)
    return UploadOut(file_name=safe_name, file_path=str(target), size=size)


@router.get("/files")
def list_files(session: SessionDep, admin: AdminDep) -> list[GroupFile]:
    del admin
    return session.exec(select(GroupFile).order_by(GroupFile.synced_at.desc())).all()


@router.post("/files/sync/{group_id}", response_model=GenericResult)
async def files_sync(group_id: int, session: SessionDep, admin: AdminDep) -> GenericResult:
    count = await sync_group_files(session, group_id)
    add_audit(session, "file.sync", str(group_id), {"count": count}, admin)
    return GenericResult(ok=True, message=f"已同步 {count} 个文件")


@router.post("/files/distribute")
async def files_distribute(
    payload: FileDistributeIn,
    session: SessionDep,
    admin: AdminDep,
) -> FileDistributionJob:
    path = Path(payload.file_path)
    if not path.exists():
        raise HTTPException(status_code=400, detail="文件路径不存在")
    job = FileDistributionJob(
        file_name=payload.name or path.name,
        file_path=str(path.resolve()),
        target_group_ids=payload.group_ids,
        status=TaskStatus.running,
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    results: dict[str, str] = {}
    for group_id in payload.group_ids:
        try:
            await onebot.upload_group_file(
                group_id,
                str(path.resolve()),
                name=payload.name or path.name,
                folder_id=payload.folder_id,
            )
            await sync_group_files(session, group_id)
            results[str(group_id)] = "success"
        except Exception as exc:  # noqa: BLE001
            results[str(group_id)] = str(exc)

    job.results = results
    job.status = TaskStatus.success if all(value == "success" for value in results.values()) else TaskStatus.failed
    job.executed_at = datetime.now(timezone.utc)
    session.add(job)
    session.commit()
    session.refresh(job)
    add_audit(session, "file.distribute", str(job.id), results, admin)
    return job


@router.post("/files/delete", response_model=GenericResult)
async def files_delete(
    payload: GroupFileDeleteIn,
    session: SessionDep,
    admin: AdminDep,
) -> GenericResult:
    await onebot.delete_group_file(payload.group_id, payload.file_id, payload.busid)
    session.exec(
        delete(GroupFile).where(
            GroupFile.group_id == payload.group_id,
            GroupFile.file_id == payload.file_id,
        )
    )
    session.commit()
    add_audit(session, "file.delete", str(payload.group_id), payload.model_dump(), admin)
    return GenericResult(ok=True, message="已删除")


@router.get("/files/url")
async def files_url(group_id: int, file_id: str, busid: int, admin: AdminDep) -> GenericResult:
    del admin
    data = await onebot.get_group_file_url(group_id, file_id, busid)
    return GenericResult(ok=True, data=data)


@router.get("/essence")
def list_essence(session: SessionDep, admin: AdminDep) -> list[EssenceMessage]:
    del admin
    return session.exec(select(EssenceMessage).order_by(EssenceMessage.synced_at.desc())).all()


@router.post("/essence/sync/{group_id}", response_model=GenericResult)
async def essence_sync(group_id: int, session: SessionDep, admin: AdminDep) -> GenericResult:
    count = await sync_essence_messages(session, group_id)
    add_audit(session, "essence.sync", str(group_id), {"count": count}, admin)
    return GenericResult(ok=True, message=f"已同步 {count} 条精华")


@router.post("/essence/create", response_model=GenericResult)
async def essence_create(
    payload: EssenceCreateIn,
    session: SessionDep,
    admin: AdminDep,
) -> GenericResult:
    results: dict[str, str] = {}
    for group_id in payload.group_ids:
        try:
            sent = await onebot.send_group_message(group_id, payload.content)
            message_id = sent.get("message_id") if isinstance(sent, dict) else sent
            await onebot.set_essence_msg(int(message_id))
            session.add(
                EssenceMessage(
                    group_id=group_id,
                    message_id=int(message_id),
                    content=payload.content,
                    raw_data={"created_by_dashboard": True},
                )
            )
            session.commit()
            results[str(group_id)] = "success"
        except Exception as exc:  # noqa: BLE001
            results[str(group_id)] = str(exc)
    add_audit(session, "essence.create", ",".join(map(str, payload.group_ids)), results, admin)
    return GenericResult(ok=all(v == "success" for v in results.values()), data=results)


@router.post("/essence/delete", response_model=GenericResult)
async def essence_delete(
    payload: EssenceDeleteIn,
    session: SessionDep,
    admin: AdminDep,
) -> GenericResult:
    results: dict[int, str] = {}
    for message_id in payload.message_ids:
        try:
            await onebot.delete_essence_msg(message_id)
            session.exec(
                delete(EssenceMessage).where(
                    EssenceMessage.group_id == payload.group_id,
                    EssenceMessage.message_id == message_id,
                )
            )
            session.commit()
            results[message_id] = "success"
        except Exception as exc:  # noqa: BLE001
            results[message_id] = str(exc)
    add_audit(session, "essence.delete", str(payload.group_id), {"results": results}, admin)
    return GenericResult(ok=all(v == "success" for v in results.values()), data=results)


@router.get("/audit-logs")
def audit_logs(session: SessionDep, admin: AdminDep) -> list[AuditLog]:
    del admin
    return session.exec(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(300)).all()
