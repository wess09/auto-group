import threading
import time
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, col, func, select

from app.models import (
    Announcement,
    AuditLog,
    EssenceMessage,
    GroupFile,
    JoinRequest,
    LeaveEvent,
    ManagedGroup,
    MemberActivityStat,
)
from app.services.admin.resources import serialize
from app.services.admin.runtime import hub


cache: dict[str, tuple[float, int, dict]] = {}
cache_lock = threading.Lock()


def dashboard_section(session: Session, section: str) -> dict:
    version = hub.versions.get(f"dashboard.{section}", 0)
    with cache_lock:
        saved = cache.get(section)
    # Frequent message commits must not defeat the TTL of aggregate scans.
    heavy = section in {"trends", "breakdown", "rankings"}
    if saved and saved[0] > time.monotonic() and (heavy or saved[1] == version):
        return saved[2]
    result = query_section(session, section)
    with cache_lock:
        cache[section] = (time.monotonic() + 15, version, result)
    return result


def query_section(session: Session, section: str) -> dict:
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    managed_leaves = col(LeaveEvent.group_id).in_(select(ManagedGroup.group_id))

    def count(model, *where):
        return session.exec(select(func.count()).select_from(model).where(*where)).one()

    if section == "summary":
        return {
            "groups": count(ManagedGroup),
            "enabled_groups": count(ManagedGroup, ManagedGroup.enabled == True),  # noqa: E712
            "total_members": session.exec(select(func.sum(ManagedGroup.current_members))).one()
            or 0,
            "join_requests": count(JoinRequest),
            "leave_events": count(LeaveEvent, managed_leaves),
            "announcements": count(Announcement),
            "files": count(GroupFile),
            "essence_messages": count(EssenceMessage),
            "today_join_requests": count(JoinRequest, JoinRequest.created_at >= today),
            "today_leave_events": count(LeaveEvent, LeaveEvent.created_at >= today, managed_leaves),
            "today_admin_actions": count(AuditLog, AuditLog.created_at >= today),
            "today_messages": session.exec(
                select(func.sum(MemberActivityStat.message_count)).where(
                    MemberActivityStat.stat_date == today.date().isoformat()
                )
            ).one()
            or 0,
            "today_active_members": count(
                MemberActivityStat,
                MemberActivityStat.stat_date == today.date().isoformat(),
                MemberActivityStat.message_count > 0,
            ),
        }
    if section == "breakdown":
        rows = session.exec(
            select(JoinRequest.result, func.count()).group_by(JoinRequest.result)
        ).all()
        return {"items": [{"result": result, "count": count} for result, count in rows]}
    if section == "trends":
        start = today - timedelta(days=6)
        results = {}
        for name, model in (
            ("admin_actions", AuditLog),
            ("join_requests", JoinRequest),
            ("leave_events", LeaveEvent),
        ):
            terms = [model.created_at >= start]
            if model is LeaveEvent:
                terms.append(managed_leaves)
            rows = session.exec(
                select(func.date(model.created_at), func.count())
                .where(*terms)
                .group_by(func.date(model.created_at))
            ).all()
            results[name] = dict(rows)
        results["messages"] = dict(
            session.exec(
                select(MemberActivityStat.stat_date, func.sum(MemberActivityStat.message_count))
                .where(MemberActivityStat.stat_date >= start.date().isoformat())
                .group_by(MemberActivityStat.stat_date)
            ).all()
        )
        return {
            "items": [
                {
                    "date": (start + timedelta(days=i)).date().isoformat(),
                    **{
                        name: values.get((start + timedelta(days=i)).date().isoformat(), 0)
                        for name, values in results.items()
                    },
                }
                for i in range(7)
            ]
        }
    if section == "rankings":
        top = session.exec(
            select(ManagedGroup)
            .order_by(col(ManagedGroup.current_members).desc(), ManagedGroup.id)
            .limit(6)
        ).all()
        start = (today - timedelta(days=6)).date().isoformat()
        active_groups = session.exec(
            select(
                MemberActivityStat.group_id,
                ManagedGroup.name,
                func.sum(MemberActivityStat.message_count),
                func.count(func.distinct(MemberActivityStat.user_id)),
            )
            .join(ManagedGroup, ManagedGroup.group_id == MemberActivityStat.group_id)
            .where(MemberActivityStat.stat_date >= start)
            .group_by(MemberActivityStat.group_id, ManagedGroup.name)
            .order_by(
                func.sum(MemberActivityStat.message_count).desc(), MemberActivityStat.group_id
            )
            .limit(8)
        ).all()
        active_members = session.exec(
            select(
                MemberActivityStat.group_id,
                MemberActivityStat.user_id,
                func.max(MemberActivityStat.nickname),
                func.max(MemberActivityStat.card),
                func.sum(MemberActivityStat.message_count),
            )
            .where(MemberActivityStat.stat_date >= start)
            .group_by(MemberActivityStat.group_id, MemberActivityStat.user_id)
            .order_by(
                func.sum(MemberActivityStat.message_count).desc(),
                MemberActivityStat.user_id,
                MemberActivityStat.group_id,
            )
            .limit(12)
        ).all()
        return {
            "top_groups": [serialize(row) for row in top],
            "active_groups": [
                {
                    "group_id": gid,
                    "name": name,
                    "message_count": messages,
                    "active_members": members,
                }
                for gid, name, messages, members in active_groups
            ],
            "active_members": [
                {
                    "group_id": gid,
                    "user_id": uid,
                    "nickname": card or nickname or str(uid),
                    "message_count": messages,
                }
                for gid, uid, nickname, card, messages in active_members
            ],
        }
    return {
        "leaves": [
            serialize(row)
            for row in session.exec(
                select(LeaveEvent)
                .where(managed_leaves)
                .order_by(col(LeaveEvent.created_at).desc(), col(LeaveEvent.id).desc())
                .limit(8)
            ).all()
        ],
        "audits": [
            serialize(row)
            for row in session.exec(
                select(AuditLog)
                .order_by(col(AuditLog.created_at).desc(), col(AuditLog.id).desc())
                .limit(8)
            ).all()
        ],
    }
