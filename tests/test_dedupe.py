from sqlmodel import Session, SQLModel, create_engine, select

import pytest
from sqlmodel import func

from app.models import DedupeAction, DedupeJob, DedupeWhitelist, GroupMember, ManagedGroup
from app.services import dedupe
from app.services.dedupe import (
    create_dedupe_preview,
    queue_dedupe_execute,
    refresh_group_members,
    run_dedupe_execute_task,
    run_realtime_preview_task,
)


def test_dedupe_preview_keeps_highest_priority_group() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ManagedGroup(group_id=10, priority=200, enabled=True))
        session.add(ManagedGroup(group_id=20, priority=100, enabled=True))
        session.add(GroupMember(group_id=10, user_id=123, nickname="u"))
        session.add(GroupMember(group_id=20, user_id=123, nickname="u"))
        session.commit()

        job = create_dedupe_preview(session)
        action = session.exec(select(DedupeAction).where(DedupeAction.job_id == job.id)).one()

    assert action.keep_group_id == 10
    assert action.kick_group_id == 20


def test_dedupe_preview_skips_manual_whitelist() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ManagedGroup(group_id=10, priority=200, enabled=True))
        session.add(ManagedGroup(group_id=20, priority=100, enabled=True))
        session.add(DedupeWhitelist(user_id=123, note="protected"))
        session.add(GroupMember(group_id=10, user_id=123, nickname="u"))
        session.add(GroupMember(group_id=20, user_id=123, nickname="u"))
        session.commit()

        job = create_dedupe_preview(session)
        action_count = session.exec(
            select(func.count(DedupeAction.id)).where(DedupeAction.job_id == job.id)
        ).one()

    assert action_count == 0
    assert job.summary["manual_whitelist_skipped"] == 1


def test_dedupe_preview_skips_group_admins() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ManagedGroup(group_id=10, priority=200, enabled=True))
        session.add(ManagedGroup(group_id=20, priority=100, enabled=True))
        session.add(GroupMember(group_id=10, user_id=123, nickname="u", role="admin"))
        session.add(GroupMember(group_id=20, user_id=123, nickname="u"))
        session.commit()

        job = create_dedupe_preview(session)
        action_count = session.exec(
            select(func.count(DedupeAction.id)).where(DedupeAction.job_id == job.id)
        ).one()

    assert action_count == 0
    assert job.summary["role_whitelist_skipped"] == 1


@pytest.mark.asyncio
async def test_refresh_group_members_persists_role_and_count(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    async def fake_get_group_member_list(group_id: int) -> list[dict[str, object]]:
        assert group_id == 10
        return [
            {"user_id": 1, "nickname": "owner", "role": "owner"},
            {"user_id": 2, "nickname": "member", "role": "member"},
        ]

    monkeypatch.setattr(dedupe.onebot, "get_group_member_list", fake_get_group_member_list)
    with Session(engine) as session:
        group = ManagedGroup(group_id=10, priority=200, enabled=True)
        session.add(group)
        session.commit()
        session.refresh(group)

        count = await refresh_group_members(session, group)
        owner = session.exec(
            select(GroupMember).where(GroupMember.group_id == 10, GroupMember.user_id == 1)
        ).one()

    assert count == 2
    assert owner.role == "owner"


@pytest.mark.asyncio
async def test_realtime_preview_records_failed_group_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    async def fake_get_group_member_list(group_id: int) -> list[dict[str, object]]:
        raise RuntimeError(f"group {group_id} timeout")

    monkeypatch.setattr(dedupe, "engine", engine)
    monkeypatch.setattr(dedupe.onebot, "get_group_member_list", fake_get_group_member_list)
    with Session(engine) as session:
        session.add(ManagedGroup(group_id=10, name="failed", enabled=True))
        job = DedupeJob()
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id

    await run_realtime_preview_task(job_id)

    with Session(engine) as session:
        job = session.get(DedupeJob, job_id)

    assert job is not None
    assert job.summary["failed_groups"] == [10]
    assert job.summary["failed_details"] == [
        {"group_id": 10, "name": "failed", "error": "group 10 timeout"}
    ]


@pytest.mark.asyncio
async def test_execute_task_calls_group_kick_after_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    kicked: list[tuple[int, int]] = []

    async def fake_set_group_kick(
        group_id: int,
        user_id: int,
        reject_add_request: bool = False,
    ) -> None:
        del reject_add_request
        kicked.append((group_id, user_id))

    monkeypatch.setattr(dedupe, "engine", engine)
    monkeypatch.setattr(dedupe.onebot, "set_group_kick", fake_set_group_kick)
    with Session(engine) as session:
        job = DedupeJob(status="preview", summary={"phase": "preview_ready", "failed_groups": []})
        session.add(job)
        session.commit()
        session.refresh(job)
        session.add(
            DedupeAction(
                job_id=job.id,
                user_id=123,
                keep_group_id=10,
                kick_group_id=20,
            )
        )
        session.commit()
        queued = queue_dedupe_execute(session, job.id)
        job_id = queued.id

    await run_dedupe_execute_task(job_id)

    with Session(engine) as session:
        job = session.get(DedupeJob, job_id)
        action = session.exec(select(DedupeAction).where(DedupeAction.job_id == job_id)).one()

    assert kicked == [(20, 123)]
    assert job is not None
    assert job.summary["success"] == 1
    assert action.status == "success"
