from collections import defaultdict
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import DedupeAction, DedupeJob, GroupMember, ManagedGroup
from app.models.entities import TaskStatus
from app.services import onebot


def create_dedupe_preview(session: Session) -> DedupeJob:
    groups = {
        group.group_id: group
        for group in session.exec(
            select(ManagedGroup).where(ManagedGroup.enabled == True)  # noqa: E712
        ).all()
    }
    members = session.exec(select(GroupMember)).all()
    by_user: dict[int, list[GroupMember]] = defaultdict(list)
    for member in members:
        if member.group_id in groups:
            by_user[member.user_id].append(member)

    job = DedupeJob(status=TaskStatus.preview, summary={})
    session.add(job)
    session.commit()
    session.refresh(job)

    action_count = 0
    duplicate_users = 0
    for user_id, user_members in by_user.items():
        if len(user_members) <= 1:
            continue
        duplicate_users += 1
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
                    job_id=job.id,
                    user_id=user_id,
                    nickname=kick.card or kick.nickname,
                    keep_group_id=keep.group_id,
                    kick_group_id=kick.group_id,
                )
            )
            action_count += 1

    job.summary = {"duplicate_users": duplicate_users, "actions": action_count}
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


async def execute_dedupe_job(session: Session, job_id: int) -> DedupeJob:
    job = session.get(DedupeJob, job_id)
    if not job:
        raise ValueError("去重任务不存在")
    actions = session.exec(select(DedupeAction).where(DedupeAction.job_id == job_id)).all()
    job.status = TaskStatus.running
    session.add(job)
    session.commit()

    ok_count = 0
    failed_count = 0
    for action in actions:
        try:
            await onebot.set_group_kick(
                action.kick_group_id,
                action.user_id,
                reject_add_request=False,
            )
            action.status = "success"
            action.executed_at = datetime.now(timezone.utc)
            ok_count += 1
        except Exception as exc:  # noqa: BLE001
            action.status = "failed"
            action.error = str(exc)
            failed_count += 1
        session.add(action)

    job.status = TaskStatus.failed if failed_count else TaskStatus.success
    job.summary = {**job.summary, "success": ok_count, "failed": failed_count}
    job.executed_at = datetime.now(timezone.utc)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job
