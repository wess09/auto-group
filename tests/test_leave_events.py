from sqlmodel import Session, SQLModel, create_engine, select

from app.models import LeaveEvent, ManagedGroup


def test_leave_event_query_only_returns_managed_groups() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ManagedGroup(group_id=1001, name="managed"))
        session.add(LeaveEvent(group_id=1001, user_id=1))
        session.add(LeaveEvent(group_id=2002, user_id=2))
        session.commit()

        rows = session.exec(
            select(LeaveEvent).where(LeaveEvent.group_id.in_(select(ManagedGroup.group_id)))
        ).all()

    assert [row.group_id for row in rows] == [1001]
