import asyncio
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, delete, select

from app.core.config import get_settings
from app.models import (
    Announcement,
    AuditLog,
    DedupeAction,
    DedupeJob,
    EssenceMessage,
    GroupFile,
    GroupMember,
    ManagedGroup,
)
from app.models.entities import AdminJob, AdminJobItem, TaskStatus
from app.schemas.rpc import JobInput, JobOut, JobRef, PageInput
from app.services import dedupe, onebot
from app.services.admin import files
from app.services.admin.resources import list_resource, resolve_selection
from app.services.admin.notices import content_text
from app.services.admin.runtime import database


KINDS = {
    "groups.sync",
    "notices.sync",
    "notices.send",
    "notices.delete",
    "essence.sync",
    "essence.create",
    "essence.delete",
    "files.sync",
    "files.distribute",
    "files.delete",
    "files.rename",
    "files.rename-folder",
    "dedupe.preview",
    "dedupe.execute",
}
tasks: set[asyncio.Task] = set()
submission_lock = asyncio.Lock()
execution_limit = asyncio.Semaphore(2)


def find_request(session: Session, admin_id: int, request_id: str) -> JobRef | None:
    job = session.exec(
        select(AdminJob).where(AdminJob.admin_id == admin_id, AdminJob.request_id == request_id)
    ).first()
    return JobRef.model_validate(job, from_attributes=True) if job else None


def create_job(
    session: Session, kind: str, params: JobInput, admin_id: int, request_id: str
) -> tuple[JobRef, bool]:
    found = find_request(session, admin_id, request_id)
    if found:
        return found, False
    data = params.model_dump(mode="json")
    targets = [params.group_id] if params.group_id else resolve_selection(session, params.selection)
    inner_id = None
    if kind == "dedupe.preview":
        targets = list(
            session.exec(
                select(ManagedGroup.group_id)
                .where(ManagedGroup.enabled == True)  # noqa: E712
                .order_by(ManagedGroup.priority.desc(), ManagedGroup.group_id)
            ).all()
        )
        inner = DedupeJob(status=TaskStatus.pending, summary={"phase": "queued", "actions": 0})
        session.add(inner)
        session.flush()
        inner_id = inner.id
    elif kind == "dedupe.execute":
        preview = session.get(AdminJob, params.job_id)
        if not preview or preview.kind != "dedupe.preview" or preview.status != "preview":
            raise HTTPException(409, "只有完整成功的去重预览才能执行")
        inner = session.get(DedupeJob, preview.dedupe_job_id)
        if not inner or inner.status != TaskStatus.preview or inner.summary.get("failed_groups"):
            raise HTTPException(409, "预览不完整，禁止执行踢人")
        inner.status = TaskStatus.pending
        inner.summary = {**inner.summary, "phase": "execute_queued"}
        session.add(inner)
        inner_id = inner.id
    elif not targets:
        raise HTTPException(422, "请选择目标群")
    if kind in {"notices.send", "essence.create"} and not params.content.strip():
        raise HTTPException(422, "内容不能为空")
    if kind == "files.distribute":
        path = Path(params.file_path).resolve()
        if not path.is_file() or not path.is_relative_to(get_settings().upload_path):
            raise HTTPException(422, "只能分发已经上传的文件")
    if kind in {"files.rename", "files.rename-folder"} and not params.new_name.strip():
        raise HTTPException(422, "新名称不能为空")
    if kind == "files.delete" and not params.file_id:
        raise HTTPException(422, "缺少文件编号")
    if kind == "notices.delete" and not params.notice_id:
        raise HTTPException(422, "缺少公告编号")
    if kind == "essence.delete" and not params.message_id:
        raise HTTPException(422, "缺少消息编号")
    data["targets"] = targets
    job = AdminJob(
        kind=kind,
        params=data,
        admin_id=admin_id,
        request_id=request_id,
        dedupe_job_id=inner_id,
        summary={
            "total": int(inner.summary.get("actions", 0))
            if kind == "dedupe.execute"
            else len(targets),
            "completed": 0,
            "phase": "queued",
        },
    )
    session.add(job)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        found = find_request(session, admin_id, request_id)
        if found:
            return found, False
        raise
    session.refresh(job)
    return JobRef.model_validate(job, from_attributes=True), True


