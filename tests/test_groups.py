from sqlmodel import Session, SQLModel, create_engine

from app.models import ManagedGroup
from app.services.groups import get_recommended_group


def test_recommended_group_uses_priority_and_capacity() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ManagedGroup(group_id=1, priority=100, current_members=100, max_members=100, join_url="a"))
        session.add(ManagedGroup(group_id=2, priority=90, current_members=10, max_members=100, join_url="b"))
        session.add(ManagedGroup(group_id=3, priority=80, enabled=False, join_url="c"))
        session.commit()

        group = get_recommended_group(session)

    assert group is not None
    assert group.group_id == 2
