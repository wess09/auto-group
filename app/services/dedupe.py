import asyncio
from nonebot import logger
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, col, delete, select

from app.core.database import engine
from app.models import DedupeAction, DedupeJob, DedupeWhitelist, GroupMember, ManagedGroup
from app.models.entities import TaskStatus
from app.services import onebot
from app.services.groups import touch_group


PROTECTED_ROLES = {"owner", "admin"}


def _pick(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return default


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _required_id(value: int | None) -> int:
    if value is None:
        raise RuntimeError("数据库对象缺少 ID")
    return value


def _serialize_action(action: DedupeAction) -> dict[str, Any]:
    return {
        "id": action.id,
        "user_id": action.user_id,
        "nickname": action.nickname,
        "keep_group_id": action.keep_group_id,
        "kick_group_id": action.kick_group_id,
        "status": action.status,
        "error": action.error,
        "created_at": action.created_at,
        "executed_at": action.executed_at,
    }


def _update_job(
    session: Session,
    job: DedupeJob,
    *,
    status: TaskStatus | None = None,
    **summary: Any,
) -> DedupeJob:
    if status is not None:
        job.status = status
    job.summary = {**(job.summary or {}), **summary}
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def _enabled_groups(session: Session) -> dict[int, ManagedGroup]:
    return {
        group.group_id: group
        for group in session.exec(
            select(ManagedGroup)
            .where(col(ManagedGroup.enabled) == True)  # noqa: E712
            .order_by(col(ManagedGroup.priority).desc(), col(ManagedGroup.group_id).asc())
        ).all()
    }


def _active_manual_whitelist(session: Session) -> set[int]:
    return set(
        session.exec(
            select(col(DedupeWhitelist.user_id)).where(col(DedupeWhitelist.enabled) == True)  # noqa: E712
        ).all()
    )


def _member_from_onebot(group_id: int, item: dict[str, Any]) -> GroupMember:
    return GroupMember(
        group_id=group_id,
        user_id=int(_pick(item, "user_id", default=0) or 0),
        nickname=str(_pick(item, "nickname", default="")),
        card=str(_pick(item, "card", default="")),
        role=str(_pick(item, "role", default="")),
        joined_at=None,
        synced_at=_now(),
    )


async def refresh_group_members(session: Session, group: ManagedGroup) -> int:
    members = await onebot.get_group_member_list(group.group_id)
    if not isinstance(members, list):
        raise RuntimeError(f"get_group_member_list 返回异常：{type(members).__name__}")
    session.exec(delete(GroupMember).where(col(GroupMember.group_id) == group.group_id))
    count = 0
    for item in members:
        member = _member_from_onebot(group.group_id, item)
        if member.user_id <= 0:
            continue
        session.add(member)
        count += 1
    group.current_members = count
    touch_group(group)
    session.add(group)
    session.commit()
    return count


def create_dedupe_preview(session: Session, job: DedupeJob | None = None) -> DedupeJob:
    groups = _enabled_groups(session)
    manual_whitelist = _active_manual_whitelist(session)
    members = session.exec(select(GroupMember)).all()
    by_user: dict[int, list[GroupMember]] = defaultdict(list)
    role_protected_users: set[int] = set()
    manual_skipped_users: set[int] = set()
    role_skipped_users: set[int] = set()
    skipped_details: list[dict[str, Any]] = []

    for member in members:
        if member.group_id not in groups:
            continue
        if member.role in PROTECTED_ROLES:
            role_protected_users.add(member.user_id)
        by_user[member.user_id].append(member)

    if job is None:
        job = DedupeJob(status=TaskStatus.preview, summary={})
        session.add(job)
        session.commit()
        session.refresh(job)
    else:
        session.exec(delete(DedupeAction).where(col(DedupeAction.job_id) == _required_id(job.id)))
    job_id = _required_id(job.id)

    action_count = 0
    duplicate_users = 0
    protected_duplicate_users = 0
    for user_id, user_members in by_user.items():
        if len(user_members) <= 1:
            continue
        duplicate_users += 1
        if user_id in manual_whitelist:
            manual_skipped_users.add(user_id)
            protected_duplicate_users += 1
            sample = user_members[0]
            skipped_details.append(
                {
                    "user_id": user_id,
                    "nickname": sample.card or sample.nickname or str(user_id),
                    "reason": "手动白名单",
                    "groups": [member.group_id for member in user_members],
                }
            )
            continue
        if user_id in role_protected_users:
            role_skipped_users.add(user_id)
            protected_duplicate_users += 1
            sample = user_members[0]
            skipped_details.append(
                {
                    "user_id": user_id,
                    "nickname": sample.card or sample.nickname or str(user_id),
                    "reason": "群主或管理员",
                    "groups": [member.group_id for member in user_members],
                }
            )
            continue
        sorted_members = sorted(
            user_members,
            key=lambda item: (
                groups[item.group_id].priority,
                -groups[item.group_id].current_members,
                -item.group_id,
            ),
            reverse=True,
        )
        keep = sorted_members[0]
        for kick in sorted_members[1:]:
            session.add(
                DedupeAction(
                    job_id=job_id,
                    user_id=user_id,
                    nickname=kick.card or kick.nickname,
                    keep_group_id=keep.group_id,
                    kick_group_id=kick.group_id,
                )
            )
            action_count += 1

    job.status = TaskStatus.preview
    job.summary = {
        **(job.summary or {}),
        "phase": "preview_ready",
        "duplicate_users": duplicate_users,
        "protected_duplicate_users": protected_duplicate_users,
        "manual_whitelist_skipped": len(manual_skipped_users),
        "role_whitelist_skipped": len(role_skipped_users),
        "whitelist_skipped": len(manual_skipped_users | role_skipped_users),
        "skipped_members": skipped_details,
        "actions": action_count,
        "completed_at": _now().isoformat(),
    }
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


async def run_realtime_preview_task(job_id: int) -> None:
    with Session(engine) as session:
        job = session.get(DedupeJob, job_id)
        if not job:
            return
        groups = list(_enabled_groups(session).values())
        total_groups = len(groups)
        _update_job(
            session,
            job,
            status=TaskStatus.running,
            phase="fetching_members",
            total_groups=total_groups,
            completed_groups=0,
            failed_groups=[],
            current_group_id=None,
            errors={},
            started_at=_now().isoformat(),
        )

        failed_groups: list[int] = []
        errors: dict[str, str] = {}
        failed_details: list[dict[str, Any]] = []
        for index, group in enumerate(groups, start=1):
            _update_job(
                session,
                job,
                phase="fetching_members",
                current_group_id=group.group_id,
                completed_groups=index - 1,
                progress=int(((index - 1) / total_groups) * 100) if total_groups else 100,
            )
            try:
                count = await refresh_group_members(session, group)
                _update_job(session, job, last_group_members=count)
            except Exception as exc:  # noqa: BLE001
                error_text = str(exc) or exc.__class__.__name__
                failed_groups.append(group.group_id)
                errors[str(group.group_id)] = error_text
                failed_details.append(
                    {
                        "group_id": group.group_id,
                        "name": group.name or str(group.group_id),
                        "error": error_text,
                    }
                )
                logger.warning(f"去重预览拉取群 {group.group_id} 成员列表失败：{error_text}")
                _update_job(
                    session,
                    job,
                    failed_groups=failed_groups,
                    errors=errors,
                    failed_details=failed_details,
                )

        if failed_groups:
            _update_job(
                session,
                job,
                status=TaskStatus.failed,
                phase="fetch_failed",
                current_group_id=None,
                completed_groups=total_groups,
                progress=100,
                failed_groups=failed_groups,
                errors=errors,
                failed_details=failed_details,
                error="部分群成员列表拉取失败，预览不完整，已禁止执行踢人。",
                completed_at=_now().isoformat(),
            )
            return

        _update_job(
            session,
            job,
            phase="building_preview",
            current_group_id=None,
            completed_groups=total_groups,
            progress=100,
        )
        create_dedupe_preview(session, job)


def create_realtime_dedupe_preview_job(session: Session) -> DedupeJob:
    job = DedupeJob(
        status=TaskStatus.pending,
        summary={
            "phase": "queued",
            "progress": 0,
            "total_groups": 0,
            "completed_groups": 0,
            "failed_groups": [],
            "actions": 0,
        },
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def start_realtime_dedupe_preview(session: Session) -> DedupeJob:
    job = create_realtime_dedupe_preview_job(session)
    asyncio.create_task(run_realtime_preview_task(_required_id(job.id)))
    return job


def get_dedupe_job_out(session: Session, job_id: int) -> dict[str, Any] | None:
    job = session.get(DedupeJob, job_id)
    if not job:
        return None
    actions = session.exec(
        select(DedupeAction).where(col(DedupeAction.job_id) == job_id).order_by(col(DedupeAction.id))
    ).all()
    return {
        "job_id": job.id,
        "status": job.status,
        "summary": job.summary or {},
        "duplicate_users": int((job.summary or {}).get("duplicate_users", 0)),
        "actions": [_serialize_action(action) for action in actions],
    }


async def run_dedupe_execute_task(job_id: int) -> None:
    with Session(engine) as session:
        job = session.get(DedupeJob, job_id)
        if not job:
            return
        if job.status not in {TaskStatus.preview, TaskStatus.pending}:
            _update_job(
                session,
                job,
                status=TaskStatus.failed,
                phase="execute_failed",
                error="只有完整预览任务才能执行踢人。",
            )
            return
        if (job.summary or {}).get("phase") not in {"preview_ready", "execute_queued"}:
            _update_job(
                session,
                job,
                status=TaskStatus.failed,
                phase="execute_failed",
                error="只有完整预览任务才能执行踢人。",
            )
            return

        manual_whitelist = _active_manual_whitelist(session)
        protected_by_role = {
            member.user_id
            for member in session.exec(select(GroupMember)).all()
            if member.role in PROTECTED_ROLES
        }
        actions = session.exec(
            select(DedupeAction).where(col(DedupeAction.job_id) == job_id).order_by(col(DedupeAction.id))
        ).all()
        total_actions = len(actions)
        _update_job(
            session,
            job,
            status=TaskStatus.running,
            phase="kicking",
            execute_total=total_actions,
            execute_completed=0,
            execute_progress=0,
        )

        ok_count = 0
        failed_count = 0
        skipped_count = 0
        for index, action in enumerate(actions, start=1):
            if action.user_id in manual_whitelist:
                action.status = "skipped"
                action.error = "手动白名单保护"
                skipped_count += 1
            elif action.user_id in protected_by_role:
                action.status = "skipped"
                action.error = "群主或管理员保护"
                skipped_count += 1
            else:
                try:
                    await onebot.set_group_kick(
                        action.kick_group_id,
                        action.user_id,
                        reject_add_request=False,
                    )
                    action.status = "success"
                    action.executed_at = _now()
                    ok_count += 1
                except Exception as exc:  # noqa: BLE001
                    action.status = "failed"
                    action.error = str(exc)
                    failed_count += 1
            session.add(action)
            _update_job(
                session,
                job,
                execute_completed=index,
                execute_progress=int((index / total_actions) * 100) if total_actions else 100,
                success=ok_count,
                failed=failed_count,
                skipped=skipped_count,
            )

        job.status = TaskStatus.failed if failed_count else TaskStatus.success
        job.summary = {
            **(job.summary or {}),
            "phase": "execute_done",
            "success": ok_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "executed_at": _now().isoformat(),
        }
        job.executed_at = _now()
        session.add(job)
        session.commit()


def queue_dedupe_execute(session: Session, job_id: int) -> DedupeJob:
    job = session.get(DedupeJob, job_id)
    if not job:
        raise ValueError("去重任务不存在")
    failed_groups = (job.summary or {}).get("failed_groups") or []
    if job.status != TaskStatus.preview or failed_groups:
        raise ValueError("只有完整成功的预览任务才能执行踢人")
    job.status = TaskStatus.pending
    job.summary = {**(job.summary or {}), "phase": "execute_queued"}
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def start_dedupe_execute(session: Session, job_id: int) -> DedupeJob:
    job = queue_dedupe_execute(session, job_id)
    asyncio.create_task(run_dedupe_execute_task(job_id))
    return job


async def execute_dedupe_job(session: Session, job_id: int) -> DedupeJob:
    return start_dedupe_execute(session, job_id)