async def submit(kind: str, params: JobInput, admin_id: int, request_id: str) -> JobRef:
    async def register() -> JobRef:
        async with submission_lock:
            reference, created = await database(create_job, kind, params, admin_id, request_id)
        if created:
            execution = asyncio.create_task(run_queued(reference.id))
            tasks.add(execution)
            execution.add_done_callback(tasks.discard)
        return reference

    # Once submission starts, a disconnected browser must not leave a saved task unstarted.
    registration = asyncio.create_task(register())
    tasks.add(registration)

    def registered(task):
        tasks.discard(task)
        if not task.cancelled():
            task.exception()  # Consume errors if the request disconnected before receiving them.

    registration.add_done_callback(registered)
    return await asyncio.shield(registration)


async def run_queued(job_id: int) -> None:
    async with execution_limit:
        await run(job_id)


def job_out(session: Session, job_id: int) -> JobOut:
    job = session.get(AdminJob, job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    summary = dict(job.summary)
    if job.dedupe_job_id:
        inner = session.get(DedupeJob, job.dedupe_job_id)
        if inner:
            summary = {
                **{
                    key: value
                    for key, value in inner.summary.items()
                    if key not in {"skipped_members", "errors", "failed_details"}
                },
                **summary,
            }
    return JobOut(
        id=job.id,
        kind=job.kind,
        status=job.status,
        summary=summary,
        dedupe_job_id=job.dedupe_job_id,
    )


def job_actions(session: Session, job_id: int, params: PageInput):
    job = session.get(AdminJob, job_id)
    if not job or not job.dedupe_job_id:
        raise HTTPException(404, "去重任务不存在")
    return list_resource(
        session, "actions", params.model_copy(update={"job_id": job.dedupe_job_id})
    )


def load_job(session: Session, job_id: int) -> dict:
    job = session.get(AdminJob, job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    job.status = "running"
    job.updated_at = datetime.now(timezone.utc)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job.model_dump()


def progress(session: Session, job_id: int, **values) -> None:
    job = session.get(AdminJob, job_id)
    job.summary = {**job.summary, **values}
    job.updated_at = datetime.now(timezone.utc)
    session.add(job)
    session.commit()


def finish(session: Session, job_id: int, status: str, error: str = "") -> None:
    job = session.get(AdminJob, job_id)
    job.status = status
    job.updated_at = datetime.now(timezone.utc)
    job.summary = {
        **job.summary,
        "error": error,
        "phase": "preview_ready" if status == "preview" else "completed",
    }
    session.add(job)
    resource = job.kind.split(".")[0]
    if resource in {"groups", "notices", "files", "essence"}:
        changes = session.info.setdefault("admin_changes", {})
        changes[resource] = {}
        for gid in job.params.get("targets", []):
            changes[f"{resource}:{gid}"] = {"group_id": gid}
    session.add(
        AuditLog(
            admin_id=job.admin_id,
            action=job.kind,
            target=str(job_id),
            detail={"status": status, "error": error},
        )
    )
    if job.dedupe_job_id and status == "failed":
        inner = session.get(DedupeJob, job.dedupe_job_id)
        inner.status = TaskStatus.failed
        inner.summary = {**inner.summary, "error": error, "phase": "failed"}
        session.add(inner)
    session.commit()


def item_result(session: Session, job_id: int, gid: int, error: str = "", detail=None) -> None:
    session.add(
        AdminJobItem(
            job_id=job_id,
            group_id=gid,
            status="failed" if error else "success",
            error=error,
            detail=detail or {},
        )
    )
    session.commit()


def save_snapshot(session: Session, resource: str, gid: int, result) -> None:
    """Persist an upstream response in a short, independent transaction."""
    if resource == "groups":
        group = session.exec(select(ManagedGroup).where(ManagedGroup.group_id == gid)).first()
        if not group:
            raise HTTPException(404, "群不存在")
        group.name = str(result.get("group_name", result.get("name", group.name)))
        group.current_members = int(
            result.get("member_count", result.get("current_member_count", 0)) or 0
        )
        group.max_members = int(
            result.get("max_member_count", result.get("max_members", group.max_members)) or 0
        )
        group.updated_at = datetime.now(timezone.utc)
        session.add(group)
    elif resource == "members":
        session.exec(delete(GroupMember).where(GroupMember.group_id == gid))
        members = [dedupe._member_from_onebot(gid, row) for row in result]
        session.add_all([member for member in members if member.user_id > 0])
        group = session.exec(select(ManagedGroup).where(ManagedGroup.group_id == gid)).first()
        if group:
            group.current_members = sum(member.user_id > 0 for member in members)
            session.add(group)
    else:
        model = {"notices": Announcement, "files": GroupFile, "essence": EssenceMessage}[resource]
        session.exec(delete(model).where(model.group_id == gid))
        rows = (
            result
            if isinstance(result, list)
            else result.get(
                {"notices": "notices", "files": "files", "essence": "messages"}[resource],
                result.get("data", []),
            )
        )
        for row in rows or []:
            if resource == "notices":
                identifier = row.get("notice_id", row.get("id", row.get("fid")))
                if identifier is None:
                    continue
                item = Announcement(
                    group_id=gid,
                    notice_id=str(identifier),
                    sender_id=row.get("sender_id", row.get("user_id")),
                    title=str(row.get("title", "")),
                    content=content_text(
                        row.get("content", row.get("message", row.get("text", "")))
                    ),
                    raw_data=row,
                )
            elif resource == "files":
                identifier = row.get("file_id", row.get("id"))
                if identifier is None:
                    continue
                item = GroupFile(
                    group_id=gid,
                    file_id=str(identifier),
                    file_name=str(row.get("file_name", row.get("name", identifier))),
                    folder_id=str(row.get("folder_id", "")),
                    busid=row.get("busid"),
                    size=row.get("size", row.get("file_size")),
                    raw_data=row,
                )
            else:
                identifier = row.get("message_id", row.get("msg_seq"))
                if identifier is None:
                    continue
                item = EssenceMessage(
                    group_id=gid,
                    message_id=int(identifier),
                    sender_id=row.get("sender_id", row.get("sender_uin")),
                    operator_id=row.get("operator_id", row.get("operator_uin")),
                    content=str(row.get("content", row.get("message", ""))),
                    raw_data=row,
                )
            session.add(item)
    session.commit()


async def sync(resource: str, gid: int) -> None:
    fetch = {
        "groups": onebot.get_group_info,
        "members": onebot.get_group_member_list,
        "notices": onebot.get_group_notices,
        "files": onebot.get_group_root_files,
        "essence": onebot.get_essence_msg_list,
    }[resource]
    result = await fetch(gid)
    await database(save_snapshot, resource, gid, result)
    if resource == "files":
        files.invalidate(gid)


async def perform(kind: str, gid: int, params: dict) -> None:
    if kind.endswith(".sync"):
        await sync(kind.split(".")[0], gid)
    elif kind == "notices.send":
        await onebot.send_group_notice(gid, params["content"])
        await sync("notices", gid)
    elif kind == "notices.delete":
        await onebot.delete_group_notice(gid, params["notice_id"])
        await sync("notices", gid)
    elif kind == "essence.create":
        sent = await onebot.send_group_message(gid, params["content"])
        message_id = sent.get("message_id") if isinstance(sent, dict) else None
        if not message_id:
            raise RuntimeError("发送消息没有返回 message_id")
        await onebot.set_essence_msg(int(message_id))
        await sync("essence", gid)
    elif kind == "essence.delete":
        await onebot.delete_essence_msg(params["message_id"])
        await sync("essence", gid)
    elif kind == "files.distribute":
        await onebot.upload_group_file(
            gid, params["file_path"], params["name"] or None, params["folder_id"] or None
        )
        await sync("files", gid)
    elif kind == "files.delete":
        await onebot.delete_group_file(gid, params["file_id"], params["busid"])
        files.invalidate(gid)
    elif kind == "files.rename":
        await onebot.rename_group_file(
            gid, params["file_id"], params["current_parent_directory"], params["new_name"]
        )
        files.invalidate(gid)
    elif kind == "files.rename-folder":
        await onebot.rename_group_file_folder(gid, params["folder_id"], params["new_name"])
        files.invalidate(gid)


def build_preview(session: Session, outer_id: int, inner_id: int) -> None:
    inner = session.get(DedupeJob, inner_id)
    outer = session.get(AdminJob, outer_id)
    dedupe.create_dedupe_preview(session, inner, group_ids=outer.params["targets"])
    for row in inner.summary.get("skipped_members", []):
        session.add(AdminJobItem(job_id=outer_id, group_id=0, status="skipped", detail=row))
    session.commit()


def next_action(session: Session, inner_id: int, after: int):
    action = session.exec(
        select(DedupeAction)
        .where(DedupeAction.job_id == inner_id, DedupeAction.id > after)
        .order_by(DedupeAction.id)
        .limit(1)
    ).first()
    if not action:
        return None
    whitelist = dedupe._active_manual_whitelist(session)
    protected = session.exec(
        select(GroupMember.id)
        .where(
            GroupMember.user_id == action.user_id, col(GroupMember.role).in_(dedupe.PROTECTED_ROLES)
        )
        .limit(1)
    ).first()
    return action.model_dump(), action.user_id in whitelist or protected is not None


def save_action(session: Session, action_id: int, status: str, error: str) -> None:
    action = session.get(DedupeAction, action_id)
    action.status = status
    action.error = error
    action.executed_at = datetime.now(timezone.utc)
    session.add(action)
    session.commit()


def complete_inner(session: Session, inner_id: int, failures: int) -> None:
    inner = session.get(DedupeJob, inner_id)
    inner.status = TaskStatus.failed if failures else TaskStatus.success
    inner.executed_at = datetime.now(timezone.utc)
    inner.summary = {**inner.summary, "phase": "execute_done"}
    session.add(inner)
    session.commit()


async def run(job_id: int) -> None:
    try:
        job = await database(load_job, job_id)
        failures = 0
        if job["kind"] == "dedupe.execute":
            after = completed = skipped = 0
            while True:
                next_row = await database(next_action, job["dedupe_job_id"], after)
                if next_row is None:
                    break
                action, protected = next_row
                after = action["id"]
                error = ""
                status = "skipped" if protected else "success"
                if protected:
                    skipped += 1
                else:
                    try:
                        await onebot.set_group_kick(action["kick_group_id"], action["user_id"])
                    except Exception as exc:
                        error, status = str(exc), "failed"
                        failures += 1
                await database(save_action, action["id"], status, error)
                completed += 1
                await database(
                    progress,
                    job_id,
                    completed=completed,
                    failed=failures,
                    skipped=skipped,
                    phase="kicking",
                )
            await database(complete_inner, job["dedupe_job_id"], failures)
        else:
            targets = job["params"]["targets"]
            for index, gid in enumerate(targets):
                error = ""
                try:
                    if job["kind"] == "dedupe.preview":
                        await sync("members", gid)
                    else:
                        await perform(job["kind"], gid, job["params"])
                except Exception as exc:
                    error = str(exc) or type(exc).__name__
                    failures += 1
                await database(item_result, job_id, gid, error)
                await database(
                    progress,
                    job_id,
                    completed=index + 1,
                    failed=failures,
                    phase="fetching_members" if job["kind"] == "dedupe.preview" else "processing",
                )
            if job["kind"] == "dedupe.preview" and not failures:
                await database(build_preview, job_id, job["dedupe_job_id"])
                await database(finish, job_id, "preview")
                return
        await database(
            finish,
            job_id,
            "failed" if failures else "success",
            f"{failures} 项操作失败，请查看明细" if failures else "",
        )
    except asyncio.CancelledError:
        await database(finish, job_id, "interrupted", "服务停止，任务已中断；请核实外部操作结果")
        raise
    except Exception as exc:
        await database(finish, job_id, "failed", str(exc) or type(exc).__name__)


def recover(session: Session) -> None:
    for job in session.exec(
        select(AdminJob).where(col(AdminJob.status).in_(["pending", "running"]))
    ).all():
        job.status = "interrupted"
        job.summary = {**job.summary, "error": "服务重启，任务已中断；请核实外部操作结果"}
        session.add(job)
        if job.dedupe_job_id:
            inner = session.get(DedupeJob, job.dedupe_job_id)
            if inner:
                inner.status = TaskStatus.failed
                session.add(inner)
    session.commit()
