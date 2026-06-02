from datetime import datetime, timezone

from sqlmodel import Session, SQLModel, create_engine, func, select

from app.models import ManagedGroup, MemberActivityStat


def test_member_activity_counts_messages_per_user_per_day() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ManagedGroup(group_id=1001, name="managed"))
        session.add(
            MemberActivityStat(
                group_id=1001,
                user_id=42,
                stat_date="2026-06-02",
                nickname="alice",
                message_count=3,
                last_active_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            MemberActivityStat(
                group_id=1001,
                user_id=43,
                stat_date="2026-06-02",
                nickname="bob",
                message_count=2,
                last_active_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

        total = session.exec(select(func.sum(MemberActivityStat.message_count))).one()
        active_members = session.exec(select(func.count(MemberActivityStat.id))).one()

    assert total == 5
    assert active_members == 2
