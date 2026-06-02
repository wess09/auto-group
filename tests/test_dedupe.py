from sqlmodel import Session, SQLModel, create_engine, select

from app.models import DedupeAction, GroupMember, ManagedGroup
from app.services.dedupe import create_dedupe_preview


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
